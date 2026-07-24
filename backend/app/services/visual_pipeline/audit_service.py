"""R11-S7-13 Visual Pipeline Audit Log — record + read helpers.

Fail-open: audit write failures are logged and do not block main actions.
Does not store request_json/result_json wholesale; secret keys are redacted.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.time import utc_now
from app.models.entities import VisualPipelineAuditLog

logger = logging.getLogger(__name__)

EVENT_SCHEDULE_ACTIVATE = "SCHEDULE_ACTIVATE"
EVENT_SCHEDULE_DEACTIVATE = "SCHEDULE_DEACTIVATE"
EVENT_SCHEDULE_PAUSE = "SCHEDULE_PAUSE"
EVENT_SCHEDULE_RESUME = "SCHEDULE_RESUME"
EVENT_RUN_CANCELLED = "RUN_CANCELLED"
EVENT_RUN_MARK_FAILED_BY_OPS = "RUN_MARK_FAILED_BY_OPS"
EVENT_OPS_MARK_FAILED_DRY_RUN = "OPS_MARK_FAILED_DRY_RUN"
EVENT_OPS_MARK_FAILED_APPLY = "OPS_MARK_FAILED_APPLY"
EVENT_SCHEDULE_WORKER_SKIPPED_ACTIVE_RUN = "SCHEDULE_WORKER_SKIPPED_ACTIVE_RUN"

SOURCE_API = "API"
SOURCE_CLI = "CLI"
SOURCE_WORKER = "WORKER"
SOURCE_SYSTEM = "SYSTEM"
SOURCE_UI = "UI"

ACTOR_USER = "USER"
ACTOR_CLI = "CLI"
ACTOR_WORKER = "WORKER"
ACTOR_SYSTEM = "SYSTEM"

STATUS_SUCCESS = "SUCCESS"
STATUS_FAILED = "FAILED"
STATUS_DRY_RUN = "DRY_RUN"
STATUS_SKIPPED = "SKIPPED"

SECRET_KEY_RE = re.compile(
    r"(secret|token|password|credential|api[_-]?key|authorization)",
    re.IGNORECASE,
)
REDACTED = "***REDACTED***"

DEFAULT_AUDIT_LIST_LIMIT = 50
MAX_AUDIT_LIST_LIMIT = 200


def _new_audit_id() -> str:
    return f"VPAU-{uuid4().hex[:8].upper()}"


def _iso(dt: Any) -> str | None:
    if dt is None:
        return None
    text = dt.isoformat() if hasattr(dt, "isoformat") else str(dt)
    if text and not text.endswith("Z") and "+" not in text and "T" in text:
        return f"{text}Z"
    return text


def sanitize_audit_payload(value: Any) -> Any:
    """Recursively redact secret-like keys. Does not deep-copy request/result blobs."""
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for key, item in value.items():
            key_s = str(key)
            if SECRET_KEY_RE.search(key_s):
                out[key_s] = REDACTED
            else:
                out[key_s] = sanitize_audit_payload(item)
        return out
    if isinstance(value, list):
        return [sanitize_audit_payload(item) for item in value]
    if isinstance(value, tuple):
        return [sanitize_audit_payload(item) for item in value]
    return value


def _row_to_list_item(row: VisualPipelineAuditLog) -> dict[str, Any]:
    return {
        "audit_id": row.audit_id,
        "event_type": row.event_type,
        "event_source": row.event_source,
        "pipeline_id": row.pipeline_id,
        "visual_run_id": row.visual_run_id,
        "activation_id": row.activation_id,
        "actor_type": row.actor_type,
        "actor_id": row.actor_id,
        "action_status": row.action_status,
        "reason": row.reason,
        "created_at": _iso(row.created_at),
    }


def _row_to_detail(row: VisualPipelineAuditLog) -> dict[str, Any]:
    item = _row_to_list_item(row)
    item.update(
        {
            "materialization_result_id": row.materialization_result_id,
            "r10_schedule_id": row.r10_schedule_id,
            "request_id": row.request_id,
            "before_json": row.before_json,
            "after_json": row.after_json,
            "metadata_json": row.metadata_json,
        }
    )
    return item


async def record_visual_pipeline_audit_event(
    db: AsyncSession,
    *,
    event_type: str,
    event_source: str,
    action_status: str,
    pipeline_id: str | None = None,
    visual_run_id: str | None = None,
    activation_id: str | None = None,
    materialization_result_id: str | None = None,
    r10_schedule_id: str | None = None,
    actor_type: str | None = None,
    actor_id: str | None = None,
    request_id: str | None = None,
    reason: str | None = None,
    before_json: dict[str, Any] | None = None,
    after_json: dict[str, Any] | None = None,
    metadata_json: dict[str, Any] | None = None,
    fail_open: bool = True,
) -> VisualPipelineAuditLog | None:
    """Add audit row to the current session.

    fail_open=True (default): nested savepoint; failure logs warning and returns None.
    fail_open=False: direct flush; failure raises so caller can rollback (fail-close).
    """

    def _build_row() -> VisualPipelineAuditLog:
        return VisualPipelineAuditLog(
            audit_id=_new_audit_id(),
            event_type=str(event_type),
            event_source=str(event_source),
            pipeline_id=pipeline_id,
            visual_run_id=visual_run_id,
            activation_id=activation_id,
            materialization_result_id=materialization_result_id,
            r10_schedule_id=r10_schedule_id,
            actor_type=actor_type,
            actor_id=actor_id,
            action_status=str(action_status),
            request_id=request_id,
            reason=(str(reason)[:200] if reason else None),
            before_json=(
                sanitize_audit_payload(before_json) if before_json is not None else None
            ),
            after_json=(
                sanitize_audit_payload(after_json) if after_json is not None else None
            ),
            metadata_json=(
                sanitize_audit_payload(metadata_json) if metadata_json is not None else None
            ),
            created_at=utc_now(),
        )

    try:
        if fail_open:
            async with db.begin_nested():
                row = _build_row()
                db.add(row)
                await db.flush()
                return row
        row = _build_row()
        db.add(row)
        await db.flush()
        return row
    except Exception as exc:  # noqa: BLE001 — fail-open PoC / fail-close raise
        logger.warning(
            "audit write failed (fail_open=%s) event_type=%s: %s",
            fail_open,
            event_type,
            exc,
        )
        if not fail_open:
            raise
        return None


async def record_activation_event(
    db: AsyncSession,
    *,
    event_type: str,
    pipeline_id: str,
    activation_id: str,
    materialization_result_id: str | None = None,
    r10_schedule_id: str | None = None,
    before_status: str | None = None,
    after_status: str | None = None,
    before_next_due_at: Any = None,
    after_next_due_at: Any = None,
    paused_at: Any = None,
    resumed_at: Any = None,
    metadata_json: dict[str, Any] | None = None,
) -> VisualPipelineAuditLog | None:
    after: dict[str, Any] = {
        "activation_status": after_status,
        "next_due_at": _iso(after_next_due_at),
    }
    if paused_at is not None:
        after["paused_at"] = _iso(paused_at)
    if resumed_at is not None:
        after["resumed_at"] = _iso(resumed_at)
    return await record_visual_pipeline_audit_event(
        db,
        event_type=event_type,
        event_source=SOURCE_API,
        action_status=STATUS_SUCCESS,
        pipeline_id=pipeline_id,
        activation_id=activation_id,
        materialization_result_id=materialization_result_id,
        r10_schedule_id=r10_schedule_id,
        actor_type=ACTOR_USER,
        actor_id="mock_admin",
        before_json={
            "activation_status": before_status,
            "next_due_at": _iso(before_next_due_at),
        },
        after_json=after,
        metadata_json=metadata_json,
    )


async def record_run_cancel_event(
    db: AsyncSession,
    *,
    pipeline_id: str,
    visual_run_id: str,
    activation_id: str | None = None,
    finished_at: Any = None,
) -> VisualPipelineAuditLog | None:
    return await record_visual_pipeline_audit_event(
        db,
        event_type=EVENT_RUN_CANCELLED,
        event_source=SOURCE_API,
        action_status=STATUS_SUCCESS,
        pipeline_id=pipeline_id,
        visual_run_id=visual_run_id,
        activation_id=activation_id,
        actor_type=ACTOR_USER,
        actor_id="mock_admin",
        before_json={"run_status": "PENDING"},
        after_json={"run_status": "CANCELLED", "finished_at": _iso(finished_at)},
    )


async def record_ops_mark_failed_batch_event(
    db: AsyncSession,
    *,
    apply: bool,
    reason: str,
    criteria: dict[str, Any] | None,
    target_count: int,
    changed_count: int,
    audit_failed_count: int = 0,
    fail_open: bool = True,
) -> VisualPipelineAuditLog | None:
    event_type = EVENT_OPS_MARK_FAILED_APPLY if apply else EVENT_OPS_MARK_FAILED_DRY_RUN
    action_status = STATUS_SUCCESS if apply else STATUS_DRY_RUN
    return await record_visual_pipeline_audit_event(
        db,
        event_type=event_type,
        event_source=SOURCE_CLI,
        action_status=action_status,
        actor_type=ACTOR_CLI,
        actor_id="cli",
        reason=reason,
        metadata_json={
            "criteria": criteria or {},
            "target_count": int(target_count),
            "changed_count": int(changed_count),
            "audit_failed_count": int(audit_failed_count),
        },
        fail_open=fail_open,
    )


async def record_ops_mark_failed_run_event(
    db: AsyncSession,
    *,
    pipeline_id: str,
    visual_run_id: str,
    activation_id: str | None,
    stuck_reason: str,
    reason: str,
    before_status: str,
    before_locked_until: Any = None,
    before_heartbeat_at: Any = None,
    before_attempt_count: int | None = None,
    finished_at: Any = None,
    error_message: str | None = None,
    event_source: str = SOURCE_CLI,
    actor_type: str = ACTOR_CLI,
    actor_id: str = "cli",
    trigger: str = "cli",
    criteria: dict[str, Any] | None = None,
    confirm_visual_run_id: str | None = None,
    fail_open: bool = False,
) -> VisualPipelineAuditLog | None:
    """Record per-run mark-failed audit. Default fail_open=False (S7-14 fail-close)."""
    meta: dict[str, Any] = {
        "stuck_reason": stuck_reason,
        "trigger": trigger,
    }
    if criteria is not None:
        meta["criteria"] = criteria
    if confirm_visual_run_id is not None:
        meta["confirm_visual_run_id"] = confirm_visual_run_id
    before: dict[str, Any] = {
        "run_status": before_status,
        "locked_until": _iso(before_locked_until),
        "heartbeat_at": _iso(before_heartbeat_at),
    }
    if before_attempt_count is not None:
        before["attempt_count"] = int(before_attempt_count)
    return await record_visual_pipeline_audit_event(
        db,
        event_type=EVENT_RUN_MARK_FAILED_BY_OPS,
        event_source=event_source,
        action_status=STATUS_SUCCESS,
        pipeline_id=pipeline_id,
        visual_run_id=visual_run_id,
        activation_id=activation_id,
        actor_type=actor_type,
        actor_id=actor_id,
        reason=reason,
        before_json=before,
        after_json={
            "run_status": "FAILED",
            "finished_at": _iso(finished_at),
            "error_message": error_message,
        },
        metadata_json=meta,
        fail_open=fail_open,
    )


async def record_schedule_worker_skip_event(
    db: AsyncSession,
    *,
    worker_id: str,
    pipeline_id: str,
    activation_id: str,
    r10_schedule_id: str | None,
    scheduled_for: Any,
    before_missed_count: int,
    after_missed_count: int,
    before_next_due_at: Any,
    after_next_due_at: Any,
    last_skip_at: Any = None,
    active_run_id: str | None = None,
) -> VisualPipelineAuditLog | None:
    meta: dict[str, Any] = {
        "scheduled_for": _iso(scheduled_for),
        "last_skip_at": _iso(last_skip_at),
        "last_skip_reason": "ACTIVE_RUN_EXISTS",
    }
    if active_run_id:
        meta["active_run_id"] = active_run_id
    return await record_visual_pipeline_audit_event(
        db,
        event_type=EVENT_SCHEDULE_WORKER_SKIPPED_ACTIVE_RUN,
        event_source=SOURCE_WORKER,
        action_status=STATUS_SKIPPED,
        pipeline_id=pipeline_id,
        activation_id=activation_id,
        r10_schedule_id=r10_schedule_id,
        actor_type=ACTOR_WORKER,
        actor_id=worker_id[:120] if worker_id else "vp-schedule-worker",
        reason="ACTIVE_RUN_EXISTS",
        before_json={
            "missed_count": int(before_missed_count),
            "next_due_at": _iso(before_next_due_at),
        },
        after_json={
            "missed_count": int(after_missed_count),
            "next_due_at": _iso(after_next_due_at),
        },
        metadata_json=meta,
    )


def _parse_dt(value: str | datetime | None) -> datetime | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.replace(tzinfo=None) if value.tzinfo else value
    text = str(value).strip().replace("Z", "")
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


async def list_audit_logs(
    db: AsyncSession,
    *,
    event_type: str | None = None,
    pipeline_id: str | None = None,
    visual_run_id: str | None = None,
    activation_id: str | None = None,
    created_from: str | datetime | None = None,
    created_to: str | datetime | None = None,
    limit: int = DEFAULT_AUDIT_LIST_LIMIT,
) -> dict[str, Any]:
    lim = max(1, min(MAX_AUDIT_LIST_LIMIT, int(limit or DEFAULT_AUDIT_LIST_LIMIT)))
    filters = []
    if event_type:
        filters.append(VisualPipelineAuditLog.event_type == str(event_type).strip())
    if pipeline_id:
        filters.append(VisualPipelineAuditLog.pipeline_id == str(pipeline_id).strip())
    if visual_run_id:
        filters.append(VisualPipelineAuditLog.visual_run_id == str(visual_run_id).strip())
    if activation_id:
        filters.append(VisualPipelineAuditLog.activation_id == str(activation_id).strip())
    cf = _parse_dt(created_from)
    ct = _parse_dt(created_to)
    if cf is not None:
        filters.append(VisualPipelineAuditLog.created_at >= cf)
    if ct is not None:
        filters.append(VisualPipelineAuditLog.created_at <= ct)

    count_q = select(func.count()).select_from(VisualPipelineAuditLog)
    list_q = select(VisualPipelineAuditLog)
    if filters:
        count_q = count_q.where(*filters)
        list_q = list_q.where(*filters)

    total = int((await db.execute(count_q)).scalar_one() or 0)
    rows = (
        await db.execute(
            list_q.order_by(VisualPipelineAuditLog.created_at.desc()).limit(lim)
        )
    ).scalars().all()

    return {
        "items": [_row_to_list_item(row) for row in rows],
        "total": total,
        "criteria": {
            "event_type": event_type,
            "pipeline_id": pipeline_id,
            "visual_run_id": visual_run_id,
            "activation_id": activation_id,
            "created_from": _iso(cf) if cf else created_from,
            "created_to": _iso(ct) if ct else created_to,
            "limit": lim,
        },
    }


async def get_audit_log(db: AsyncSession, audit_id: str) -> dict[str, Any] | None:
    row = (
        await db.execute(
            select(VisualPipelineAuditLog).where(
                VisualPipelineAuditLog.audit_id == audit_id
            )
        )
    ).scalar_one_or_none()
    if row is None:
        return None
    return _row_to_detail(row)
