"""R11-S8-6 Visual Pipeline Schedule Catch-up — manual enqueue PoC.

Creates one PENDING SCHEDULED run for a missed due slot. Does not call run_load,
BackgroundTasks, or wake the schedule worker. Does not change next_due_at.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.time import utc_now
from app.models.entities import (
    VisualPipelineMaterializationResult,
    VisualPipelineRun,
    VisualPipelineScheduleActivation,
)
from app.services.visual_pipeline.audit_service import (
    ACTOR_USER,
    SOURCE_API,
    STATUS_SUCCESS,
    record_visual_pipeline_audit_event,
)
from app.services.visual_pipeline.manual_run_service import (
    ACTIVE_RUN_STATUSES,
    EXECUTION_BACKGROUND,
    EXECUTOR_WORKER,
    _new_visual_run_id,
)
from app.services.visual_pipeline.run_event_service import (
    EVENT_RUN_CREATED,
    EVENT_SCHEDULE_CATCHUP_ENQUEUED,
    emit_run_event_safe,
)
from app.services.visual_pipeline.schedule_activation_service import (
    DEFAULT_TZ,
    STATUS_ACTIVE,
    STATUS_INACTIVE,
    STATUS_PAUSED,
    _iso,
)
from app.services.visual_pipeline.schedule_worker_service import (
    SKIP_ACTIVE_RUN,
    SKIP_STALE_OR_INVALID,
)
from app.services.visual_pipeline.visual_pipeline_service import _get_visual_definition

logger = logging.getLogger(__name__)

SCHEDULED_MODE = "SCHEDULED"

CATCHUP_ELIGIBLE_SKIP_REASONS = frozenset({SKIP_ACTIVE_RUN, SKIP_STALE_OR_INVALID})

DATA_BASIS_WARNING = (
    "Catch-up은 과거 기준시점의 데이터를 재실행할 수 있으므로 입력 데이터 기준을 확인하세요."
)
STALE_WARNING = (
    "최근 skip 사유가 STALE_OR_INVALID입니다. 그래프 동기화/실행 설정을 확인한 뒤 보정하세요."
)


class ScheduleCatchupError(Exception):
    def __init__(self, code: str, message: str | None = None, *, http_status: int = 409) -> None:
        self.code = code
        self.message = message or code
        self.http_status = http_status
        super().__init__(self.message)


def _poll_url(pipeline_id: str, visual_run_id: str) -> str:
    return f"/api/v1/visual-pipelines/{pipeline_id}/runs/{visual_run_id}"


def _parse_dt(raw: str | datetime | None) -> datetime | None:
    if raw is None:
        return None
    if isinstance(raw, datetime):
        return raw.replace(tzinfo=None) if raw.tzinfo else raw
    text = str(raw).strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    return dt.replace(tzinfo=None) if dt.tzinfo else dt


def _iso_seconds(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    return dt.replace(microsecond=0).isoformat(timespec="seconds")


def _catchup_dedup_key(activation_id: str, scheduled_at: datetime, visual_run_id: str) -> str:
    stamp = scheduled_at.replace(microsecond=0).isoformat(timespec="seconds")
    return f"CATCHUP:{activation_id}:{stamp}:{visual_run_id}"


def _candidate_response(
    *,
    pipeline_id: str,
    activation_id: str,
    eligible: bool,
    reason: str,
    candidate_scheduled_at: datetime | None = None,
    missed_count: int = 0,
    last_due_at: datetime | None = None,
    last_skip_at: datetime | None = None,
    last_skip_reason: str | None = None,
    warnings: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "pipeline_id": pipeline_id,
        "activation_id": activation_id,
        "eligible": eligible,
        "candidate_scheduled_at": _iso(candidate_scheduled_at),
        "missed_count": int(missed_count or 0),
        "last_due_at": _iso(last_due_at),
        "last_skip_at": _iso(last_skip_at),
        "last_skip_reason": last_skip_reason,
        "reason": reason,
        "warnings": list(warnings or []),
    }


async def _load_activation(
    db: AsyncSession, pipeline_id: str, activation_id: str
) -> VisualPipelineScheduleActivation:
    await _get_visual_definition(db, pipeline_id)
    row = (
        await db.execute(
            select(VisualPipelineScheduleActivation).where(
                VisualPipelineScheduleActivation.pipeline_id == pipeline_id,
                VisualPipelineScheduleActivation.activation_id == activation_id,
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise ScheduleCatchupError(
            "SCHEDULE_CATCHUP_ACTIVATION_NOT_FOUND",
            "Schedule activation not found for this pipeline.",
            http_status=404,
        )
    return row


async def _has_run_for_scheduled_at(
    db: AsyncSession,
    *,
    pipeline_id: str,
    activation_id: str,
    scheduled_at: datetime,
) -> bool:
    count = (
        await db.execute(
            select(func.count())
            .select_from(VisualPipelineRun)
            .where(
                VisualPipelineRun.pipeline_id == pipeline_id,
                VisualPipelineRun.activation_id == activation_id,
                or_(
                    VisualPipelineRun.scheduled_for == scheduled_at,
                    VisualPipelineRun.catchup_for_scheduled_at == scheduled_at,
                ),
            )
        )
    ).scalar_one()
    return int(count or 0) > 0


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


async def get_schedule_catchup_candidate(
    db: AsyncSession,
    *,
    pipeline_id: str,
    activation_id: str,
) -> dict[str, Any]:
    """Read-only candidate for the most recent catch-up-able missed slot."""
    activation = await _load_activation(db, pipeline_id, activation_id)
    missed = int(activation.missed_count or 0)
    last_due = activation.last_due_at
    last_skip = activation.last_skip_at
    skip_reason = str(activation.last_skip_reason or "").strip() or None

    base_kwargs = {
        "pipeline_id": pipeline_id,
        "activation_id": activation_id,
        "missed_count": missed,
        "last_due_at": last_due,
        "last_skip_at": last_skip,
        "last_skip_reason": skip_reason,
    }

    candidate_at = last_due or last_skip
    if candidate_at is None:
        return _candidate_response(
            **base_kwargs,
            eligible=False,
            reason="Catch-up 가능한 누락 실행 후보가 없습니다.",
        )

    if skip_reason not in CATCHUP_ELIGIBLE_SKIP_REASONS:
        if missed <= 0:
            return _candidate_response(
                **base_kwargs,
                eligible=False,
                reason="Catch-up 가능한 누락 실행 후보가 없습니다.",
            )
        return _candidate_response(
            **base_kwargs,
            eligible=False,
            reason=(
                f"최근 skip 사유({skip_reason or '없음'})는 Catch-up 대상이 아닙니다."
            ),
            candidate_scheduled_at=candidate_at,
        )

    if await _has_run_for_scheduled_at(
        db,
        pipeline_id=pipeline_id,
        activation_id=activation_id,
        scheduled_at=candidate_at,
    ):
        return _candidate_response(
            **base_kwargs,
            eligible=False,
            reason="해당 스케줄 시각에 대한 Run이 이미 존재합니다.",
            candidate_scheduled_at=candidate_at,
        )

    warnings = [DATA_BASIS_WARNING]
    if skip_reason == SKIP_STALE_OR_INVALID:
        warnings.append(STALE_WARNING)

    status = str(activation.activation_status or "").upper()
    if status == STATUS_INACTIVE:
        return _candidate_response(
            **base_kwargs,
            eligible=False,
            reason="INACTIVE activation에서는 Catch-up Run을 생성할 수 없습니다.",
            candidate_scheduled_at=candidate_at,
            warnings=warnings,
        )

    return _candidate_response(
        **base_kwargs,
        eligible=True,
        reason="최근 누락된 스케줄 실행 후보가 있습니다.",
        candidate_scheduled_at=candidate_at,
        warnings=warnings,
    )


async def enqueue_schedule_catchup_run(
    db: AsyncSession,
    *,
    pipeline_id: str,
    activation_id: str,
    candidate_scheduled_at: str | datetime,
    reason: str,
    confirm_activation_id: str,
    actor_type: str = ACTOR_USER,
    actor_id: str = "mock_admin",
) -> dict[str, Any]:
    """Create one PENDING catch-up run. Does not execute or alter next_due_at."""
    settings = get_settings()
    if not bool(settings.vp_schedule_catchup_enabled):
        raise ScheduleCatchupError(
            "SCHEDULE_CATCHUP_DISABLED",
            "Schedule catch-up is disabled by configuration.",
            http_status=409,
        )

    max_batch = max(1, int(settings.vp_schedule_catchup_max_batch or 1))
    if max_batch != 1:
        # PoC hard-limit: only single-run enqueue is supported.
        max_batch = 1

    confirm = str(confirm_activation_id or "").strip()
    if confirm != activation_id:
        raise ScheduleCatchupError(
            "SCHEDULE_CATCHUP_CONFIRM_MISMATCH",
            "confirm_activation_id must match the path activation_id.",
            http_status=400,
        )

    reason_text = str(reason or "").strip()
    if len(reason_text) < 5 or len(reason_text) > 300:
        raise ScheduleCatchupError(
            "SCHEDULE_CATCHUP_REASON_REQUIRED",
            "reason must be between 5 and 300 characters.",
            http_status=400,
        )

    requested_at = _parse_dt(candidate_scheduled_at)
    if requested_at is None:
        raise ScheduleCatchupError(
            "SCHEDULE_CATCHUP_NOT_ELIGIBLE",
            "candidate_scheduled_at is invalid.",
            http_status=400,
        )

    activation = await _load_activation(db, pipeline_id, activation_id)
    status = str(activation.activation_status or "").upper()
    if status == STATUS_INACTIVE:
        raise ScheduleCatchupError(
            "SCHEDULE_CATCHUP_NOT_ELIGIBLE",
            "INACTIVE activation cannot enqueue catch-up runs.",
            http_status=409,
        )
    if status not in {STATUS_ACTIVE, STATUS_PAUSED}:
        raise ScheduleCatchupError(
            "SCHEDULE_CATCHUP_NOT_ELIGIBLE",
            f"Catch-up is not allowed for activation_status={status}.",
            http_status=409,
        )

    candidate = await get_schedule_catchup_candidate(
        db, pipeline_id=pipeline_id, activation_id=activation_id
    )
    if not candidate.get("eligible"):
        raise ScheduleCatchupError(
            "SCHEDULE_CATCHUP_NOT_ELIGIBLE",
            str(candidate.get("reason") or "Catch-up candidate is not eligible."),
            http_status=409,
        )

    expected_at = _parse_dt(candidate.get("candidate_scheduled_at"))
    if expected_at is None or expected_at.replace(microsecond=0) != requested_at.replace(
        microsecond=0
    ):
        raise ScheduleCatchupError(
            "SCHEDULE_CATCHUP_NOT_ELIGIBLE",
            "candidate_scheduled_at does not match the current eligible candidate.",
            http_status=409,
        )

    window_hours = max(1, int(settings.vp_schedule_catchup_max_window_hours or 24))
    now = utc_now()
    if expected_at < now - timedelta(hours=window_hours):
        raise ScheduleCatchupError(
            "SCHEDULE_CATCHUP_WINDOW_EXCEEDED",
            f"Catch-up window exceeded ({window_hours}h).",
            http_status=409,
        )

    if await _pipeline_has_active_run(db, pipeline_id):
        raise ScheduleCatchupError(
            "SCHEDULE_CATCHUP_ACTIVE_RUN_EXISTS",
            "An active PENDING/RUNNING run exists for this pipeline.",
            http_status=409,
        )

    if await _has_run_for_scheduled_at(
        db,
        pipeline_id=pipeline_id,
        activation_id=activation_id,
        scheduled_at=expected_at,
    ):
        raise ScheduleCatchupError(
            "SCHEDULE_CATCHUP_DUPLICATE_RUN_EXISTS",
            "A run already exists for this scheduled_at.",
            http_status=409,
        )

    mat_row = (
        await db.execute(
            select(VisualPipelineMaterializationResult).where(
                VisualPipelineMaterializationResult.materialization_result_id
                == activation.materialization_result_id,
                VisualPipelineMaterializationResult.pipeline_id == pipeline_id,
            )
        )
    ).scalar_one_or_none()
    if mat_row is None or str(mat_row.materialization_status or "").upper() != "SUCCESS":
        raise ScheduleCatchupError(
            "SCHEDULE_CATCHUP_NOT_ELIGIBLE",
            "Materialization snapshot is missing or not SUCCESS.",
            http_status=409,
        )

    new_id = _new_visual_run_id()
    dedup = _catchup_dedup_key(activation_id, expected_at, new_id)
    objects = dict(mat_row.objects_json or {})
    request_store = {
        "mode": SCHEDULED_MODE,
        "trigger_type": "CATCHUP",
        "activation_id": activation.activation_id,
        "r10_schedule_id": activation.r10_schedule_id,
        "cron_expression": activation.cron_expression,
        "timezone": activation.timezone or DEFAULT_TZ,
        "scheduled_for": _iso(expected_at),
        "executor": EXECUTOR_WORKER,
        "params": {},
        "resolved_objects": {
            "operation_id": objects.get("operation_id"),
            "write_policy_id": objects.get("write_policy_id"),
            "transform_config_id": objects.get("transform_config_id"),
        },
        "catchup": {
            "catchup_of_activation_id": activation_id,
            "catchup_for_scheduled_at": _iso(expected_at),
            "reason": reason_text[:300],
            "requested_by": actor_id,
        },
        "enqueued_by": "schedule_catchup_api",
    }

    # Audit fail-close before insert.
    try:
        audit_row = await record_visual_pipeline_audit_event(
            db,
            event_type=EVENT_SCHEDULE_CATCHUP_ENQUEUED,
            event_source=SOURCE_API,
            action_status=STATUS_SUCCESS,
            pipeline_id=pipeline_id,
            visual_run_id=new_id,
            activation_id=activation_id,
            materialization_result_id=activation.materialization_result_id,
            r10_schedule_id=activation.r10_schedule_id,
            actor_type=actor_type,
            actor_id=actor_id,
            reason=reason_text[:200],
            before_json={
                "activation_status": status,
                "next_due_at": _iso(activation.next_due_at),
                "last_due_at": _iso(activation.last_due_at),
                "last_skip_reason": activation.last_skip_reason,
            },
            after_json={
                "catchup_visual_run_id": new_id,
                "run_status": "PENDING",
                "catchup_for_scheduled_at": _iso(expected_at),
            },
            metadata_json={
                "catchup_of_activation_id": activation_id,
                "catchup_for_scheduled_at": _iso(expected_at),
                "max_batch": max_batch,
            },
            fail_open=False,
        )
    except Exception as exc:  # noqa: BLE001
        raise ScheduleCatchupError(
            "SCHEDULE_CATCHUP_AUDIT_REQUIRED_FAILED",
            "Audit recording failed; catch-up run was not created.",
            http_status=409,
        ) from exc
    if audit_row is None:
        raise ScheduleCatchupError(
            "SCHEDULE_CATCHUP_AUDIT_REQUIRED_FAILED",
            "Audit recording failed; catch-up run was not created.",
            http_status=409,
        )

    next_due_before = activation.next_due_at
    run_row = VisualPipelineRun(
        visual_run_id=new_id,
        pipeline_id=pipeline_id,
        compile_result_id=activation.compile_result_id or mat_row.compile_result_id,
        materialization_result_id=mat_row.materialization_result_id,
        graph_version_hash=mat_row.graph_version_hash,
        load_run_id=None,
        mode=SCHEDULED_MODE,
        execution_mode=EXECUTION_BACKGROUND,
        run_status="PENDING",
        request_json=request_store,
        result_json={},
        issues_json=[],
        error_message=None,
        activation_id=activation.activation_id,
        r10_schedule_id=activation.r10_schedule_id,
        scheduled_for=expected_at,
        triggered_at=now,
        dedup_key=dedup,
        claimed_at=None,
        claimed_by=None,
        locked_until=None,
        heartbeat_at=None,
        attempt_count=0,
        catchup_of_activation_id=activation_id,
        catchup_for_scheduled_at=expected_at,
        catchup_reason=reason_text[:300],
        catchup_requested_by=actor_id[:120],
        catchup_requested_at=now,
        started_at=None,
        finished_at=None,
        created_at=now,
    )
    db.add(run_row)
    await db.flush()

    await emit_run_event_safe(
        db,
        visual_run_id=new_id,
        pipeline_id=pipeline_id,
        event_type=EVENT_RUN_CREATED,
        message="Catch-up run enqueued (PENDING)",
        metadata_json={
            "mode": SCHEDULED_MODE,
            "trigger_type": "CATCHUP",
            "catchup_of_activation_id": activation_id,
            "catchup_for_scheduled_at": _iso(expected_at),
            "catchup_reason": reason_text[:300],
        },
    )
    await emit_run_event_safe(
        db,
        visual_run_id=new_id,
        pipeline_id=pipeline_id,
        event_type=EVENT_SCHEDULE_CATCHUP_ENQUEUED,
        message="Schedule catch-up enqueued",
        metadata_json={
            "activation_id": activation_id,
            "catchup_for_scheduled_at": _iso(expected_at),
            "reason": reason_text[:300],
        },
    )

    await db.commit()
    await db.refresh(run_row)
    await db.refresh(activation)

    # Guarantees: next_due_at must not change.
    if activation.next_due_at != next_due_before:
        logger.error(
            "catch-up unexpectedly mutated next_due_at activation_id=%s before=%s after=%s",
            activation_id,
            next_due_before,
            activation.next_due_at,
        )

    return {
        "pipeline_id": pipeline_id,
        "activation_id": activation_id,
        "catchup_visual_run_id": new_id,
        "run_status": "PENDING",
        "catchup_for_scheduled_at": _iso(expected_at),
        "reason": reason_text[:300],
        "poll_url": _poll_url(pipeline_id, new_id),
    }
