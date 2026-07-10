"""R10-S10 Run Due Worker API."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.response import ok
from app.schemas.api import RunDueWorkerMarkStaleRequest, RunDueWorkerRunOnceRequest
from app.services.run_due_worker_lock_service import list_locks
from app.services.run_due_worker_service import (
    RunDueWorkerError,
    WorkerConfig,
    get_worker_instance,
    get_worker_run,
    get_worker_summary,
    list_worker_instances,
    list_worker_runs,
    mark_stale_workers,
    run_once_via_api,
)

router = APIRouter(tags=["Run Due Worker"])


@router.get("/run-due-worker/summary")
async def get_run_due_worker_summary(db: AsyncSession = Depends(get_db)):
    return ok(await get_worker_summary(db))


@router.get("/run-due-worker/instances")
async def get_run_due_worker_instances(db: AsyncSession = Depends(get_db)):
    return ok(await list_worker_instances(db))


@router.get("/run-due-worker/instances/{worker_instance_id}")
async def get_run_due_worker_instance(worker_instance_id: str, db: AsyncSession = Depends(get_db)):
    item = await get_worker_instance(db, worker_instance_id)
    if not item:
        raise HTTPException(status_code=404, detail="NOT_FOUND")
    return ok(item)


@router.get("/run-due-worker/runs")
async def get_run_due_worker_runs(
    worker_instance_id: str | None = Query(default=None),
    run_status: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
):
    return ok(
        await list_worker_runs(
            db,
            worker_instance_id=worker_instance_id,
            run_status=run_status,
            limit=limit,
        )
    )


@router.get("/run-due-worker/runs/{worker_run_id}")
async def get_run_due_worker_run(worker_run_id: str, db: AsyncSession = Depends(get_db)):
    item = await get_worker_run(db, worker_run_id)
    if not item:
        raise HTTPException(status_code=404, detail="NOT_FOUND")
    return ok(item)


@router.get("/run-due-worker/locks")
async def get_run_due_worker_locks(db: AsyncSession = Depends(get_db)):
    return ok(await list_locks(db))


@router.post("/run-due-worker/run-once")
async def post_run_due_worker_once(body: RunDueWorkerRunOnceRequest, db: AsyncSession = Depends(get_db)):
    try:
        item = await run_once_via_api(
            db,
            worker_name=body.worker_name,
            max_batch_size=body.max_batch_size,
        )
    except RunDueWorkerError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ok(item, message="Worker 1회 실행이 완료되었습니다.")


@router.post("/run-due-worker/mark-stale")
async def post_mark_stale_workers(body: RunDueWorkerMarkStaleRequest, db: AsyncSession = Depends(get_db)):
    cfg = WorkerConfig.from_settings()
    marked = await mark_stale_workers(
        db,
        lock_ttl_seconds=body.lock_ttl_seconds,
        config=cfg,
    )
    return ok(marked, message=f"STALE 처리 {len(marked)}건")
