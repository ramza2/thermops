"""파이프라인 트리거·상태 동기화 서비스."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entities import PipelineRun
from app.services.airflow_client import AirflowClient, AirflowClientError, map_airflow_state

PIPELINE_DEFINITIONS: list[dict[str, Any]] = [
    {
        "pipeline_id": "data_ingestion_dag",
        "name": "data_ingestion_dag",
        "type": "INGESTION",
        "description": "CSV/DB 데이터 적재",
        "schedule": "0 * * * *",
    },
    {
        "pipeline_id": "data_quality_dag",
        "name": "data_quality_dag",
        "type": "INGESTION",
        "description": "데이터 품질 점검",
        "schedule": None,
    },
    {
        "pipeline_id": "feature_build_dag",
        "name": "feature_build_dag",
        "type": "FEATURE",
        "description": "Feature 생성",
        "schedule": None,
    },
    {
        "pipeline_id": "model_training_dag",
        "name": "model_training_dag",
        "type": "TRAINING",
        "description": "모델 학습 및 MLflow 등록",
        "schedule": None,
    },
    {
        "pipeline_id": "batch_prediction_dag",
        "name": "batch_prediction_dag",
        "type": "PREDICTION",
        "description": "배치 예측 실행",
        "schedule": "0 5 * * *",
    },
    {
        "pipeline_id": "monitoring_dag",
        "name": "monitoring_dag",
        "type": "MONITORING",
        "description": "예측-실제 매칭 및 성능 평가",
        "schedule": "0 8 * * *",
    },
    {
        "pipeline_id": "drift_detection_dag",
        "name": "drift_detection_dag",
        "type": "MONITORING",
        "description": "Drift 감지 및 재학습 후보 자동 생성",
        "schedule": "0 9 * * *",
    },
    {
        "pipeline_id": "retraining_dag",
        "name": "retraining_dag",
        "type": "TRAINING",
        "description": "승인된 재학습 후보 기반 모델 재학습 (conf에 candidate_id 필수)",
        "schedule": None,
    },
    {
        "pipeline_id": "thermops_full_pipeline_dag",
        "name": "thermops_full_pipeline_dag",
        "type": "INGESTION",
        "description": "전체 파이프라인 (적재→품질→Feature→학습→예측→평가)",
        "schedule": None,
    },
]

PIPELINE_IDS = {p["pipeline_id"] for p in PIPELINE_DEFINITIONS}

DEFAULT_CONF_BY_PIPELINE: dict[str, dict[str, Any]] = {
    "data_ingestion_dag": {
        "load_mode": "UPSERT",
    },
    "data_quality_dag": {},
    "feature_build_dag": {},
    "model_training_dag": {
        "register_model_yn": True,
    },
    "batch_prediction_dag": {
        "overwrite_yn": True,
    },
    "monitoring_dag": {},
    "drift_detection_dag": {},
    "retraining_dag": {
        "candidate_id": None,
    },
    "thermops_full_pipeline_dag": {},
}


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _default_date_range(days: int = 7) -> tuple[str, str]:
    end = datetime.now(timezone.utc).date()
    start = end - timedelta(days=days)
    return start.isoformat(), end.isoformat()


def build_dag_conf(
    pipeline_id: str,
    pipeline_run_id: str,
    parameters: dict[str, Any] | None,
    business_date: str | None,
) -> tuple[dict[str, Any], list[str]]:
    warnings: list[str] = []
    conf = deepcopy(DEFAULT_CONF_BY_PIPELINE.get(pipeline_id, {}))
    if parameters:
        conf.update(parameters)
    conf["pipeline_run_id"] = pipeline_run_id
    if business_date:
        conf["business_date"] = business_date

    start_at, end_at = _default_date_range(7)
    if business_date:
        end_at = business_date
        start_dt = datetime.fromisoformat(business_date) - timedelta(days=7)
        start_at = start_dt.date().isoformat()
    conf.setdefault("start_at", start_at)
    conf.setdefault("end_at", end_at)

    if not parameters and pipeline_id in DEFAULT_CONF_BY_PIPELINE:
        warnings.append("default conf used")

    return conf, warnings


def _merge_result_summary(existing: dict | None, incoming: dict | None) -> dict | None:
    if not incoming:
        return existing
    base = dict(existing or {})
    base.update(incoming)
    return base


def run_dict(r: PipelineRun, sync_warning: str | None = None) -> dict:
    duration = None
    if r.finished_at and r.started_at:
        duration = int((r.finished_at - r.started_at).total_seconds() / 60)
    data = {
        "pipeline_run_id": r.pipeline_run_id,
        "pipeline_id": r.pipeline_id,
        "pipeline_name": r.pipeline_name,
        "pipeline_type": r.pipeline_type,
        "run_status": r.run_status,
        "orchestrator": r.orchestrator,
        "orchestrator_run_id": r.orchestrator_run_id,
        "started_at": r.started_at.isoformat(),
        "finished_at": r.finished_at.isoformat() if r.finished_at else None,
        "duration_minutes": duration,
        "message": r.message,
        "result_summary": r.result_summary,
    }
    if sync_warning:
        data["sync_warning"] = sync_warning
    return data


async def list_pipelines(db: AsyncSession) -> list[dict[str, Any]]:
    client = AirflowClient()
    airflow_dags: dict[str, dict] = {}
    source = "static"
    try:
        for dag in await client.list_dags(limit=200):
            dag_id = dag.get("dag_id")
            if dag_id:
                airflow_dags[dag_id] = dag
        source = "airflow"
    except AirflowClientError:
        source = "static_fallback"

    latest_by_pipeline: dict[str, PipelineRun] = {}
    rows = (await db.execute(select(PipelineRun).order_by(PipelineRun.started_at.desc()))).scalars().all()
    for row in rows:
        if row.pipeline_id not in latest_by_pipeline:
            latest_by_pipeline[row.pipeline_id] = row

    items = []
    for p in PIPELINE_DEFINITIONS:
        pid = p["pipeline_id"]
        dag_meta = airflow_dags.get(pid, {})
        last = latest_by_pipeline.get(pid)
        items.append({
            **p,
            "is_paused": dag_meta.get("is_paused"),
            "last_run_status": last.run_status if last else None,
            "last_run_at": last.started_at.isoformat() if last else None,
            "source": source,
        })
    return items


async def sync_run_from_airflow(db: AsyncSession, run: PipelineRun) -> str | None:
    if run.orchestrator != "AIRFLOW" or not run.orchestrator_run_id:
        return None
    client = AirflowClient()
    try:
        dag_run = await client.get_dag_run(run.pipeline_id, run.orchestrator_run_id)
    except AirflowClientError as exc:
        return str(exc)

    mapped = map_airflow_state(dag_run.get("state"))
    if mapped:
        run.run_status = mapped
        if mapped in ("QUEUED", "RUNNING"):
            run.finished_at = None
        elif mapped in ("SUCCESS", "FAILED"):
            end_date = dag_run.get("end_date")
            if end_date:
                try:
                    run.finished_at = datetime.fromisoformat(end_date.replace("Z", "+00:00")).replace(tzinfo=None)
                except ValueError:
                    run.finished_at = run.finished_at or _utc_now()
            else:
                run.finished_at = run.finished_at or _utc_now()

    airflow_state = dag_run.get("state")
    if mapped == "FAILED":
        run.message = run.message or f"Airflow DAG 실행 실패 (state={airflow_state})"
        run.result_summary = _merge_result_summary(run.result_summary, {
            "airflow_state": airflow_state,
            "sync_source": "airflow",
        })
    elif mapped == "SUCCESS":
        run.result_summary = _merge_result_summary(run.result_summary, {
            "airflow_state": airflow_state,
            "sync_source": "airflow",
        })
    return None


async def trigger_pipeline(
    db: AsyncSession,
    pipeline_id: str,
    parameters: dict[str, Any] | None,
    business_date: str | None,
) -> dict[str, Any]:
    if pipeline_id not in PIPELINE_IDS:
        raise ValueError("NOT_FOUND")

    run_id = f"AIRFLOW-RUN-{uuid4().hex[:6].upper()}"
    ptype = next(p["type"] for p in PIPELINE_DEFINITIONS if p["pipeline_id"] == pipeline_id)
    now = _utc_now()
    conf, warnings = build_dag_conf(pipeline_id, run_id, parameters, business_date)
    result_summary: dict[str, Any] = {"run_source": "DIRECT_DAG"}
    if warnings:
        result_summary["warnings"] = warnings

    run = PipelineRun(
        pipeline_run_id=run_id,
        pipeline_id=pipeline_id,
        pipeline_name=pipeline_id,
        pipeline_type=ptype,
        orchestrator="AIRFLOW",
        run_status="QUEUED",
        started_at=now,
        message=f"Airflow 트리거 요청: business_date={business_date or 'N/A'}",
        result_summary=result_summary or None,
    )
    db.add(run)
    await db.flush()

    client = AirflowClient()
    try:
        dag_run = await client.trigger_dag(pipeline_id, conf)
    except AirflowClientError as exc:
        run.run_status = "FAILED"
        run.finished_at = _utc_now()
        run.message = f"Airflow 트리거 실패: {exc}"
        run.result_summary = _merge_result_summary(run.result_summary, {"error_message": str(exc)})
        return {
            "pipeline_run_id": run_id,
            "orchestrator_run_id": None,
            "status": run.run_status,
            "error_message": str(exc),
        }

    dag_run_id = dag_run.get("dag_run_id")
    run.orchestrator_run_id = dag_run_id
    run.run_status = map_airflow_state(dag_run.get("state")) or "QUEUED"
    run.message = f"Airflow DAG 트리거 완료 (dag_run_id={dag_run_id})"
    run.result_summary = _merge_result_summary(run.result_summary, {"conf": conf, "business_date": business_date})
    return {
        "pipeline_run_id": run_id,
        "orchestrator_run_id": dag_run_id,
        "dag_run_id": dag_run_id,
        "status": run.run_status,
        "conf": conf,
    }


async def retry_pipeline(db: AsyncSession, run_id: str) -> dict[str, Any]:
    r = (await db.execute(select(PipelineRun).where(PipelineRun.pipeline_run_id == run_id))).scalar_one_or_none()
    if not r:
        raise ValueError("NOT_FOUND")
    if r.run_status != "FAILED":
        raise ValueError("CONFLICT")

    params = (r.result_summary or {}).get("conf") if isinstance(r.result_summary, dict) else None
    business_date = (r.result_summary or {}).get("business_date") if isinstance(r.result_summary, dict) else None
    result = await trigger_pipeline(db, r.pipeline_id, params, business_date)
    result["original_run_id"] = run_id
    return result


async def update_pipeline_status(
    db: AsyncSession,
    run_id: str,
    status: str,
    step_name: str | None,
    message: str | None,
    result_summary: dict | None,
) -> dict:
    # TODO: 내부 API service token 인증 적용
    r = (await db.execute(select(PipelineRun).where(PipelineRun.pipeline_run_id == run_id))).scalar_one_or_none()
    if not r:
        raise ValueError("NOT_FOUND")

    r.run_status = status
    if message:
        r.message = message
    elif step_name:
        r.message = f"{step_name}: {status}"
    r.result_summary = _merge_result_summary(r.result_summary, result_summary)
    if step_name and r.result_summary is not None:
        steps = dict(r.result_summary.get("steps") or {})
        steps[step_name] = {"status": status, **(result_summary or {})}
        r.result_summary["steps"] = steps

    if status == "RUNNING":
        r.finished_at = None
    elif status in ("SUCCESS", "FAILED"):
        r.finished_at = r.finished_at or _utc_now()
    return run_dict(r)
