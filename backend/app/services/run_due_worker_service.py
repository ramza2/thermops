"""Run-due Worker 서비스 (R10-S10)."""

from __future__ import annotations

import json
import logging
import os
import socket
from dataclasses import dataclass
from datetime import timedelta
from typing import Any
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.time import utc_now
from app.models.entities import RunDueWorkerInstance, RunDueWorkerRun
from app.services.data_load_scheduler_service import run_due_schedules
from app.services.notification_event_service import emit_notification_safe
from app.services.run_due_worker_lock_service import (
    DEFAULT_LOCK_KEY,
    extend_lock,
    release_lock,
    try_acquire_lock,
)
from app.utils.masking import mask_params_dict, redact_text

logger = logging.getLogger(__name__)

CONSECUTIVE_FAILURE_THRESHOLD = 3


class RunDueWorkerError(ValueError):
    def __init__(self, message: str, *, error_code: str = "WORKER_ERROR"):
        self.error_code = error_code
        super().__init__(message)


@dataclass
class WorkerConfig:
    enabled: bool
    worker_name: str
    worker_mode: str
    poll_interval_seconds: int
    lock_ttl_seconds: int
    max_batch_size: int
    fail_fast: bool
    notification_enabled: bool
    graceful_timeout_seconds: int
    log_level: str

    @classmethod
    def from_settings(cls, settings: Settings | None = None) -> WorkerConfig:
        s = settings or get_settings()
        mode = (s.run_due_worker_mode or "loop").strip().lower()
        if mode not in ("loop", "once"):
            mode = "loop"
        enabled_raw = s.run_due_worker_enabled
        if isinstance(enabled_raw, str):
            enabled = enabled_raw.strip().lower() in ("1", "true", "yes", "on")
        else:
            enabled = bool(enabled_raw)
        return cls(
            enabled=enabled,
            worker_name=s.run_due_worker_name or "run-due-worker-1",
            worker_mode=mode,
            poll_interval_seconds=max(5, int(s.run_due_poll_interval_seconds or 60)),
            lock_ttl_seconds=max(30, int(s.run_due_lock_ttl_seconds or 120)),
            max_batch_size=max(1, int(s.run_due_max_batch_size or 20)),
            fail_fast=bool(s.run_due_fail_fast),
            notification_enabled=bool(s.run_due_notification_enabled),
            graceful_timeout_seconds=max(5, int(s.run_due_graceful_timeout_seconds or 30)),
            log_level=(s.run_due_log_level or "INFO").upper(),
        )


def build_worker_instance_id(worker_name: str) -> str:
    host = socket.gethostname() or "localhost"
    pid = os.getpid()
    return f"{worker_name}@{host}:{pid}"


def _new_run_id() -> str:
    return f"WR-{uuid4().hex[:12].upper()}"


def _dt_iso(val) -> str | None:
    return val.isoformat() if val else None


def _instance_dict(row: RunDueWorkerInstance) -> dict[str, Any]:
    return {
        "worker_instance_id": row.worker_instance_id,
        "worker_name": row.worker_name,
        "worker_mode": row.worker_mode,
        "host_name": row.host_name,
        "process_id": row.process_id,
        "enabled_yn": bool(row.enabled_yn),
        "status": row.status,
        "poll_interval_seconds": row.poll_interval_seconds,
        "last_heartbeat_at": _dt_iso(row.last_heartbeat_at),
        "last_run_started_at": _dt_iso(row.last_run_started_at),
        "last_run_finished_at": _dt_iso(row.last_run_finished_at),
        "last_run_status": row.last_run_status,
        "consecutive_failure_count": int(row.consecutive_failure_count or 0),
        "total_run_count": int(row.total_run_count or 0),
        "total_success_count": int(row.total_success_count or 0),
        "total_failure_count": int(row.total_failure_count or 0),
        "created_at": _dt_iso(row.created_at),
        "updated_at": _dt_iso(row.updated_at),
        "metadata_json": row.metadata_json,
    }


def _run_dict(row: RunDueWorkerRun) -> dict[str, Any]:
    return {
        "worker_run_id": row.worker_run_id,
        "worker_instance_id": row.worker_instance_id,
        "worker_name": row.worker_name,
        "run_mode": row.run_mode,
        "started_at": _dt_iso(row.started_at),
        "finished_at": _dt_iso(row.finished_at),
        "run_status": row.run_status,
        "due_schedule_count": int(row.due_schedule_count or 0),
        "executed_schedule_count": int(row.executed_schedule_count or 0),
        "success_schedule_count": int(row.success_schedule_count or 0),
        "failed_schedule_count": int(row.failed_schedule_count or 0),
        "skipped_schedule_count": int(row.skipped_schedule_count or 0),
        "run_due_result_json": row.run_due_result_json,
        "error_message": row.error_message,
        "created_at": _dt_iso(row.created_at),
        "metadata_json": row.metadata_json,
    }


def mask_run_due_result(result: dict[str, Any] | None) -> dict[str, Any] | None:
    if not result:
        return result
    safe = mask_params_dict(dict(result))
    text = redact_text(json.dumps(safe, ensure_ascii=False, default=str))
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return {"summary": text[:2000]}
    if isinstance(parsed, dict):
        for key in ("results", "errors", "error_summary"):
            if key in parsed and isinstance(parsed[key], list):
                parsed[key] = [
                    mask_params_dict(item) if isinstance(item, dict) else item for item in parsed[key]
                ]
    return parsed if isinstance(parsed, dict) else {"summary": str(parsed)[:2000]}


async def upsert_worker_instance(
    db: AsyncSession,
    *,
    worker_instance_id: str,
    config: WorkerConfig,
    status: str = "STARTING",
) -> dict[str, Any]:
    now = utc_now()
    host = socket.gethostname() or None
    pid = os.getpid()
    mode = config.worker_mode.upper()
    row = (
        await db.execute(
            select(RunDueWorkerInstance).where(RunDueWorkerInstance.worker_instance_id == worker_instance_id)
        )
    ).scalar_one_or_none()
    if row is None:
        row = RunDueWorkerInstance(
            worker_instance_id=worker_instance_id,
            worker_name=config.worker_name,
            worker_mode=mode,
            host_name=host,
            process_id=pid,
            enabled_yn=True,
            status=status,
            poll_interval_seconds=config.poll_interval_seconds,
            last_heartbeat_at=now,
            consecutive_failure_count=0,
            total_run_count=0,
            total_success_count=0,
            total_failure_count=0,
            created_at=now,
            updated_at=now,
        )
        db.add(row)
    else:
        row.worker_name = config.worker_name
        row.worker_mode = mode
        row.host_name = host
        row.process_id = pid
        row.status = status
        row.poll_interval_seconds = config.poll_interval_seconds
        row.last_heartbeat_at = now
        row.updated_at = now
    await db.flush()
    return _instance_dict(row)


async def update_heartbeat(db: AsyncSession, worker_instance_id: str, *, status: str | None = None) -> None:
    row = (
        await db.execute(
            select(RunDueWorkerInstance).where(RunDueWorkerInstance.worker_instance_id == worker_instance_id)
        )
    ).scalar_one_or_none()
    if not row:
        return
    now = utc_now()
    row.last_heartbeat_at = now
    row.updated_at = now
    if status:
        row.status = status
    await db.flush()


async def set_worker_status(db: AsyncSession, worker_instance_id: str, status: str) -> None:
    row = (
        await db.execute(
            select(RunDueWorkerInstance).where(RunDueWorkerInstance.worker_instance_id == worker_instance_id)
        )
    ).scalar_one_or_none()
    if not row:
        return
    row.status = status
    row.updated_at = utc_now()
    if status in ("STOPPED", "FAILED"):
        row.last_heartbeat_at = utc_now()
    await db.flush()


async def list_worker_instances(db: AsyncSession) -> list[dict[str, Any]]:
    rows = (
        await db.execute(select(RunDueWorkerInstance).order_by(RunDueWorkerInstance.last_heartbeat_at.desc().nullslast()))
    ).scalars().all()
    return [_instance_dict(r) for r in rows]


async def get_worker_instance(db: AsyncSession, worker_instance_id: str) -> dict[str, Any] | None:
    row = (
        await db.execute(
            select(RunDueWorkerInstance).where(RunDueWorkerInstance.worker_instance_id == worker_instance_id)
        )
    ).scalar_one_or_none()
    return _instance_dict(row) if row else None


async def list_worker_runs(
    db: AsyncSession,
    *,
    worker_instance_id: str | None = None,
    run_status: str | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    q = select(RunDueWorkerRun).order_by(RunDueWorkerRun.started_at.desc())
    if worker_instance_id:
        q = q.where(RunDueWorkerRun.worker_instance_id == worker_instance_id)
    if run_status:
        q = q.where(RunDueWorkerRun.run_status == run_status)
    rows = (await db.execute(q.limit(limit))).scalars().all()
    return [_run_dict(r) for r in rows]


async def get_worker_run(db: AsyncSession, worker_run_id: str) -> dict[str, Any] | None:
    row = (
        await db.execute(select(RunDueWorkerRun).where(RunDueWorkerRun.worker_run_id == worker_run_id))
    ).scalar_one_or_none()
    return _run_dict(row) if row else None


async def get_worker_summary(db: AsyncSession) -> dict[str, Any]:
    instance_count = (await db.execute(select(func.count()).select_from(RunDueWorkerInstance))).scalar_one()
    running_count = (
        await db.execute(
            select(func.count())
            .select_from(RunDueWorkerInstance)
            .where(RunDueWorkerInstance.status.in_(("RUNNING", "IDLE", "STARTING")))
        )
    ).scalar_one()
    stale_count = (
        await db.execute(
            select(func.count()).select_from(RunDueWorkerInstance).where(RunDueWorkerInstance.status == "STALE")
        )
    ).scalar_one()
    recent_runs = (await db.execute(select(func.count()).select_from(RunDueWorkerRun))).scalar_one()
    failed_runs = (
        await db.execute(
            select(func.count()).select_from(RunDueWorkerRun).where(RunDueWorkerRun.run_status == "FAILED")
        )
    ).scalar_one()
    return {
        "instance_count": int(instance_count or 0),
        "active_instance_count": int(running_count or 0),
        "stale_instance_count": int(stale_count or 0),
        "total_worker_run_count": int(recent_runs or 0),
        "failed_worker_run_count": int(failed_runs or 0),
        "lock_key": DEFAULT_LOCK_KEY,
    }


async def _emit_worker_notification(
    db: AsyncSession,
    *,
    config: WorkerConfig,
    event_type: str,
    severity: str,
    title: str,
    message: str | None,
    worker_instance_id: str,
    worker_run_id: str | None = None,
    payload: dict[str, Any] | None = None,
) -> None:
    if not config.notification_enabled:
        return
    safe_payload = mask_params_dict(payload) if payload else None
    await emit_notification_safe(
        db,
        event_source="RUN_DUE_WORKER",
        event_type=event_type,
        severity=severity,
        title=title,
        message=message,
        resource_type="worker_run" if worker_run_id else "worker_instance",
        resource_id=worker_run_id or worker_instance_id,
        correlation_id=worker_instance_id,
        dedup_key=f"{worker_instance_id}:{event_type}",
        event_payload_json=safe_payload,
    )


async def _finalize_instance_after_run(
    db: AsyncSession,
    *,
    worker_instance_id: str,
    run_status: str,
    had_prior_failures: bool,
    config: WorkerConfig,
    worker_run_id: str,
) -> None:
    row = (
        await db.execute(
            select(RunDueWorkerInstance).where(RunDueWorkerInstance.worker_instance_id == worker_instance_id)
        )
    ).scalar_one_or_none()
    if not row:
        return
    now = utc_now()
    row.last_run_finished_at = now
    row.last_run_status = run_status
    row.total_run_count = int(row.total_run_count or 0) + 1
    row.updated_at = now
    row.last_heartbeat_at = now

    if run_status in ("SUCCESS", "WARNING", "SKIPPED"):
        row.total_success_count = int(row.total_success_count or 0) + 1
        if had_prior_failures and row.consecutive_failure_count > 0:
            await _emit_worker_notification(
                db,
                config=config,
                event_type="RUN_DUE_WORKER_RECOVERED",
                severity="INFO",
                title=f"적재 일정 실행 Worker 복구: {row.worker_name}",
                message="Worker run-due 실행이 정상화되었습니다.",
                worker_instance_id=worker_instance_id,
                worker_run_id=worker_run_id,
                payload={"last_run_status": run_status},
            )
        row.consecutive_failure_count = 0
        row.status = "IDLE" if config.worker_mode == "loop" else "STOPPED"
    else:
        row.total_failure_count = int(row.total_failure_count or 0) + 1
        row.consecutive_failure_count = int(row.consecutive_failure_count or 0) + 1
        row.status = "FAILED" if config.worker_mode == "once" else "RUNNING"
        await _emit_worker_notification(
            db,
            config=config,
            event_type="RUN_DUE_WORKER_FAILED",
            severity="ERROR",
            title=f"적재 일정 실행 Worker 실패: {row.worker_name}",
            message=f"Worker run-due 실행이 실패했습니다. (상태: {run_status})",
            worker_instance_id=worker_instance_id,
            worker_run_id=worker_run_id,
            payload={"run_status": run_status},
        )
        if row.consecutive_failure_count >= CONSECUTIVE_FAILURE_THRESHOLD:
            await _emit_worker_notification(
                db,
                config=config,
                event_type="RUN_DUE_WORKER_CONSECUTIVE_FAILURE",
                severity="CRITICAL",
                title=f"적재 일정 실행 Worker 연속 실패: {row.worker_name}",
                message=f"연속 실패 {row.consecutive_failure_count}회",
                worker_instance_id=worker_instance_id,
                worker_run_id=worker_run_id,
                payload={"consecutive_failure_count": row.consecutive_failure_count},
            )
    await db.flush()


def _resolve_worker_run_status(
    *,
    lock_acquired: bool,
    run_due_result: dict[str, Any] | None,
    exc: Exception | None,
) -> str:
    if not lock_acquired:
        return "SKIPPED"
    if exc is not None:
        return "FAILED"
    if not run_due_result:
        return "SUCCESS"
    due_count = int(run_due_result.get("due_schedule_count") or 0)
    failed = int(run_due_result.get("failed_schedule_count") or 0) + len(run_due_result.get("error_summary") or [])
    success = int(run_due_result.get("success_schedule_count") or 0)
    if due_count == 0:
        return "SUCCESS"
    if failed > 0 and success > 0:
        return "WARNING"
    if failed > 0:
        return "FAILED"
    return "SUCCESS"


async def execute_worker_tick(
    db: AsyncSession,
    *,
    worker_instance_id: str,
    config: WorkerConfig,
    run_mode: str,
) -> dict[str, Any]:
    """단일 worker tick — lock 획득 후 run-due 실행."""
    now = utc_now()
    inst = (
        await db.execute(
            select(RunDueWorkerInstance).where(RunDueWorkerInstance.worker_instance_id == worker_instance_id)
        )
    ).scalar_one_or_none()
    had_prior_failures = bool(inst and int(inst.consecutive_failure_count or 0) > 0)
    if inst:
        inst.last_run_started_at = now
        inst.status = "RUNNING"
        inst.updated_at = now
        await db.flush()

    run_id = _new_run_id()
    run_row = RunDueWorkerRun(
        worker_run_id=run_id,
        worker_instance_id=worker_instance_id,
        worker_name=config.worker_name,
        run_mode=run_mode,
        started_at=now,
        run_status="RUNNING",
        created_at=now,
        metadata_json={"triggered_by": "WORKER", "lock_key": DEFAULT_LOCK_KEY},
    )
    db.add(run_row)
    await db.flush()

    lock_acquired = await try_acquire_lock(
        db,
        owner_instance_id=worker_instance_id,
        ttl_seconds=config.lock_ttl_seconds,
    )
    run_due_result: dict[str, Any] | None = None
    exc: Exception | None = None

    if lock_acquired:
        try:
            await extend_lock(db, owner_instance_id=worker_instance_id, ttl_seconds=config.lock_ttl_seconds)
            run_due_result = await run_due_schedules(
                db,
                max_batch_size=config.max_batch_size,
                triggered_by="WORKER",
                worker_instance_id=worker_instance_id,
                fail_fast=config.fail_fast,
                return_detail=True,
            )
        except Exception as run_exc:
            exc = run_exc
            logger.exception("run-due execution failed")
        finally:
            await release_lock(db, owner_instance_id=worker_instance_id)
    else:
        logger.info("run-due lock held by another worker; skipping tick")

    run_status = _resolve_worker_run_status(lock_acquired=lock_acquired, run_due_result=run_due_result, exc=exc)
    finished = utc_now()
    run_row.finished_at = finished
    run_row.run_status = run_status
    if run_due_result:
        run_row.due_schedule_count = int(run_due_result.get("due_schedule_count") or 0)
        run_row.executed_schedule_count = int(run_due_result.get("executed_schedule_count") or 0)
        run_row.success_schedule_count = int(run_due_result.get("success_schedule_count") or 0)
        run_row.failed_schedule_count = int(run_due_result.get("failed_schedule_count") or 0)
        run_row.skipped_schedule_count = int(run_due_result.get("skipped_schedule_count") or 0)
        run_row.run_due_result_json = mask_run_due_result(run_due_result)
    if exc is not None:
        run_row.error_message = redact_text(str(exc))[:500]

    if lock_acquired and run_status == "WARNING" and config.notification_enabled:
        await _emit_worker_notification(
            db,
            config=config,
            event_type="RUN_DUE_WORKER_RUN_WARNING",
            severity="WARNING",
            title=f"적재 일정 실행 Worker 부분 실패: {config.worker_name}",
            message="run-due 결과 일부 일정이 실패했습니다.",
            worker_instance_id=worker_instance_id,
            worker_run_id=run_id,
            payload={
                "failed_schedule_count": run_row.failed_schedule_count,
                "success_schedule_count": run_row.success_schedule_count,
            },
        )

    await _finalize_instance_after_run(
        db,
        worker_instance_id=worker_instance_id,
        run_status=run_status,
        had_prior_failures=had_prior_failures,
        config=config,
        worker_run_id=run_id,
    )
    await db.flush()
    return _run_dict(run_row)


async def mark_stale_workers(
    db: AsyncSession,
    *,
    lock_ttl_seconds: int | None = None,
    config: WorkerConfig | None = None,
) -> list[dict[str, Any]]:
    cfg = config or WorkerConfig.from_settings()
    ttl = lock_ttl_seconds or cfg.lock_ttl_seconds
    threshold = utc_now() - timedelta(seconds=ttl * 2)
    rows = (
        await db.execute(
            select(RunDueWorkerInstance).where(
                RunDueWorkerInstance.status.in_(("RUNNING", "IDLE", "STARTING")),
                RunDueWorkerInstance.last_heartbeat_at.is_not(None),
                RunDueWorkerInstance.last_heartbeat_at < threshold,
            )
        )
    ).scalars().all()
    marked: list[dict[str, Any]] = []
    for row in rows:
        row.status = "STALE"
        row.updated_at = utc_now()
        marked.append(_instance_dict(row))
        if cfg.notification_enabled:
            await _emit_worker_notification(
                db,
                config=cfg,
                event_type="RUN_DUE_WORKER_STALE",
                severity="WARNING",
                title=f"적재 일정 실행 Worker 상태 신호 누락: {row.worker_name}",
                message="Worker heartbeat가 장시간 갱신되지 않았습니다.",
                worker_instance_id=row.worker_instance_id,
                payload={"last_heartbeat_at": _dt_iso(row.last_heartbeat_at)},
            )
    await db.flush()
    return marked


async def run_once_via_api(
    db: AsyncSession,
    *,
    worker_name: str | None = None,
    max_batch_size: int | None = None,
) -> dict[str, Any]:
    cfg = WorkerConfig.from_settings()
    if worker_name:
        cfg = WorkerConfig(
            enabled=True,
            worker_name=worker_name,
            worker_mode="once",
            poll_interval_seconds=cfg.poll_interval_seconds,
            lock_ttl_seconds=cfg.lock_ttl_seconds,
            max_batch_size=max_batch_size or cfg.max_batch_size,
            fail_fast=cfg.fail_fast,
            notification_enabled=cfg.notification_enabled,
            graceful_timeout_seconds=cfg.graceful_timeout_seconds,
            log_level=cfg.log_level,
        )
    instance_id = build_worker_instance_id(cfg.worker_name)
    await upsert_worker_instance(db, worker_instance_id=instance_id, config=cfg, status="RUNNING")
    return await execute_worker_tick(db, worker_instance_id=instance_id, config=cfg, run_mode="ONCE")
