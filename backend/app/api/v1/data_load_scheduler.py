from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.response import ok
from app.schemas.api import (
    DataLoadScheduleArchiveRequest,
    DataLoadScheduleCreate,
    DataLoadScheduleCronValidateRequest,
    DataLoadSchedulePreviewNextRunRequest,
    DataLoadScheduleRenderParamsRequest,
    DataLoadScheduleRunNowRequest,
    DataLoadScheduleUpdate,
)
from app.services.data_load_scheduler_service import (
    DataLoadSchedulerError,
    activate_schedule,
    archive_schedule,
    create_schedule,
    deactivate_schedule,
    get_schedule,
    get_schedule_run,
    list_due_schedules,
    list_schedule_events,
    list_schedule_runs,
    list_schedules,
    preview_next_run,
    render_runtime_params_preview,
    retry_schedule_run,
    run_due_schedules,
    run_schedule_now,
    update_schedule,
    validate_cron_only,
    validate_schedule,
)

router = APIRouter(tags=["Data Load Scheduler"])


@router.get("/data-load-schedules")
async def get_data_load_schedules(
    active_yn: bool | None = Query(default=None),
    operation_id: str | None = Query(default=None),
    schedule_type: str | None = Query(default=None),
    last_run_status: str | None = Query(default=None),
    keyword: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    items = await list_schedules(
        db,
        active_yn=active_yn,
        operation_id=operation_id,
        schedule_type=schedule_type,
        last_run_status=last_run_status,
        keyword=keyword,
    )
    return ok(items)


@router.post("/data-load-schedules")
async def post_data_load_schedule(body: DataLoadScheduleCreate, db: AsyncSession = Depends(get_db)):
    try:
        item = await create_schedule(db, body.model_dump())
    except DataLoadSchedulerError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ok(item, message="데이터 적재 일정이 등록되었습니다.")


@router.get("/data-load-schedules/due")
async def get_due_data_load_schedules(db: AsyncSession = Depends(get_db)):
    items = await list_due_schedules(db)
    return ok(items)


@router.post("/data-load-schedules/run-due")
async def post_run_due_data_load_schedules(db: AsyncSession = Depends(get_db)):
    try:
        result = await run_due_schedules(db)
    except DataLoadSchedulerError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ok(result, message="실행 대상 일정 처리가 완료되었습니다.")


@router.post("/data-load-schedules/preview-next-run")
async def post_preview_next_run(body: DataLoadSchedulePreviewNextRunRequest, db: AsyncSession = Depends(get_db)):
    try:
        item = await preview_next_run(db, body.model_dump(exclude_unset=True))
    except DataLoadSchedulerError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ok(item)


@router.post("/data-load-schedules/cron/validate")
async def post_cron_validate(body: DataLoadScheduleCronValidateRequest):
    try:
        item = await validate_cron_only(body.model_dump(exclude_unset=True))
    except DataLoadSchedulerError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ok(item)


@router.post("/data-load-schedules/cron/preview")
async def post_cron_preview(body: DataLoadScheduleCronValidateRequest):
    try:
        item = await validate_cron_only(body.model_dump(exclude_unset=True))
    except DataLoadSchedulerError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ok(item)


@router.post("/data-load-schedules/render-runtime-params")
async def post_render_runtime_params(body: DataLoadScheduleRenderParamsRequest, db: AsyncSession = Depends(get_db)):
    try:
        item = await render_runtime_params_preview(db, body.model_dump(exclude_unset=True))
    except DataLoadSchedulerError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ok(item)


@router.get("/data-load-schedules/{schedule_id}")
async def get_data_load_schedule(schedule_id: str, db: AsyncSession = Depends(get_db)):
    item = await get_schedule(db, schedule_id)
    if not item:
        raise HTTPException(status_code=404, detail="NOT_FOUND")
    return ok(item)


@router.put("/data-load-schedules/{schedule_id}")
async def put_data_load_schedule(
    schedule_id: str, body: DataLoadScheduleUpdate, db: AsyncSession = Depends(get_db)
):
    try:
        item = await update_schedule(db, schedule_id, body.model_dump(exclude_unset=True))
    except DataLoadSchedulerError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ok(item, message="데이터 적재 일정이 수정되었습니다.")


@router.post("/data-load-schedules/{schedule_id}/activate")
async def post_activate_schedule(schedule_id: str, db: AsyncSession = Depends(get_db)):
    try:
        item = await activate_schedule(db, schedule_id)
    except DataLoadSchedulerError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ok(item, message="적재 일정이 활성화되었습니다.")


@router.post("/data-load-schedules/{schedule_id}/deactivate")
async def post_deactivate_schedule(schedule_id: str, db: AsyncSession = Depends(get_db)):
    try:
        item = await deactivate_schedule(db, schedule_id)
    except DataLoadSchedulerError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ok(item, message="적재 일정이 비활성화되었습니다.")


@router.post("/data-load-schedules/{schedule_id}/archive")
async def post_archive_schedule(
    schedule_id: str, body: DataLoadScheduleArchiveRequest, db: AsyncSession = Depends(get_db)
):
    try:
        item = await archive_schedule(db, schedule_id, reason=body.archived_reason)
    except DataLoadSchedulerError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ok(item, message="적재 일정이 보관 처리되었습니다.")


@router.post("/data-load-schedules/{schedule_id}/validate")
async def post_validate_schedule(schedule_id: str, db: AsyncSession = Depends(get_db)):
    try:
        item = await validate_schedule(db, schedule_id)
    except DataLoadSchedulerError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ok(item)


@router.post("/data-load-schedules/{schedule_id}/run-now")
async def post_run_schedule_now(
    schedule_id: str, body: DataLoadScheduleRunNowRequest, db: AsyncSession = Depends(get_db)
):
    try:
        item = await run_schedule_now(db, schedule_id, manual_params=body.manual_params)
    except DataLoadSchedulerError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ok(item, message="적재 일정 수동 실행이 완료되었습니다.")


@router.get("/data-load-schedules/{schedule_id}/events")
async def get_schedule_events(
    schedule_id: str,
    limit: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    items = await list_schedule_events(db, schedule_id, limit=limit)
    return ok(items)


@router.get("/data-load-schedule-runs")
async def get_data_load_schedule_runs(
    schedule_id: str | None = Query(default=None),
    run_status: str | None = Query(default=None),
    run_source: str | None = Query(default=None),
    date_from: datetime | None = Query(default=None),
    date_to: datetime | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
):
    items = await list_schedule_runs(
        db,
        schedule_id=schedule_id,
        run_status=run_status,
        run_source=run_source,
        date_from=date_from,
        date_to=date_to,
        limit=limit,
    )
    return ok(items)


@router.get("/data-load-schedule-runs/{schedule_run_id}")
async def get_data_load_schedule_run(schedule_run_id: str, db: AsyncSession = Depends(get_db)):
    item = await get_schedule_run(db, schedule_run_id)
    if not item:
        raise HTTPException(status_code=404, detail="NOT_FOUND")
    return ok(item)


@router.post("/data-load-schedule-runs/{schedule_run_id}/retry")
async def post_retry_schedule_run(schedule_run_id: str, db: AsyncSession = Depends(get_db)):
    try:
        item = await retry_schedule_run(db, schedule_run_id)
    except DataLoadSchedulerError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ok(item, message="적재 실행 재시도가 완료되었습니다.")
