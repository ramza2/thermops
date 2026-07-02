"""재학습 후보 기반 학습 실행 서비스."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.time import utc_now
from app.models.entities import (
    DriftReport,
    FeatureDataset,
    ModelVersion,
    RetrainingCandidate,
    TrainingConfig,
)
from app.services.airflow_client import AirflowClient, AirflowClientError, map_airflow_state
from app.services.drift_detection_service import (
    SOURCE_TYPE_COMPUTED,
    SOURCE_TYPE_SEED,
    resolve_retraining_candidate_source_type,
    retraining_candidate_to_dict,
)
from app.services.system_config_service import DEFAULT_CONFIG_VALUES
from app.services.training_service import TrainingJobParams, run_training_job

DEFAULT_FEATURE_SET_ID = ""
DEFAULT_CONFIG_ID = ""
RETRAINING_DAG_ID = "retraining_dag"
EXECUTION_MODE_SYNC = "SYNC"
EXECUTION_MODE_AIRFLOW = "AIRFLOW"
AIRFLOW_ACTIVE_STATES = {"queued", "running"}

_PREFERRED_CONFIG_BY_MODEL: dict[str, str] = {
    "heat_demand_two_stage_catboost": "TRC-TPL-TWO-STAGE-CATBOOST",
    "heat_demand_catboost": "TRC-TPL-CATBOOST",
    "heat_demand_lightgbm": "TRC-TPL-LAG-ROLL",
    "heat_demand_baseline_lag24h": "TRC-TPL-BASELINE",
    "heat_demand_baseline_ma": "TRC-TPL-BASELINE",
    "heat_demand_gbdt": "TRC-TPL-LAG-ROLL",
}


def _retrained_model_name(base_name: str | None) -> str:
    name = (base_name or DEFAULT_CONFIG_VALUES.get("default_model_name", "heat_demand_lightgbm")).strip()
    if name.endswith("_retrained"):
        return name
    return f"{name}_retrained"


def _preferred_config_for_model(model_name: str | None) -> str | None:
    if not model_name:
        return None
    return _PREFERRED_CONFIG_BY_MODEL.get(model_name.replace("_retrained", ""))


async def _get_candidate(db: AsyncSession, candidate_id: str) -> RetrainingCandidate:
    candidate = (
        await db.execute(select(RetrainingCandidate).where(RetrainingCandidate.candidate_id == candidate_id))
    ).scalar_one_or_none()
    if not candidate:
        raise ValueError("재학습 후보를 찾을 수 없습니다.")
    return candidate


def _validate_source_type(candidate: RetrainingCandidate) -> str:
    source_type = resolve_retraining_candidate_source_type(candidate)
    if source_type == SOURCE_TYPE_SEED:
        raise PermissionError("SEED candidate cannot be trained")
    if source_type != SOURCE_TYPE_COMPUTED:
        raise PermissionError("COMPUTED 후보만 재학습할 수 있습니다.")
    return source_type


def _validate_for_trigger(candidate: RetrainingCandidate) -> None:
    _validate_source_type(candidate)
    if candidate.status == "REJECTED":
        raise PermissionError("반려된 후보는 재학습할 수 없습니다.")
    if candidate.status == "TRAINING":
        raise RuntimeError("이미 재학습이 진행 중입니다.")
    if candidate.status == "TRAINED" and candidate.training_job_id:
        raise RuntimeError("이미 재학습이 완료된 후보입니다.")
    if candidate.status not in ("APPROVED",):
        raise PermissionError(f"승인된 후보만 재학습할 수 있습니다. (현재: {candidate.status})")


def _validate_for_internal(candidate: RetrainingCandidate) -> None:
    _validate_source_type(candidate)
    if candidate.status == "REJECTED":
        raise PermissionError("반려된 후보는 재학습할 수 없습니다.")
    if candidate.status == "TRAINED" and candidate.training_job_id:
        raise RuntimeError("이미 재학습이 완료된 후보입니다.")
    if candidate.status not in ("APPROVED", "TRAINING"):
        raise PermissionError(f"승인 또는 학습 중 상태만 내부 재학습할 수 있습니다. (현재: {candidate.status})")


async def _resolve_feature_set_id(
    db: AsyncSession,
    candidate: RetrainingCandidate,
    drift_report: DriftReport | None,
    warnings: list[str],
) -> str:
    if candidate.feature_set_id:
        return candidate.feature_set_id
    if drift_report and drift_report.feature_set_id:
        return drift_report.feature_set_id
    raise ValueError("재학습 후보에 feature_set_id가 없습니다. 후보 또는 Drift 리포트에 Feature Set을 지정하세요.")


async def _resolve_config_id(
    db: AsyncSession,
    feature_set_id: str,
    warnings: list[str],
    source_model_name: str | None = None,
) -> str:
    preferred_id = _preferred_config_for_model(source_model_name)
    if preferred_id:
        preferred_cfg = (
            await db.execute(select(TrainingConfig).where(TrainingConfig.config_id == preferred_id))
        ).scalar_one_or_none()
        if preferred_cfg:
            if preferred_cfg.feature_set_id == feature_set_id:
                return preferred_cfg.config_id
            warnings.append(
                f"source model {source_model_name} 선호 config {preferred_id}의 feature_set 불일치 — "
                f"{feature_set_id}용 설정 검색"
            )
        else:
            warnings.append(f"선호 config {preferred_id} 없음 — {feature_set_id}용 설정 검색")

    cfg = (
        await db.execute(
            select(TrainingConfig)
            .where(TrainingConfig.feature_set_id == feature_set_id, TrainingConfig.active_yn == "Y")
            .order_by(TrainingConfig.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if cfg:
        return cfg.config_id
    raise ValueError(f"feature_set {feature_set_id}에 연결된 학습 설정이 없습니다.")


async def _resolve_train_period(
    db: AsyncSession,
    drift_report: DriftReport | None,
    feature_set_id: str,
    warnings: list[str],
) -> tuple[date | None, date | None]:
    if drift_report and drift_report.baseline_start_at and drift_report.current_end_at:
        return drift_report.baseline_start_at.date(), drift_report.current_end_at.date()

    row = (
        await db.execute(
            select(FeatureDataset.feature_at)
            .where(FeatureDataset.feature_json["feature_set_id"].astext == feature_set_id)
            .order_by(FeatureDataset.feature_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if row:
        min_at = (
            await db.execute(
                select(FeatureDataset.feature_at)
                .where(FeatureDataset.feature_json["feature_set_id"].astext == feature_set_id)
                .order_by(FeatureDataset.feature_at.asc())
                .limit(1)
            )
        ).scalar_one_or_none()
        if min_at:
            warnings.append("drift_report 기간 없음 — feature_dataset 최신 기간 사용")
            return min_at.date() if isinstance(min_at, datetime) else min_at, (
                row.date() if isinstance(row, datetime) else row
            )

    warnings.append("학습 기간 정보 없음 — training service 기본 분할 사용")
    return None, None


def _build_train_response(candidate: RetrainingCandidate, train_result: dict[str, Any], warnings: list[str]) -> dict[str, Any]:
    payload = retraining_candidate_to_dict(candidate)
    return {
        "candidate": payload,
        "training_job": {
            "job_id": train_result.get("job_id"),
            "status": train_result.get("status"),
            "pipeline_run_id": train_result.get("pipeline_run_id"),
        },
        "model_version": {
            "model_version_id": train_result.get("model_version_id"),
            "model_name": train_result.get("model_name"),
            "model_version": train_result.get("model_version"),
        },
        "metrics": train_result.get("metrics"),
        "warnings": warnings,
        "status": train_result.get("status"),
        "execution_mode": candidate.execution_mode,
        "retraining_dag_run_id": candidate.retraining_dag_run_id,
    }


async def _is_airflow_run_active(dag_run_id: str) -> bool:
    client = AirflowClient()
    try:
        dag_run = await client.get_dag_run(RETRAINING_DAG_ID, dag_run_id)
    except AirflowClientError:
        return False
    return (dag_run.get("state") or "").lower() in AIRFLOW_ACTIVE_STATES


async def _execute_retraining_core(
    db: AsyncSession,
    candidate: RetrainingCandidate,
    *,
    mark_training: bool,
) -> dict[str, Any]:
    drift_report: DriftReport | None = None
    if candidate.drift_report_id:
        drift_report = (
            await db.execute(select(DriftReport).where(DriftReport.drift_report_id == candidate.drift_report_id))
        ).scalar_one_or_none()

    warnings: list[str] = []
    feature_set_id = await _resolve_feature_set_id(db, candidate, drift_report, warnings)

    base_model_name = candidate.model_name
    if candidate.model_version_id:
        mv = (
            await db.execute(select(ModelVersion).where(ModelVersion.model_version_id == candidate.model_version_id))
        ).scalar_one_or_none()
        if mv:
            base_model_name = mv.model_name

    config_id = await _resolve_config_id(db, feature_set_id, warnings, base_model_name)
    train_start, train_end = await _resolve_train_period(db, drift_report, feature_set_id, warnings)

    site_ids = [candidate.site_id] if candidate.site_id else None
    model_name_override = _retrained_model_name(base_model_name)
    now = utc_now()

    if mark_training:
        candidate.status = "TRAINING"
        candidate.error_message = None
        if not candidate.retraining_started_at:
            candidate.retraining_started_at = now
        candidate.updated_at = now
        await db.flush()

    train_result = await run_training_job(
        db,
        TrainingJobParams(
            config_id=config_id,
            site_ids=site_ids,
            train_start_at=train_start,
            train_end_at=train_end,
            register_model_yn=True,
            triggered_by=f"retraining:{candidate.candidate_id}",
            model_name_override=model_name_override,
        ),
    )
    warnings.extend(train_result.get("warnings") or [])

    candidate.training_job_id = train_result.get("job_id")
    candidate.mlflow_run_id = train_result.get("mlflow_run_id")
    candidate.train_result_summary = {
        "metrics": train_result.get("metrics"),
        "model_name": train_result.get("model_name"),
        "model_version": train_result.get("model_version"),
        "feature_set_id": train_result.get("feature_set_id") or feature_set_id,
        "config_id": config_id,
        "warnings": warnings,
    }
    candidate.updated_at = now

    if train_result.get("status") == "SUCCESS":
        candidate.status = "TRAINED"
        candidate.new_model_version_id = train_result.get("model_version_id")
        candidate.trained_at = now
        candidate.retraining_finished_at = now
        candidate.error_message = None
    else:
        candidate.status = "FAILED"
        candidate.error_message = train_result.get("error_message", "모델 학습 실패")
        candidate.retraining_finished_at = now
        candidate.train_result_summary = {
            **(candidate.train_result_summary or {}),
            "failed_step": "run_retraining",
            "error_message": candidate.error_message,
        }

    await db.commit()
    await db.refresh(candidate)
    return _build_train_response(candidate, train_result, warnings)


async def train_retraining_candidate_sync(db: AsyncSession, candidate_id: str, *, internal: bool = False) -> dict[str, Any]:
    """동기 재학습 실행. internal=True이면 Airflow DAG용(TRAINING 상태 허용)."""
    candidate = await _get_candidate(db, candidate_id)
    if internal:
        _validate_for_internal(candidate)
    else:
        _validate_for_trigger(candidate)

    if candidate.retraining_dag_run_id and candidate.status == "TRAINING" and not internal:
        if await _is_airflow_run_active(candidate.retraining_dag_run_id):
            raise RuntimeError("이미 재학습이 진행 중입니다.")

    candidate.execution_mode = EXECUTION_MODE_SYNC
    was_training = candidate.status == "TRAINING"
    mark_training = not (internal and was_training)
    return await _execute_retraining_core(db, candidate, mark_training=mark_training)


async def train_retraining_candidate(db: AsyncSession, candidate_id: str) -> dict[str, Any]:
    """기존 P1-2 동기 API 호환."""
    return await train_retraining_candidate_sync(db, candidate_id, internal=False)


async def trigger_retraining_dag(
    db: AsyncSession,
    candidate_id: str,
    *,
    requested_by: str | None = None,
) -> dict[str, Any]:
    candidate = await _get_candidate(db, candidate_id)
    _validate_for_trigger(candidate)

    if candidate.retraining_dag_run_id and candidate.status == "TRAINING":
        if await _is_airflow_run_active(candidate.retraining_dag_run_id):
            raise RuntimeError("이미 재학습 DAG가 실행 중입니다.")

    now = utc_now()
    execution_request_id = f"RTR-{uuid4().hex[:8].upper()}"
    conf = {
        "candidate_id": candidate_id,
        "execution_request_id": execution_request_id,
        "requested_by": requested_by,
    }

    candidate.status = "TRAINING"
    candidate.execution_mode = EXECUTION_MODE_AIRFLOW
    candidate.retraining_requested_at = now
    candidate.retraining_started_at = now
    candidate.error_message = None
    candidate.updated_at = now
    await db.flush()

    client = AirflowClient()
    try:
        dag_run = await client.trigger_dag(RETRAINING_DAG_ID, conf)
    except AirflowClientError as exc:
        candidate.status = "FAILED"
        candidate.error_message = f"Airflow 트리거 실패: {exc}"
        candidate.retraining_finished_at = utc_now()
        candidate.train_result_summary = {
            "failed_step": "trigger_dag",
            "error_message": str(exc),
        }
        await db.commit()
        raise RuntimeError(str(exc)) from exc

    dag_run_id = dag_run.get("dag_run_id")
    candidate.retraining_dag_run_id = dag_run_id
    await db.commit()
    await db.refresh(candidate)

    payload = retraining_candidate_to_dict(candidate)
    return {
        "candidate": payload,
        "execution_mode": EXECUTION_MODE_AIRFLOW,
        "retraining_dag_run_id": dag_run_id,
        "dag_run_id": dag_run_id,
        "dag_id": RETRAINING_DAG_ID,
        "airflow_state": dag_run.get("state"),
        "status": candidate.status,
        "execution_request_id": execution_request_id,
    }


async def mark_retraining_candidate_failed(
    db: AsyncSession,
    candidate_id: str,
    *,
    error_message: str,
    failed_step: str | None = None,
    traceback_summary: str | None = None,
) -> dict[str, Any]:
    # TODO: 내부 API service token 인증 적용
    candidate = await _get_candidate(db, candidate_id)
    if candidate.status in ("TRAINED", "FAILED"):
        return retraining_candidate_to_dict(candidate)

    now = utc_now()
    candidate.status = "FAILED"
    candidate.error_message = error_message
    candidate.retraining_finished_at = now
    candidate.updated_at = now
    summary = dict(candidate.train_result_summary or {})
    summary.update({
        "failed_step": failed_step or "airflow_task",
        "error_message": error_message,
    })
    if traceback_summary:
        summary["traceback"] = traceback_summary[-2000:]
    candidate.train_result_summary = summary
    await db.commit()
    await db.refresh(candidate)
    return retraining_candidate_to_dict(candidate)


async def sync_retraining_candidate_from_airflow(
    db: AsyncSession,
    candidate: RetrainingCandidate,
) -> list[str]:
    warnings: list[str] = []
    if candidate.status != "TRAINING" or not candidate.retraining_dag_run_id:
        return warnings

    client = AirflowClient()
    try:
        dag_run = await client.get_dag_run(RETRAINING_DAG_ID, candidate.retraining_dag_run_id)
    except AirflowClientError as exc:
        warnings.append(f"Airflow 상태 조회 실패: {exc}")
        return warnings

    airflow_state = (dag_run.get("state") or "").lower()
    mapped = map_airflow_state(airflow_state)

    if airflow_state in AIRFLOW_ACTIVE_STATES:
        return warnings

    if mapped == "FAILED" and candidate.status == "TRAINING":
        candidate.status = "FAILED"
        candidate.error_message = candidate.error_message or f"Airflow DAG 실패 (state={airflow_state})"
        candidate.retraining_finished_at = candidate.retraining_finished_at or utc_now()
        summary = dict(candidate.train_result_summary or {})
        summary.setdefault("failed_step", "airflow_dag")
        summary["airflow_state"] = airflow_state
        candidate.train_result_summary = summary
        candidate.updated_at = utc_now()
        await db.commit()
        await db.refresh(candidate)
        warnings.append("Airflow FAILED — 후보 상태를 FAILED로 갱신했습니다.")
    elif mapped == "SUCCESS" and candidate.status == "TRAINING":
        warnings.append("Airflow SUCCESS이나 후보가 TRAINING입니다. finalize 단계를 확인하세요.")

    return warnings


async def get_retraining_candidate_detail(
    db: AsyncSession,
    candidate_id: str,
    *,
    sync_airflow: bool = False,
) -> dict[str, Any]:
    candidate = await _get_candidate(db, candidate_id)
    warnings: list[str] = []
    if sync_airflow:
        warnings = await sync_retraining_candidate_from_airflow(db, candidate)
        await db.refresh(candidate)

    site_name = None
    payload = retraining_candidate_to_dict(candidate, site_name)
    if warnings:
        payload["sync_warnings"] = warnings
    return payload
