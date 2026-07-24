"""R11-S7-9 VP schedule-worker — due enqueue + skip/missed observability.

Separate from R10 run-due-worker and VP run-worker.
Creates mode=SCHEDULED PENDING rows for vp-run-worker to claim.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.database import async_session
from app.core.time import utc_now
from app.models.entities import (
    DataLoadSchedule,
    VisualPipelineMaterializationResult,
    VisualPipelineRun,
    VisualPipelineScheduleActivation,
)
from app.services.schedule_time_service import compute_next_run_at
from app.services.visual_pipeline.compile_result_service import SYNC_IN_SYNC
from app.services.visual_pipeline.manual_run_service import (
    ACTIVE_RUN_STATUSES,
    EXECUTION_BACKGROUND,
    EXECUTOR_WORKER,
    _new_visual_run_id,
)
from app.services.visual_pipeline.schedule_activation_service import (
    DEFAULT_TZ,
    STATUS_ACTIVE,
    _iso,
    _schedule_dict_from_row,
)
from app.services.visual_pipeline.visual_pipeline_service import _get_visual_definition

logger = logging.getLogger(__name__)

SCHEDULED_MODE = "SCHEDULED"
SKIP_ACTIVE_RUN = "ACTIVE_RUN_EXISTS"
SKIP_STALE_OR_INVALID = "STALE_OR_INVALID"
SKIP_DUPLICATE = "DUPLICATE_DEDUP_KEY"


@dataclass
class VpScheduleWorkerConfig:
    enabled: bool = False
    worker_id: str = ""
    worker_mode: str = "loop"
    poll_interval_seconds: int = 30
    max_batch_size: int = 10
    log_level: str = "INFO"

    @classmethod
    def from_settings(cls, settings: Settings | None = None) -> "VpScheduleWorkerConfig":
        s = settings or get_settings()
        return cls(
            enabled=bool(s.vp_schedule_worker_enabled),
            worker_id=str(s.vp_schedule_worker_id or "").strip(),
            worker_mode=str(s.vp_schedule_worker_mode or "loop").strip().lower() or "loop",
            poll_interval_seconds=max(1, int(s.vp_schedule_worker_poll_interval_seconds or 30)),
            max_batch_size=max(1, int(s.vp_schedule_worker_max_batch_size or 10)),
            log_level=str(s.vp_schedule_worker_log_level or "INFO").upper(),
        )


def build_schedule_worker_id(configured: str | None = None) -> str:
    base = (configured or "").strip() or f"vp-schedule-{uuid4().hex[:8]}"
    return base[:120]


def _dedup_key(activation_id: str, scheduled_for: datetime) -> str:
    stamp = scheduled_for.isoformat(timespec="seconds")
    return f"VP-SCHEDULED:{activation_id}:{stamp}"


def _iso_for_request(dt: datetime | None) -> str | None:
    return _iso(dt)


async def _pipeline_has_active_run(db: AsyncSession, pipeline_id: str) -> bool:
    count = (
        await db.execute(
            select(func.count())
            .select_from(VisualPipelineRun)
            .where(
                VisualPipelineRun.pipeline_id == pipeline_id,
                VisualPipelineRun.run_status.in_(ACTIVE_RUN_STATUSES),
            )
        )
    ).scalar_one()
    return int(count or 0) > 0


async def _advance_next_due(
    db: AsyncSession,
    activation: VisualPipelineScheduleActivation,
    schedule: DataLoadSchedule,
    *,
    from_time: datetime,
) -> None:
    next_due = compute_next_run_at(_schedule_dict_from_row(schedule), from_time=from_time)
    activation.next_due_at = next_due
    activation.updated_at = utc_now()
    await db.flush()


def _record_skip(
    activation: VisualPipelineScheduleActivation,
    *,
    worker_id: str,
    scheduled_for: datetime,
    reason: str,
    increment_missed: bool,
    now: datetime,
) -> None:
    activation.last_due_at = scheduled_for
    activation.last_skip_at = now
    activation.last_skip_reason = reason
    if increment_missed:
        activation.missed_count = int(activation.missed_count or 0) + 1
    meta = dict(activation.metadata_json or {})
    meta["last_worker_result"] = {
        "worker_id": worker_id,
        "checked_at": _iso(now),
        "action": reason,
        "scheduled_for": _iso(scheduled_for),
        "next_due_at": _iso(activation.next_due_at),
        "missed_count": int(activation.missed_count or 0),
    }
    activation.metadata_json = meta
    activation.updated_at = now


async def enqueue_due_activation(
    db: AsyncSession,
    activation: VisualPipelineScheduleActivation,
    *,
    worker_id: str,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Enqueue one SCHEDULED PENDING run for a due ACTIVE activation."""
    now = now or utc_now()
    result: dict[str, Any] = {
        "activation_id": activation.activation_id,
        "pipeline_id": activation.pipeline_id,
        "status": "skipped",
        "reason": None,
        "visual_run_id": None,
        "updated_next_due": False,
    }

    if activation.activation_status != STATUS_ACTIVE:
        result["reason"] = "not_active"
        return result
    if activation.next_due_at is None or activation.next_due_at > now:
        result["reason"] = "not_due"
        return result

    scheduled_for = activation.next_due_at

    try:
        defn = await _get_visual_definition(db, activation.pipeline_id)
    except LookupError:
        result["reason"] = "pipeline_missing"
        return result

    if (defn.current_sync_status or "") != SYNC_IN_SYNC:
        result["reason"] = "pipeline_stale"
        schedule = await _load_schedule(db, activation.r10_schedule_id)
        if schedule is not None:
            await _advance_next_due(db, activation, schedule, from_time=scheduled_for)
            _record_skip(
                activation,
                worker_id=worker_id,
                scheduled_for=scheduled_for,
                reason=SKIP_STALE_OR_INVALID,
                increment_missed=True,
                now=now,
            )
            await db.commit()
            result["updated_next_due"] = True
        return result

    mat_row = (
        await db.execute(
            select(VisualPipelineMaterializationResult).where(
                VisualPipelineMaterializationResult.materialization_result_id
                == activation.materialization_result_id,
                VisualPipelineMaterializationResult.pipeline_id == activation.pipeline_id,
            )
        )
    ).scalar_one_or_none()
    if mat_row is None or str(mat_row.materialization_status or "").upper() != "SUCCESS":
        result["reason"] = "materialization_invalid"
        schedule = await _load_schedule(db, activation.r10_schedule_id)
        if schedule is not None:
            await _advance_next_due(db, activation, schedule, from_time=scheduled_for)
            _record_skip(
                activation,
                worker_id=worker_id,
                scheduled_for=scheduled_for,
                reason=SKIP_STALE_OR_INVALID,
                increment_missed=True,
                now=now,
            )
            await db.commit()
            result["updated_next_due"] = True
        return result

    schedule = await _load_schedule(db, activation.r10_schedule_id)
    if schedule is None:
        result["reason"] = "r10_schedule_missing"
        return result

    if schedule.active_yn:
        schedule.active_yn = False

    if await _pipeline_has_active_run(db, activation.pipeline_id):
        result["reason"] = "skipped_active_run"
        await _advance_next_due(db, activation, schedule, from_time=scheduled_for)
        _record_skip(
            activation,
            worker_id=worker_id,
            scheduled_for=scheduled_for,
            reason=SKIP_ACTIVE_RUN,
            increment_missed=True,
            now=now,
        )
        await db.commit()
        result["updated_next_due"] = True
        return result

    objects = dict(mat_row.objects_json or {})
    dedup = _dedup_key(activation.activation_id, scheduled_for)
    request_store = {
        "mode": SCHEDULED_MODE,
        "trigger_type": SCHEDULED_MODE,
        "activation_id": activation.activation_id,
        "r10_schedule_id": activation.r10_schedule_id,
        "cron_expression": activation.cron_expression,
        "timezone": activation.timezone or schedule.timezone or DEFAULT_TZ,
        "scheduled_for": _iso_for_request(scheduled_for),
        "executor": EXECUTOR_WORKER,
        "params": {},
        "resolved_objects": {
            "operation_id": objects.get("operation_id"),
            "write_policy_id": objects.get("write_policy_id"),
            "transform_config_id": objects.get("transform_config_id"),
        },
        "enqueued_by": worker_id,
    }

    run_row = VisualPipelineRun(
        visual_run_id=_new_visual_run_id(),
        pipeline_id=activation.pipeline_id,
        compile_result_id=activation.compile_result_id or mat_row.compile_result_id,
        materialization_result_id=mat_row.materialization_result_id,
        graph_version_hash=mat_row.graph_version_hash,
        mode=SCHEDULED_MODE,
        execution_mode=EXECUTION_BACKGROUND,
        run_status="PENDING",
        request_json=request_store,
        result_json={},
        issues_json=[],
        activation_id=activation.activation_id,
        r10_schedule_id=activation.r10_schedule_id,
        scheduled_for=scheduled_for,
        triggered_at=now,
        dedup_key=dedup,
        attempt_count=0,
        started_at=None,
        finished_at=None,
        created_at=now,
    )
    db.add(run_row)

    activation.last_triggered_at = now
    activation.last_due_at = scheduled_for
    activation.trigger_count = int(activation.trigger_count or 0) + 1
    await _advance_next_due(db, activation, schedule, from_time=scheduled_for)
    meta = dict(activation.metadata_json or {})
    meta["last_worker_result"] = {
        "worker_id": worker_id,
        "checked_at": _iso(now),
        "action": "enqueued",
        "scheduled_for": _iso(scheduled_for),
        "next_due_at": _iso(activation.next_due_at),
        "visual_run_id": run_row.visual_run_id,
    }
    activation.metadata_json = meta
    activation.updated_at = now

    try:
        await db.flush()
        await db.commit()
    except IntegrityError:
        await db.rollback()
        activation = (
            await db.execute(
                select(VisualPipelineScheduleActivation).where(
                    VisualPipelineScheduleActivation.activation_id == activation.activation_id
                )
            )
        ).scalar_one()
        schedule = await _load_schedule(db, activation.r10_schedule_id)
        if schedule is not None:
            await _advance_next_due(db, activation, schedule, from_time=scheduled_for)
            _record_skip(
                activation,
                worker_id=worker_id,
                scheduled_for=scheduled_for,
                reason=SKIP_DUPLICATE,
                increment_missed=False,
                now=now,
            )
            await db.commit()
            result["updated_next_due"] = True
        result["reason"] = "duplicate_dedup"
        return result

    result["status"] = "enqueued"
    result["visual_run_id"] = run_row.visual_run_id
    result["reason"] = None
    result["updated_next_due"] = True
    logger.info(
        "enqueued scheduled run activation_id=%s visual_run_id=%s scheduled_for=%s worker_id=%s",
        activation.activation_id,
        run_row.visual_run_id,
        scheduled_for,
        worker_id,
    )
    return result


async def _load_schedule(db: AsyncSession, schedule_id: str) -> DataLoadSchedule | None:
    return (
        await db.execute(select(DataLoadSchedule).where(DataLoadSchedule.schedule_id == schedule_id))
    ).scalar_one_or_none()


async def find_due_activations(
    db: AsyncSession,
    *,
    now: datetime | None = None,
    batch_size: int = 10,
) -> list[VisualPipelineScheduleActivation]:
    now = now or utc_now()
    rows = (
        await db.execute(
            select(VisualPipelineScheduleActivation)
            .where(
                VisualPipelineScheduleActivation.activation_status == STATUS_ACTIVE,
                VisualPipelineScheduleActivation.next_due_at.is_not(None),
                VisualPipelineScheduleActivation.next_due_at <= now,
            )
            .order_by(VisualPipelineScheduleActivation.next_due_at.asc())
            .limit(max(1, batch_size))
        )
    ).scalars().all()
    return list(rows)


def _empty_summary(worker_id: str) -> dict[str, Any]:
    return {
        "worker_id": worker_id,
        "checked": 0,
        "scanned": 0,
        "enqueued": 0,
        "skipped": 0,
        "skipped_active_run": 0,
        "skipped_duplicate": 0,
        "skipped_paused": 0,
        "skipped_invalid": 0,
        "updated_next_due": 0,
        "errors": 0,
        "items": [],
    }


def _bump_summary(summary: dict[str, Any], item: dict[str, Any]) -> None:
    reason = item.get("reason")
    if item.get("status") == "enqueued":
        summary["enqueued"] += 1
    else:
        summary["skipped"] += 1
        if reason == "skipped_active_run":
            summary["skipped_active_run"] += 1
        elif reason == "duplicate_dedup":
            summary["skipped_duplicate"] += 1
        elif reason in {"pipeline_stale", "materialization_invalid", "r10_schedule_missing", "pipeline_missing"}:
            summary["skipped_invalid"] += 1
        elif reason == "not_active":
            summary["skipped_paused"] += 1
    if item.get("updated_next_due"):
        summary["updated_next_due"] += 1


async def run_schedule_worker_once(
    *,
    worker_id: str,
    batch_size: int = 10,
) -> dict[str, Any]:
    summary = _empty_summary(worker_id)
    async with async_session() as db:
        due_rows = await find_due_activations(db, batch_size=batch_size)
        summary["checked"] = len(due_rows)
        summary["scanned"] = len(due_rows)
        activation_ids = [r.activation_id for r in due_rows]

    for activation_id in activation_ids:
        try:
            async with async_session() as db:
                activation = (
                    await db.execute(
                        select(VisualPipelineScheduleActivation)
                        .where(VisualPipelineScheduleActivation.activation_id == activation_id)
                        .with_for_update()
                    )
                ).scalar_one_or_none()
                if activation is None:
                    summary["skipped"] += 1
                    continue
                item = await enqueue_due_activation(db, activation, worker_id=worker_id)
                summary["items"].append(item)
                _bump_summary(summary, item)
                logger.info(
                    "schedule action activation_id=%s action=%s scheduled_for=%s next_due=%s",
                    item.get("activation_id"),
                    item.get("reason") or item.get("status"),
                    (item.get("activation_id") and None),
                    None,
                )
        except Exception:
            logger.exception("schedule worker failed activation_id=%s", activation_id)
            summary["errors"] += 1
    return summary


async def run_schedule_worker_loop(
    *,
    worker_id: str,
    poll_interval_seconds: int = 30,
    batch_size: int = 10,
    max_iterations: int | None = None,
    should_stop: Callable[[], bool] | None = None,
) -> None:
    import asyncio

    iterations = 0
    while True:
        if should_stop and should_stop():
            break
        summary = await run_schedule_worker_once(worker_id=worker_id, batch_size=batch_size)
        logger.info(
            "schedule cycle checked=%s enqueued=%s skipped_active_run=%s skipped_duplicate=%s "
            "skipped_invalid=%s updated_next_due=%s errors=%s",
            summary["checked"],
            summary["enqueued"],
            summary["skipped_active_run"],
            summary["skipped_duplicate"],
            summary["skipped_invalid"],
            summary["updated_next_due"],
            summary["errors"],
        )
        iterations += 1
        if max_iterations is not None and iterations >= max_iterations:
            break
        if should_stop and should_stop():
            break
        await asyncio.sleep(max(1, poll_interval_seconds))
