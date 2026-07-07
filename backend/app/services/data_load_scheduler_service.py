"""데이터 적재 스케줄러 서비스 (R10-S6)."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.time import utc_now
from app.models.entities import (
    ApiConnectorOperation,
    DataLoadSchedule,
    DataLoadScheduleEvent,
    DataLoadScheduleRun,
)
from app.services.api_connector_service import ApiConnectorError, _get_operation, load_preview, run_load
from app.services.runtime_param_template_service import mask_runtime_params, resolve_runtime_params
from app.services.schedule_time_service import compute_next_run_at, is_schedule_due


class DataLoadSchedulerError(ValueError):
    def __init__(self, message: str, *, error_code: str = "SCHEDULER_ERROR"):
        self.error_code = error_code
        super().__init__(message)


def _new_id(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex[:8].upper()}"


def _dt_iso(val: datetime | None) -> str | None:
    return val.isoformat() if val else None


def _schedule_dict(row: DataLoadSchedule, *, operation_name: str | None = None) -> dict[str, Any]:
    return {
        "schedule_id": row.schedule_id,
        "schedule_name": row.schedule_name,
        "schedule_description": row.schedule_description,
        "operation_id": row.operation_id,
        "operation_name": operation_name,
        "data_source_id": row.data_source_id,
        "schedule_type": row.schedule_type,
        "cron_expression": row.cron_expression,
        "timezone": row.timezone,
        "start_at": _dt_iso(row.start_at),
        "end_at": _dt_iso(row.end_at),
        "active_yn": bool(row.active_yn),
        "run_policy": row.run_policy,
        "load_window_type": row.load_window_type,
        "window_offset_minutes": row.window_offset_minutes,
        "runtime_params_template": row.runtime_params_template,
        "max_pages_override": row.max_pages_override,
        "retry_enabled_yn": bool(row.retry_enabled_yn),
        "max_retry_count": row.max_retry_count,
        "retry_interval_minutes": row.retry_interval_minutes,
        "on_failure_policy": row.on_failure_policy,
        "last_run_at": _dt_iso(row.last_run_at),
        "last_success_at": _dt_iso(row.last_success_at),
        "last_failure_at": _dt_iso(row.last_failure_at),
        "next_run_at": _dt_iso(row.next_run_at),
        "last_run_status": row.last_run_status,
        "created_at": _dt_iso(row.created_at),
        "updated_at": _dt_iso(row.updated_at),
        "metadata_json": row.metadata_json,
    }


def _run_dict(row: DataLoadScheduleRun, *, schedule_name: str | None = None) -> dict[str, Any]:
    return {
        "schedule_run_id": row.schedule_run_id,
        "schedule_id": row.schedule_id,
        "schedule_name": schedule_name,
        "operation_id": row.operation_id,
        "api_load_run_id": row.api_load_run_id,
        "run_source": row.run_source,
        "scheduled_for": _dt_iso(row.scheduled_for),
        "started_at": _dt_iso(row.started_at),
        "finished_at": _dt_iso(row.finished_at),
        "run_status": row.run_status,
        "attempt_no": row.attempt_no,
        "parent_schedule_run_id": row.parent_schedule_run_id,
        "runtime_params_masked": row.runtime_params_masked,
        "request_summary": row.request_summary,
        "result_summary": row.result_summary,
        "inserted_count": row.inserted_count,
        "updated_count": row.updated_count,
        "skipped_count": row.skipped_count,
        "error_count": row.error_count,
        "error_message": row.error_message,
        "created_at": _dt_iso(row.created_at),
        "metadata_json": row.metadata_json,
    }


def _event_dict(row: DataLoadScheduleEvent) -> dict[str, Any]:
    return {
        "event_id": row.event_id,
        "schedule_id": row.schedule_id,
        "schedule_run_id": row.schedule_run_id,
        "event_type": row.event_type,
        "event_message": row.event_message,
        "event_payload_json": row.event_payload_json,
        "created_at": _dt_iso(row.created_at),
    }


async def _record_event(
    db: AsyncSession,
    *,
    schedule_id: str,
    event_type: str,
    event_message: str,
    schedule_run_id: str | None = None,
    payload: dict[str, Any] | None = None,
) -> None:
    db.add(
        DataLoadScheduleEvent(
            event_id=_new_id("DLE"),
            schedule_id=schedule_id,
            schedule_run_id=schedule_run_id,
            event_type=event_type,
            event_message=event_message,
            event_payload_json=payload,
            created_at=utc_now(),
        )
    )


async def _get_operation_name(db: AsyncSession, operation_id: str) -> str | None:
    row = (
        await db.execute(
            select(ApiConnectorOperation.operation_name).where(
                ApiConnectorOperation.operation_id == operation_id
            )
        )
    ).scalar_one_or_none()
    return row


async def list_schedules(
    db: AsyncSession,
    *,
    active_yn: bool | None = None,
    operation_id: str | None = None,
    schedule_type: str | None = None,
    last_run_status: str | None = None,
    keyword: str | None = None,
) -> list[dict[str, Any]]:
    q = select(DataLoadSchedule).order_by(DataLoadSchedule.created_at.desc())
    if active_yn is not None:
        q = q.where(DataLoadSchedule.active_yn.is_(active_yn))
    if operation_id:
        q = q.where(DataLoadSchedule.operation_id == operation_id)
    if schedule_type:
        q = q.where(DataLoadSchedule.schedule_type == schedule_type)
    if last_run_status:
        q = q.where(DataLoadSchedule.last_run_status == last_run_status)
    if keyword:
        like = f"%{keyword}%"
        q = q.where(
            or_(
                DataLoadSchedule.schedule_name.ilike(like),
                DataLoadSchedule.schedule_description.ilike(like),
            )
        )
    rows = (await db.execute(q)).scalars().all()
    out: list[dict[str, Any]] = []
    for row in rows:
        op_name = await _get_operation_name(db, row.operation_id)
        out.append(_schedule_dict(row, operation_name=op_name))
    return out


async def get_schedule(db: AsyncSession, schedule_id: str) -> dict[str, Any] | None:
    row = (
        await db.execute(select(DataLoadSchedule).where(DataLoadSchedule.schedule_id == schedule_id))
    ).scalar_one_or_none()
    if not row:
        return None
    op_name = await _get_operation_name(db, row.operation_id)
    return _schedule_dict(row, operation_name=op_name)


async def create_schedule(db: AsyncSession, payload: dict[str, Any]) -> dict[str, Any]:
    operation_id = payload.get("operation_id")
    if not operation_id:
        raise DataLoadSchedulerError("API 작업(operation_id)이 필요합니다.", error_code="MISSING_OPERATION")
    op = await _get_operation(db, operation_id)
    now = utc_now()
    schedule_type = str(payload.get("schedule_type") or "MANUAL").upper()
    row = DataLoadSchedule(
        schedule_id=_new_id("DLS"),
        schedule_name=payload["schedule_name"],
        schedule_description=payload.get("schedule_description"),
        operation_id=operation_id,
        data_source_id=op.data_source_id,
        schedule_type=schedule_type,
        cron_expression=payload.get("cron_expression"),
        timezone=payload.get("timezone") or "Asia/Seoul",
        start_at=payload.get("start_at"),
        end_at=payload.get("end_at"),
        active_yn=bool(payload.get("active_yn", True)),
        run_policy=payload.get("run_policy") or "LOAD_RUN",
        load_window_type=payload.get("load_window_type") or "NONE",
        window_offset_minutes=payload.get("window_offset_minutes"),
        runtime_params_template=payload.get("runtime_params_template"),
        max_pages_override=payload.get("max_pages_override"),
        retry_enabled_yn=bool(payload.get("retry_enabled_yn", False)),
        max_retry_count=int(payload.get("max_retry_count") or 0),
        retry_interval_minutes=int(payload.get("retry_interval_minutes") or 10),
        on_failure_policy=payload.get("on_failure_policy") or "STOP",
        created_at=now,
        updated_at=now,
        metadata_json=payload.get("metadata_json"),
    )
    sched_dict = _schedule_dict(row)
    row.next_run_at = compute_next_run_at(sched_dict, from_time=now)
    db.add(row)
    await _record_event(db, schedule_id=row.schedule_id, event_type="CREATED", event_message="적재 일정이 등록되었습니다.")
    await db.flush()
    return await get_schedule(db, row.schedule_id)


async def update_schedule(db: AsyncSession, schedule_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    row = (
        await db.execute(select(DataLoadSchedule).where(DataLoadSchedule.schedule_id == schedule_id))
    ).scalar_one_or_none()
    if not row:
        raise DataLoadSchedulerError("적재 일정을 찾을 수 없습니다.", error_code="NOT_FOUND")
    for key in (
        "schedule_name",
        "schedule_description",
        "schedule_type",
        "cron_expression",
        "timezone",
        "start_at",
        "end_at",
        "active_yn",
        "run_policy",
        "load_window_type",
        "window_offset_minutes",
        "runtime_params_template",
        "max_pages_override",
        "retry_enabled_yn",
        "max_retry_count",
        "retry_interval_minutes",
        "on_failure_policy",
        "metadata_json",
    ):
        if key in payload and payload[key] is not None:
            setattr(row, key, payload[key])
    if payload.get("operation_id"):
        op = await _get_operation(db, payload["operation_id"])
        row.operation_id = op.operation_id
        row.data_source_id = op.data_source_id
    row.updated_at = utc_now()
    row.next_run_at = compute_next_run_at(_schedule_dict(row), from_time=utc_now())
    await _record_event(db, schedule_id=schedule_id, event_type="UPDATED", event_message="적재 일정이 수정되었습니다.")
    await db.flush()
    return await get_schedule(db, schedule_id)


async def activate_schedule(db: AsyncSession, schedule_id: str) -> dict[str, Any]:
    row = (
        await db.execute(select(DataLoadSchedule).where(DataLoadSchedule.schedule_id == schedule_id))
    ).scalar_one_or_none()
    if not row:
        raise DataLoadSchedulerError("적재 일정을 찾을 수 없습니다.", error_code="NOT_FOUND")
    row.active_yn = True
    row.updated_at = utc_now()
    row.next_run_at = compute_next_run_at(_schedule_dict(row), from_time=utc_now())
    await _record_event(db, schedule_id=schedule_id, event_type="ACTIVATED", event_message="적재 일정이 활성화되었습니다.")
    await db.flush()
    return await get_schedule(db, schedule_id)


async def deactivate_schedule(db: AsyncSession, schedule_id: str) -> dict[str, Any]:
    row = (
        await db.execute(select(DataLoadSchedule).where(DataLoadSchedule.schedule_id == schedule_id))
    ).scalar_one_or_none()
    if not row:
        raise DataLoadSchedulerError("적재 일정을 찾을 수 없습니다.", error_code="NOT_FOUND")
    row.active_yn = False
    row.updated_at = utc_now()
    await _record_event(db, schedule_id=schedule_id, event_type="DEACTIVATED", event_message="적재 일정이 비활성화되었습니다.")
    await db.flush()
    return await get_schedule(db, schedule_id)


async def archive_schedule(db: AsyncSession, schedule_id: str, *, reason: str | None = None) -> dict[str, Any]:
    row = (
        await db.execute(select(DataLoadSchedule).where(DataLoadSchedule.schedule_id == schedule_id))
    ).scalar_one_or_none()
    if not row:
        raise DataLoadSchedulerError("적재 일정을 찾을 수 없습니다.", error_code="NOT_FOUND")
    row.active_yn = False
    meta = dict(row.metadata_json or {})
    meta["archived_at"] = utc_now().isoformat()
    if reason:
        meta["archived_reason"] = reason
    row.metadata_json = meta
    row.updated_at = utc_now()
    await _record_event(
        db,
        schedule_id=schedule_id,
        event_type="DEACTIVATED",
        event_message="적재 일정이 보관(비활성) 처리되었습니다.",
        payload={"archived": True, "reason": reason},
    )
    await db.flush()
    return await get_schedule(db, schedule_id)


async def preview_next_run(db: AsyncSession, payload: dict[str, Any]) -> dict[str, Any]:
    sched = payload
    if payload.get("schedule_id"):
        existing = await get_schedule(db, payload["schedule_id"])
        if not existing:
            raise DataLoadSchedulerError("적재 일정을 찾을 수 없습니다.", error_code="NOT_FOUND")
        sched = {**existing, **{k: v for k, v in payload.items() if v is not None}}
    now = utc_now()
    next_at = compute_next_run_at(sched, from_time=now)
    warnings: list[str] = []
    if str(sched.get("schedule_type", "")).upper() == "CRON":
        warnings.append("CRON 유형은 R10-S6에서 next_run_at 자동 계산을 지원하지 않습니다.")
    return {
        "schedule_type": sched.get("schedule_type"),
        "timezone": sched.get("timezone") or "Asia/Seoul",
        "from_time": now.isoformat(),
        "next_run_at": next_at.isoformat() if next_at else None,
        "warnings": warnings,
    }


async def render_runtime_params_preview(db: AsyncSession, payload: dict[str, Any]) -> dict[str, Any]:
    schedule_id = payload.get("schedule_id")
    sched = payload
    if schedule_id:
        existing = await get_schedule(db, schedule_id)
        if not existing:
            raise DataLoadSchedulerError("적재 일정을 찾을 수 없습니다.", error_code="NOT_FOUND")
        sched = existing
    now = utc_now()
    last_success = sched.get("last_success_at")
    if isinstance(last_success, str):
        last_success = datetime.fromisoformat(last_success.replace("Z", ""))
    start_at = sched.get("start_at")
    if isinstance(start_at, str):
        start_at = datetime.fromisoformat(start_at.replace("Z", ""))
    params = resolve_runtime_params(
        sched.get("runtime_params_template"),
        now=now,
        last_success_at=last_success,
        start_at=start_at,
        load_window_type=sched.get("load_window_type") or "NONE",
        window_offset_minutes=sched.get("window_offset_minutes"),
        manual_params=payload.get("manual_params"),
    )
    return {
        "runtime_params": params,
        "runtime_params_masked": mask_runtime_params(params),
    }


async def validate_schedule(db: AsyncSession, schedule_id: str) -> dict[str, Any]:
    sched = await get_schedule(db, schedule_id)
    if not sched:
        raise DataLoadSchedulerError("적재 일정을 찾을 수 없습니다.", error_code="NOT_FOUND")
    warnings: list[str] = []
    errors: list[str] = []
    try:
        op = await _get_operation(db, sched["operation_id"])
        if not op.target_table and sched.get("run_policy") == "LOAD_RUN":
            errors.append("API 작업에 적재 대상 테이블이 설정되지 않았습니다.")
    except ApiConnectorError as exc:
        errors.append(str(exc))
    if str(sched.get("schedule_type")).upper() == "CRON":
        warnings.append("CRON 유형은 due 자동 실행 대상에서 제외됩니다.")
    if str(sched.get("schedule_type")).upper() == "MANUAL":
        warnings.append("MANUAL 유형은 run-due 자동 실행 대상이 아닙니다.")
    return {"valid": not errors, "errors": errors, "warnings": warnings}


async def list_due_schedules(db: AsyncSession, *, now: datetime | None = None) -> list[dict[str, Any]]:
    ref = now or utc_now()
    schedules = await list_schedules(db, active_yn=True)
    return [s for s in schedules if is_schedule_due(s, ref)]


async def _execute_schedule_run(
    db: AsyncSession,
    schedule: DataLoadSchedule,
    *,
    run_source: str,
    scheduled_for: datetime | None,
    manual_params: dict[str, Any] | None = None,
    attempt_no: int = 1,
    parent_schedule_run_id: str | None = None,
) -> dict[str, Any]:
    now = utc_now()
    sched_dict = _schedule_dict(schedule)
    runtime = resolve_runtime_params(
        schedule.runtime_params_template,
        now=now,
        last_success_at=schedule.last_success_at,
        start_at=schedule.start_at,
        load_window_type=schedule.load_window_type or "NONE",
        window_offset_minutes=schedule.window_offset_minutes,
        manual_params=manual_params,
    )
    masked = mask_runtime_params(runtime)
    run_id = _new_id("DLR")
    run_row = DataLoadScheduleRun(
        schedule_run_id=run_id,
        schedule_id=schedule.schedule_id,
        operation_id=schedule.operation_id,
        run_source=run_source,
        scheduled_for=scheduled_for or schedule.next_run_at,
        started_at=now,
        run_status="RUNNING",
        attempt_no=attempt_no,
        parent_schedule_run_id=parent_schedule_run_id,
        runtime_params_snapshot=runtime,
        runtime_params_masked=masked,
        created_at=now,
    )
    db.add(run_row)
    schedule.last_run_at = now
    schedule.last_run_status = "RUNNING"
    await _record_event(
        db,
        schedule_id=schedule.schedule_id,
        schedule_run_id=run_id,
        event_type="RUN_STARTED" if attempt_no == 1 else "RETRY_STARTED",
        event_message="적재 실행을 시작합니다.",
        payload={"run_source": run_source, "attempt_no": attempt_no},
    )
    await db.flush()

    try:
        if schedule.run_policy == "LOAD_PREVIEW":
            result = await load_preview(db, schedule.operation_id, runtime_params=runtime)
            status = "SUCCESS"
            run_row.api_load_run_id = None
            run_row.inserted_count = 0
            run_row.skipped_count = int(result.get("skipped_count") or 0)
            run_row.error_count = 0
            run_row.result_summary = result
        else:
            result = await run_load(
                db,
                schedule.operation_id,
                runtime_params=runtime,
                called_by=f"schedule:{schedule.schedule_id}",
            )
            status = str(result.get("status") or "SUCCESS")
            run_row.api_load_run_id = result.get("load_run_id")
            run_row.inserted_count = int(result.get("inserted_count") or 0)
            run_row.skipped_count = int(result.get("skipped_count") or 0)
            run_row.error_count = int(result.get("error_count") or 0)
            run_row.result_summary = result

        run_row.run_status = status
        run_row.finished_at = utc_now()
        run_row.request_summary = {"runtime_params_masked": masked, "run_policy": schedule.run_policy}

        if status in ("SUCCESS", "WARNING"):
            schedule.last_success_at = run_row.finished_at
            schedule.last_run_status = status
            await _record_event(
                db,
                schedule_id=schedule.schedule_id,
                schedule_run_id=run_id,
                event_type="RUN_SUCCEEDED" if attempt_no == 1 else "RETRY_SUCCEEDED",
                event_message="적재 실행이 완료되었습니다.",
            )
        else:
            schedule.last_failure_at = run_row.finished_at
            schedule.last_run_status = status
            await _record_event(
                db,
                schedule_id=schedule.schedule_id,
                schedule_run_id=run_id,
                event_type="RUN_FAILED",
                event_message="적재 실행이 실패했습니다.",
            )
    except Exception as exc:
        run_row.run_status = "FAILED"
        run_row.finished_at = utc_now()
        run_row.error_message = str(exc)[:500]
        schedule.last_failure_at = run_row.finished_at
        schedule.last_run_status = "FAILED"
        await _record_event(
            db,
            schedule_id=schedule.schedule_id,
            schedule_run_id=run_id,
            event_type="RUN_FAILED" if attempt_no == 1 else "RETRY_FAILED",
            event_message=str(exc)[:300],
        )
        schedule.next_run_at = compute_next_run_at(sched_dict, from_time=utc_now())
        schedule.updated_at = utc_now()
        await db.flush()
        sched_name = schedule.schedule_name
        return _run_dict(run_row, schedule_name=sched_name)

    schedule.next_run_at = compute_next_run_at(sched_dict, from_time=utc_now())
    schedule.updated_at = utc_now()
    await db.flush()
    sched_name = schedule.schedule_name
    return _run_dict(run_row, schedule_name=sched_name)


async def run_schedule_now(
    db: AsyncSession,
    schedule_id: str,
    *,
    manual_params: dict[str, Any] | None = None,
    run_source: str = "MANUAL",
) -> dict[str, Any]:
    row = (
        await db.execute(select(DataLoadSchedule).where(DataLoadSchedule.schedule_id == schedule_id))
    ).scalar_one_or_none()
    if not row:
        raise DataLoadSchedulerError("적재 일정을 찾을 수 없습니다.", error_code="NOT_FOUND")
    if not row.active_yn:
        raise DataLoadSchedulerError("비활성화된 적재 일정은 실행할 수 없습니다.", error_code="INACTIVE")
    if row.metadata_json and row.metadata_json.get("archived_at"):
        raise DataLoadSchedulerError("보관된 적재 일정은 실행할 수 없습니다.", error_code="ARCHIVED")
    return await _execute_schedule_run(
        db,
        row,
        run_source=run_source,
        scheduled_for=utc_now(),
        manual_params=manual_params,
    )


async def run_due_schedules(db: AsyncSession) -> dict[str, Any]:
    due = await list_due_schedules(db)
    results: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    for sched in due:
        row = (
            await db.execute(
                select(DataLoadSchedule).where(DataLoadSchedule.schedule_id == sched["schedule_id"])
            )
        ).scalar_one()
        try:
            item = await _execute_schedule_run(
                db,
                row,
                run_source="RUN_DUE",
                scheduled_for=row.next_run_at,
            )
            results.append({"schedule_id": row.schedule_id, "schedule_run_id": item["schedule_run_id"], "status": item["run_status"]})
        except DataLoadSchedulerError as exc:
            errors.append({"schedule_id": row.schedule_id, "error_message": str(exc)})
    return {
        "due_count": len(due),
        "executed_count": len(results),
        "failed_count": len(errors),
        "results": results,
        "errors": errors,
    }


async def retry_schedule_run(db: AsyncSession, schedule_run_id: str) -> dict[str, Any]:
    run_row = (
        await db.execute(
            select(DataLoadScheduleRun).where(DataLoadScheduleRun.schedule_run_id == schedule_run_id)
        )
    ).scalar_one_or_none()
    if not run_row:
        raise DataLoadSchedulerError("적재 실행 이력을 찾을 수 없습니다.", error_code="NOT_FOUND")
    schedule = (
        await db.execute(
            select(DataLoadSchedule).where(DataLoadSchedule.schedule_id == run_row.schedule_id)
        )
    ).scalar_one_or_none()
    if not schedule:
        raise DataLoadSchedulerError("적재 일정을 찾을 수 없습니다.", error_code="NOT_FOUND")
    if not schedule.retry_enabled_yn:
        raise DataLoadSchedulerError("재시도가 비활성화된 일정입니다.", error_code="RETRY_DISABLED")
    if run_row.attempt_no > int(schedule.max_retry_count or 0):
        raise DataLoadSchedulerError("최대 재시도 횟수를 초과했습니다.", error_code="RETRY_LIMIT")
    return await _execute_schedule_run(
        db,
        schedule,
        run_source="RETRY",
        scheduled_for=utc_now(),
        manual_params=run_row.runtime_params_snapshot,
        attempt_no=run_row.attempt_no + 1,
        parent_schedule_run_id=schedule_run_id,
    )


async def list_schedule_runs(
    db: AsyncSession,
    *,
    schedule_id: str | None = None,
    run_status: str | None = None,
    run_source: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    clauses = []
    if schedule_id:
        clauses.append(DataLoadScheduleRun.schedule_id == schedule_id)
    if run_status:
        clauses.append(DataLoadScheduleRun.run_status == run_status)
    if run_source:
        clauses.append(DataLoadScheduleRun.run_source == run_source)
    if date_from:
        clauses.append(DataLoadScheduleRun.started_at >= date_from)
    if date_to:
        clauses.append(DataLoadScheduleRun.started_at <= date_to)
    q = select(DataLoadScheduleRun).order_by(DataLoadScheduleRun.started_at.desc())
    if clauses:
        q = q.where(and_(*clauses))
    rows = (await db.execute(q.limit(limit))).scalars().all()
    out: list[dict[str, Any]] = []
    for row in rows:
        sched = (
            await db.execute(
                select(DataLoadSchedule.schedule_name).where(
                    DataLoadSchedule.schedule_id == row.schedule_id
                )
            )
        ).scalar_one_or_none()
        out.append(_run_dict(row, schedule_name=sched))
    return out


async def get_schedule_run(db: AsyncSession, schedule_run_id: str) -> dict[str, Any] | None:
    row = (
        await db.execute(
            select(DataLoadScheduleRun).where(DataLoadScheduleRun.schedule_run_id == schedule_run_id)
        )
    ).scalar_one_or_none()
    if not row:
        return None
    sched = (
        await db.execute(
            select(DataLoadSchedule.schedule_name).where(DataLoadSchedule.schedule_id == row.schedule_id)
        )
    ).scalar_one_or_none()
    return _run_dict(row, schedule_name=sched)


async def list_schedule_events(
    db: AsyncSession,
    schedule_id: str,
    *,
    limit: int = 50,
) -> list[dict[str, Any]]:
    rows = (
        await db.execute(
            select(DataLoadScheduleEvent)
            .where(DataLoadScheduleEvent.schedule_id == schedule_id)
            .order_by(DataLoadScheduleEvent.created_at.desc())
            .limit(limit)
        )
    ).scalars().all()
    return [_event_dict(r) for r in rows]
