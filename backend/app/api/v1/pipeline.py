from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.response import accepted, ok, paged
from app.models.entities import PipelineRun
from app.schemas.api import PipelineTrigger

router = APIRouter(tags=["Pipeline"])

PIPELINES = [
    {"pipeline_id": "data_ingestion_dag", "name": "data_ingestion_dag", "type": "INGESTION"},
    {"pipeline_id": "feature_build_dag", "name": "feature_build_dag", "type": "FEATURE"},
    {"pipeline_id": "model_training_dag", "name": "model_training_dag", "type": "TRAINING"},
    {"pipeline_id": "batch_prediction_dag", "name": "batch_prediction_dag", "type": "PREDICTION"},
    {"pipeline_id": "monitoring_dag", "name": "monitoring_dag", "type": "MONITORING"},
]


@router.get("/pipelines")
async def list_pipelines():
    return ok(PIPELINES)


@router.post("/pipelines/{pipeline_id}/trigger")
async def trigger_pipeline(pipeline_id: str, body: PipelineTrigger, db: AsyncSession = Depends(get_db)):
    if not any(p["pipeline_id"] == pipeline_id for p in PIPELINES):
        raise HTTPException(status_code=404, detail="NOT_FOUND")

    run_id = f"AIRFLOW-RUN-{uuid4().hex[:6].upper()}"
    ptype = next(p["type"] for p in PIPELINES if p["pipeline_id"] == pipeline_id)
    now = datetime.now(timezone.utc)

    run = PipelineRun(
        pipeline_run_id=run_id,
        pipeline_id=pipeline_id,
        pipeline_name=pipeline_id,
        pipeline_type=ptype,
        orchestrator="AIRFLOW",
        run_status="RUNNING",
        started_at=now,
        message=f"수동 실행: business_date={body.business_date}",
    )
    db.add(run)
    return accepted({"pipeline_run_id": run_id, "status": "RUNNING"}, message="파이프라인이 실행 요청되었습니다.")


@router.get("/pipeline-runs")
async def list_pipeline_runs(
    pipeline_type: str | None = Query(default=None),
    run_status: str | None = Query(default=None),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    q = select(PipelineRun).order_by(PipelineRun.started_at.desc())
    if pipeline_type:
        q = q.where(PipelineRun.pipeline_type == pipeline_type)
    if run_status:
        q = q.where(PipelineRun.run_status == run_status)
    rows = (await db.execute(q)).scalars().all()
    items = [_run_dict(r) for r in rows]
    start = (page - 1) * size
    return paged(items[start:start + size], page, size, len(items))


@router.get("/pipeline-runs/{run_id}")
async def get_pipeline_run(run_id: str, db: AsyncSession = Depends(get_db)):
    r = (await db.execute(select(PipelineRun).where(PipelineRun.pipeline_run_id == run_id))).scalar_one_or_none()
    if not r:
        raise HTTPException(status_code=404, detail="NOT_FOUND")
    return ok(_run_dict(r))


@router.post("/pipeline-runs/{run_id}/retry")
async def retry_pipeline_run(run_id: str, db: AsyncSession = Depends(get_db)):
    r = (await db.execute(select(PipelineRun).where(PipelineRun.pipeline_run_id == run_id))).scalar_one_or_none()
    if not r:
        raise HTTPException(status_code=404, detail="NOT_FOUND")
    if r.run_status != "FAILED":
        raise HTTPException(status_code=409, detail="CONFLICT")

    new_id = f"AIRFLOW-RUN-{uuid4().hex[:6].upper()}"
    now = datetime.now(timezone.utc)
    new_run = PipelineRun(
        pipeline_run_id=new_id,
        pipeline_id=r.pipeline_id,
        pipeline_name=r.pipeline_name,
        pipeline_type=r.pipeline_type,
        orchestrator="AIRFLOW",
        run_status="RUNNING",
        started_at=now,
        message=f"재시도 (원본: {run_id})",
    )
    db.add(new_run)
    return accepted({"pipeline_run_id": new_id, "status": "RUNNING", "original_run_id": run_id}, message="파이프라인 재시도가 요청되었습니다.")


def _run_dict(r: PipelineRun) -> dict:
    duration = None
    if r.finished_at and r.started_at:
        duration = int((r.finished_at - r.started_at).total_seconds() / 60)
    return {
        "pipeline_run_id": r.pipeline_run_id,
        "pipeline_id": r.pipeline_id,
        "pipeline_name": r.pipeline_name,
        "pipeline_type": r.pipeline_type,
        "run_status": r.run_status,
        "orchestrator_run_id": r.orchestrator_run_id,
        "started_at": r.started_at.isoformat(),
        "finished_at": r.finished_at.isoformat() if r.finished_at else None,
        "duration_minutes": duration,
        "message": r.message,
    }
