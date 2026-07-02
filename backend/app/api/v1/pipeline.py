from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.response import accepted, ok, paged
from app.models.entities import PipelineRun
from app.schemas.api import PipelineRunStatusUpdate, PipelineTrigger
from app.services.airflow_client import AirflowClientError
from app.services.pipeline_execution_service import attach_pipeline_metadata_to_runs
from app.services.pipeline_service import (
    list_pipelines,
    retry_pipeline,
    run_dict,
    sync_run_from_airflow,
    trigger_pipeline,
    update_pipeline_status,
)

router = APIRouter(tags=["Pipeline"])


@router.get("/pipelines")
async def get_pipelines(db: AsyncSession = Depends(get_db)):
    return ok(await list_pipelines(db))


@router.post("/pipelines/{pipeline_id}/trigger")
async def trigger_pipeline_endpoint(
    pipeline_id: str,
    body: PipelineTrigger,
    db: AsyncSession = Depends(get_db),
):
    try:
        result = await trigger_pipeline(db, pipeline_id, body.parameters, body.business_date)
    except ValueError as exc:
        if str(exc) == "NOT_FOUND":
            raise HTTPException(status_code=404, detail="NOT_FOUND") from exc
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if result.get("status") == "FAILED":
        return accepted(result, message=result.get("error_message", "Airflow 트리거 실패"))
    return accepted(result, message="파이프라인이 Airflow에 실행 요청되었습니다.")


@router.get("/pipeline-runs")
async def list_pipeline_runs(
    pipeline_type: str | None = Query(default=None),
    run_status: str | None = Query(default=None),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=200),
    sync_airflow: bool = Query(default=True),
    db: AsyncSession = Depends(get_db),
):
    q = select(PipelineRun).order_by(PipelineRun.started_at.desc())
    if pipeline_type:
        q = q.where(PipelineRun.pipeline_type == pipeline_type)
    if run_status:
        q = q.where(PipelineRun.run_status == run_status)
    rows = list((await db.execute(q)).scalars().all())

    items = []
    for r in rows:
        warning = None
        if sync_airflow and r.run_status in ("QUEUED", "RUNNING"):
            warning = await sync_run_from_airflow(db, r)
        items.append(run_dict(r, warning))

    items = await attach_pipeline_metadata_to_runs(db, items)
    start = (page - 1) * size
    return paged(items[start:start + size], page, size, len(items))


@router.get("/pipeline-runs/{run_id}")
async def get_pipeline_run(
    run_id: str,
    sync_airflow: bool = Query(default=True),
    db: AsyncSession = Depends(get_db),
):
    r = (await db.execute(select(PipelineRun).where(PipelineRun.pipeline_run_id == run_id))).scalar_one_or_none()
    if not r:
        raise HTTPException(status_code=404, detail="NOT_FOUND")
    warning = None
    if sync_airflow and r.run_status in ("QUEUED", "RUNNING"):
        warning = await sync_run_from_airflow(db, r)
    data = run_dict(r, warning)
    enriched = await attach_pipeline_metadata_to_runs(db, [data])
    return ok(enriched[0] if enriched else data)


@router.post("/pipeline-runs/{run_id}/status")
async def update_pipeline_run_status(
    run_id: str,
    body: PipelineRunStatusUpdate,
    db: AsyncSession = Depends(get_db),
):
    try:
        result = await update_pipeline_status(
            db,
            run_id,
            body.status,
            body.step_name,
            body.message,
            body.result_summary,
        )
    except ValueError as exc:
        if str(exc) == "NOT_FOUND":
            raise HTTPException(status_code=404, detail="NOT_FOUND") from exc
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ok(result, message="파이프라인 상태가 갱신되었습니다.")


@router.post("/pipeline-runs/{run_id}/retry")
async def retry_pipeline_run(run_id: str, db: AsyncSession = Depends(get_db)):
    try:
        result = await retry_pipeline(db, run_id)
    except ValueError as exc:
        if str(exc) == "NOT_FOUND":
            raise HTTPException(status_code=404, detail="NOT_FOUND") from exc
        if str(exc) == "CONFLICT":
            raise HTTPException(status_code=409, detail="CONFLICT") from exc
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if result.get("status") == "FAILED":
        return accepted(result, message=result.get("error_message", "재시도 실패"))
    return accepted(result, message="파이프라인 재시도가 Airflow에 요청되었습니다.")
