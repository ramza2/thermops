"""재학습 후보 기반 학습 실행 서비스."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

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
from app.services.drift_detection_service import (
    SOURCE_TYPE_COMPUTED,
    SOURCE_TYPE_SEED,
    resolve_retraining_candidate_source_type,
    retraining_candidate_to_dict,
)
from app.services.system_config_service import DEFAULT_CONFIG_VALUES
from app.services.training_service import TrainingJobParams, run_training_job

DEFAULT_FEATURE_SET_ID = "FS-TPL-LAG-ROLL"
DEFAULT_CONFIG_ID = "TRC-TPL-LAG-ROLL"


def _retrained_model_name(base_name: str | None) -> str:
    name = (base_name or DEFAULT_CONFIG_VALUES.get("default_model_name", "heat_demand_lightgbm")).strip()
    if name.endswith("_retrained"):
        return name
    return f"{name}_retrained"


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
    warnings.append(f"feature_set_id 없음 — 기본값 {DEFAULT_FEATURE_SET_ID} 사용")
    return DEFAULT_FEATURE_SET_ID


async def _resolve_config_id(db: AsyncSession, feature_set_id: str, warnings: list[str]) -> str:
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
    warnings.append(f"feature_set {feature_set_id}용 학습 설정 없음 — {DEFAULT_CONFIG_ID} 사용")
    return DEFAULT_CONFIG_ID


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


async def train_retraining_candidate(db: AsyncSession, candidate_id: str) -> dict[str, Any]:
    candidate = (
        await db.execute(select(RetrainingCandidate).where(RetrainingCandidate.candidate_id == candidate_id))
    ).scalar_one_or_none()
    if not candidate:
        raise ValueError("재학습 후보를 찾을 수 없습니다.")

    source_type = resolve_retraining_candidate_source_type(candidate)
    if source_type == SOURCE_TYPE_SEED:
        raise PermissionError("SEED candidate cannot be trained")
    if source_type != SOURCE_TYPE_COMPUTED:
        raise PermissionError("COMPUTED 후보만 재학습할 수 있습니다.")

    if candidate.status == "TRAINING":
        raise RuntimeError("이미 재학습이 진행 중입니다.")
    if candidate.status == "TRAINED" and candidate.training_job_id:
        raise RuntimeError("이미 재학습이 완료된 후보입니다.")
    if candidate.status == "REJECTED":
        raise PermissionError("반려된 후보는 재학습할 수 없습니다.")
    if candidate.status not in ("APPROVED",):
        raise PermissionError(f"승인된 후보만 재학습할 수 있습니다. (현재: {candidate.status})")

    drift_report: DriftReport | None = None
    if candidate.drift_report_id:
        drift_report = (
            await db.execute(select(DriftReport).where(DriftReport.drift_report_id == candidate.drift_report_id))
        ).scalar_one_or_none()

    warnings: list[str] = []
    feature_set_id = await _resolve_feature_set_id(db, candidate, drift_report, warnings)
    config_id = await _resolve_config_id(db, feature_set_id, warnings)
    train_start, train_end = await _resolve_train_period(db, drift_report, feature_set_id, warnings)

    base_model_name = candidate.model_name
    if candidate.model_version_id:
        mv = (
            await db.execute(select(ModelVersion).where(ModelVersion.model_version_id == candidate.model_version_id))
        ).scalar_one_or_none()
        if mv:
            base_model_name = mv.model_name

    site_ids = [candidate.site_id] if candidate.site_id else None
    model_name_override = _retrained_model_name(base_model_name)

    candidate.status = "TRAINING"
    candidate.error_message = None
    candidate.updated_at = utc_now()
    await db.flush()

    train_result = await run_training_job(
        db,
        TrainingJobParams(
            config_id=config_id,
            site_ids=site_ids,
            train_start_at=train_start,
            train_end_at=train_end,
            register_model_yn=True,
            triggered_by=f"retraining:{candidate_id}",
            model_name_override=model_name_override,
        ),
    )
    warnings.extend(train_result.get("warnings") or [])

    now = utc_now()
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
        candidate.error_message = None
    else:
        candidate.status = "FAILED"
        candidate.error_message = train_result.get("error_message", "모델 학습 실패")

    await db.commit()
    await db.refresh(candidate)

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
    }
