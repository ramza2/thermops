"""R11-S7-10 Visual Pipeline ops — read-only summary + stuck cleanup helpers.

Does not call run_load, create runs, or mutate activations.
Process liveness is not checked; Docker health is operator-side.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.time import utc_now
from app.models.entities import VisualPipelineRun, VisualPipelineScheduleActivation
from app.services.visual_pipeline.audit_service import (
    ACTOR_CLI,
    ACTOR_USER,
    SOURCE_API,
    SOURCE_CLI,
    record_ops_mark_failed_batch_event,
    record_ops_mark_failed_run_event,
)
from app.services.visual_pipeline.manual_run_service import (
    _clear_run_lease,
    _iso,
    _issue,
    resolve_vp_run_executor,
)

DEFAULT_PENDING_AGE_SECONDS = 600
DEFAULT_RUNNING_LOCK_GRACE_SECONDS = 0
DEFAULT_STUCK_LIMIT = 50
DEFAULT_RECENT_FAILURES = 10
DEFAULT_HEARTBEAT_STALE_HINT_SECONDS = 600

REASON_PENDING_TOO_OLD = "PENDING_TOO_OLD"
REASON_RUNNING_LOCK_EXPIRED = "RUNNING_LOCK_EXPIRED"

RUN_STATUSES = ("PENDING", "RUNNING", "SUCCESS", "FAILED", "PARTIAL", "CANCELLED")
ACTIVATION_STATUSES = ("ACTIVE", "PAUSED", "INACTIVE", "ERROR")

OPS_ISSUE_CODE = "OPS_CLEANUP_MARKED_FAILED"

CODE_NOT_ELIGIBLE = "RUN_MARK_FAILED_NOT_ELIGIBLE"
CODE_AUDIT_REQUIRED_FAILED = "RUN_MARK_FAILED_AUDIT_REQUIRED_FAILED"
CODE_CONFIRM_MISMATCH = "RUN_MARK_FAILED_CONFIRM_MISMATCH"
CODE_REASON_INVALID = "RUN_MARK_FAILED_REASON_INVALID"
CODE_RUN_NOT_FOUND = "VISUAL_PIPELINE_RUN_NOT_FOUND"
CODE_ADMIN_ACTIONS_DISABLED = "VP_ADMIN_ACTIONS_DISABLED"

MIN_MARK_FAILED_REASON_LEN = 5
MAX_MARK_FAILED_REASON_LEN = 200


class MarkFailedError(Exception):
    """Raised for mark-failed precondition / fail-close failures."""

    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


def validate_mark_failed_reason(reason: str | None) -> str:
    text = str(reason or "").strip()
    if len(text) < MIN_MARK_FAILED_REASON_LEN or len(text) > MAX_MARK_FAILED_REASON_LEN:
        raise MarkFailedError(CODE_REASON_INVALID)
    return text


def evaluate_stuck_eligibility(
    row: VisualPipelineRun,
    *,
    now: Any,
    pending_age_seconds: int = DEFAULT_PENDING_AGE_SECONDS,
    running_lock_grace_seconds: int = DEFAULT_RUNNING_LOCK_GRACE_SECONDS,
) -> str | None:
    """Return stuck_reason if eligible, else None."""
    status = str(row.run_status or "").upper()
    pending_age = max(0, int(pending_age_seconds))
    lock_grace = max(0, int(running_lock_grace_seconds))
    pending_cutoff = now - timedelta(seconds=pending_age)
    lock_cutoff = now - timedelta(seconds=lock_grace)

    if status == "PENDING":
        if row.created_at is not None and row.created_at < pending_cutoff:
            return REASON_PENDING_TOO_OLD
        return None
    if status == "RUNNING":
        if row.locked_until is None:
            return None
        if row.locked_until < lock_cutoff:
            return REASON_RUNNING_LOCK_EXPIRED
        return None
    return None


def _worker_config(settings: Settings | None = None) -> dict[str, Any]:
    s = settings or get_settings()
    return {
        "run_executor": resolve_vp_run_executor(s.vp_run_executor),
        "schedule_activation_enabled": bool(s.vp_schedule_activation_enabled),
        "run_worker_enabled": bool(s.vp_run_worker_enabled),
        "schedule_worker_enabled": bool(s.vp_schedule_worker_enabled),
        "run_worker_mode": str(s.vp_run_worker_mode or "loop"),
        "schedule_worker_mode": str(s.vp_schedule_worker_mode or "loop"),
        "run_worker_poll_interval_seconds": int(s.vp_run_worker_poll_interval_seconds or 5),
        "run_worker_lock_ttl_seconds": int(s.vp_run_worker_lock_ttl_seconds or 120),
        "run_worker_max_batch_size": int(s.vp_run_worker_max_batch_size or 1),
        "schedule_worker_poll_interval_seconds": int(
            s.vp_schedule_worker_poll_interval_seconds or 30
        ),
        "schedule_worker_max_batch_size": int(s.vp_schedule_worker_max_batch_size or 10),
        "admin_actions_enabled": bool(s.vp_admin_actions_enabled),
    }


async def _status_counts(
    db: AsyncSession,
    model: type,
    status_column: Any,
    statuses: tuple[str, ...],
) -> dict[str, int]:
    rows = (
        await db.execute(select(status_column, func.count()).group_by(status_column))
    ).all()
    counts = {name: 0 for name in statuses}
    for status, count in rows:
        key = str(status or "").upper()
        if key in counts:
            counts[key] = int(count or 0)
        else:
            counts[key] = int(count or 0)
    return counts


def _age_seconds(now: Any, created_at: Any) -> int | None:
    if created_at is None:
        return None
    try:
        return max(0, int((now - created_at).total_seconds()))
    except TypeError:
        return None


def _stuck_item(row: VisualPipelineRun, *, reason: str, now: Any) -> dict[str, Any]:
    heartbeat_stale = False
    if row.heartbeat_at is not None:
        try:
            heartbeat_stale = row.heartbeat_at < now - timedelta(
                seconds=DEFAULT_HEARTBEAT_STALE_HINT_SECONDS
            )
        except TypeError:
            heartbeat_stale = False
    return {
        "visual_run_id": row.visual_run_id,
        "pipeline_id": row.pipeline_id,
        "mode": row.mode,
        "activation_id": row.activation_id,
        "scheduled_for": _iso(row.scheduled_for),
        "run_status": row.run_status,
        "created_at": _iso(row.created_at),
        "started_at": _iso(row.started_at),
        "locked_until": _iso(row.locked_until),
        "heartbeat_at": _iso(row.heartbeat_at),
        "claimed_by": row.claimed_by,
        "attempt_count": int(row.attempt_count or 0),
        "age_seconds": _age_seconds(now, row.created_at),
        "reason": reason,
        "heartbeat_stale_hint": heartbeat_stale,
    }


async def list_stuck_runs(
    db: AsyncSession,
    *,
    pending_age_seconds: int = DEFAULT_PENDING_AGE_SECONDS,
    running_lock_grace_seconds: int = DEFAULT_RUNNING_LOCK_GRACE_SECONDS,
    limit: int = DEFAULT_STUCK_LIMIT,
    now: Any | None = None,
) -> dict[str, Any]:
    """Return stuck PENDING/RUNNING rows. Read-only."""
    now = now or utc_now()
    pending_age = max(0, int(pending_age_seconds))
    lock_grace = max(0, int(running_lock_grace_seconds))
    lim = max(1, min(500, int(limit)))

    pending_cutoff = now - timedelta(seconds=pending_age)
    lock_cutoff = now - timedelta(seconds=lock_grace)

    pending_rows = (
        await db.execute(
            select(VisualPipelineRun)
            .where(
                VisualPipelineRun.run_status == "PENDING",
                VisualPipelineRun.created_at < pending_cutoff,
            )
            .order_by(VisualPipelineRun.created_at.asc())
            .limit(lim)
        )
    ).scalars().all()

    running_rows = (
        await db.execute(
            select(VisualPipelineRun)
            .where(
                VisualPipelineRun.run_status == "RUNNING",
                VisualPipelineRun.locked_until.is_not(None),
                VisualPipelineRun.locked_until < lock_cutoff,
            )
            .order_by(VisualPipelineRun.locked_until.asc())
            .limit(lim)
        )
    ).scalars().all()

    items: list[dict[str, Any]] = []
    for row in pending_rows:
        items.append(_stuck_item(row, reason=REASON_PENDING_TOO_OLD, now=now))
    for row in running_rows:
        items.append(_stuck_item(row, reason=REASON_RUNNING_LOCK_EXPIRED, now=now))

    # Prefer oldest first across reasons; trim to limit
    items.sort(key=lambda x: (x.get("created_at") or "", x.get("visual_run_id") or ""))
    items = items[:lim]

    return {
        "items": items,
        "total": len(items),
        "criteria": {
            "pending_age_seconds": pending_age,
            "running_lock_grace_seconds": lock_grace,
            "limit": lim,
        },
    }


async def count_stuck(
    db: AsyncSession,
    *,
    pending_age_seconds: int = DEFAULT_PENDING_AGE_SECONDS,
    running_lock_grace_seconds: int = DEFAULT_RUNNING_LOCK_GRACE_SECONDS,
    now: Any | None = None,
) -> dict[str, int]:
    now = now or utc_now()
    pending_cutoff = now - timedelta(seconds=max(0, int(pending_age_seconds)))
    lock_cutoff = now - timedelta(seconds=max(0, int(running_lock_grace_seconds)))

    pending_count = (
        await db.execute(
            select(func.count())
            .select_from(VisualPipelineRun)
            .where(
                VisualPipelineRun.run_status == "PENDING",
                VisualPipelineRun.created_at < pending_cutoff,
            )
        )
    ).scalar_one()
    running_count = (
        await db.execute(
            select(func.count())
            .select_from(VisualPipelineRun)
            .where(
                VisualPipelineRun.run_status == "RUNNING",
                VisualPipelineRun.locked_until.is_not(None),
                VisualPipelineRun.locked_until < lock_cutoff,
            )
        )
    ).scalar_one()
    return {
        "pending_older_than_threshold": int(pending_count or 0),
        "running_lock_expired": int(running_count or 0),
    }


async def get_ops_summary(
    db: AsyncSession,
    *,
    pending_age_seconds: int = DEFAULT_PENDING_AGE_SECONDS,
    running_lock_grace_seconds: int = DEFAULT_RUNNING_LOCK_GRACE_SECONDS,
    recent_failures_limit: int = DEFAULT_RECENT_FAILURES,
) -> dict[str, Any]:
    """Aggregate ops view from settings + DB. Read-only."""
    settings = get_settings()
    now = utc_now()

    run_counts = await _status_counts(
        db, VisualPipelineRun, VisualPipelineRun.run_status, RUN_STATUSES
    )
    act_counts = await _status_counts(
        db,
        VisualPipelineScheduleActivation,
        VisualPipelineScheduleActivation.activation_status,
        ACTIVATION_STATUSES,
    )
    stuck = await count_stuck(
        db,
        pending_age_seconds=pending_age_seconds,
        running_lock_grace_seconds=running_lock_grace_seconds,
        now=now,
    )

    recent_fail_rows = (
        await db.execute(
            select(VisualPipelineRun)
            .where(VisualPipelineRun.run_status == "FAILED")
            .order_by(VisualPipelineRun.finished_at.desc().nullslast())
            .limit(max(1, min(50, int(recent_failures_limit))))
        )
    ).scalars().all()
    recent_failures = [
        {
            "visual_run_id": row.visual_run_id,
            "pipeline_id": row.pipeline_id,
            "mode": row.mode,
            "finished_at": _iso(row.finished_at),
            "error_message": row.error_message,
            "activation_id": row.activation_id,
        }
        for row in recent_fail_rows
    ]

    max_claimed = (
        await db.execute(select(func.max(VisualPipelineRun.claimed_at)))
    ).scalar_one()
    max_heartbeat = (
        await db.execute(select(func.max(VisualPipelineRun.heartbeat_at)))
    ).scalar_one()
    max_triggered = (
        await db.execute(
            select(func.max(VisualPipelineScheduleActivation.last_triggered_at))
        )
    ).scalar_one()
    max_skip = (
        await db.execute(select(func.max(VisualPipelineScheduleActivation.last_skip_at)))
    ).scalar_one()

    return {
        "run_status_counts": run_counts,
        "activation_status_counts": act_counts,
        "worker_config": _worker_config(settings),
        "stuck_summary": stuck,
        "stuck_criteria": {
            "pending_age_seconds": max(0, int(pending_age_seconds)),
            "running_lock_grace_seconds": max(0, int(running_lock_grace_seconds)),
        },
        "activity_hints": {
            "latest_claimed_at": _iso(max_claimed),
            "latest_heartbeat_at": _iso(max_heartbeat),
            "latest_last_triggered_at": _iso(max_triggered),
            "latest_last_skip_at": _iso(max_skip),
        },
        "recent_failures": recent_failures,
        "generated_at": _iso(now),
    }


def _apply_mark_failed(
    row: VisualPipelineRun,
    *,
    stuck_reason: str,
    reason: str,
    now: Any,
) -> None:
    msg = f"Marked failed by ops cleanup: {reason}"
    row.run_status = "FAILED"
    row.finished_at = now
    row.error_message = msg[:500]
    issues = list(row.issues_json or [])
    issues.append(
        _issue(
            OPS_ISSUE_CODE,
            msg,
            step_id="ops_cleanup",
            details={"stuck_reason": stuck_reason, "ops_reason": reason},
        )
    )
    row.issues_json = issues
    result = dict(row.result_json or {})
    summary = dict(result.get("summary") or {})
    summary.update(
        {
            "ops_cleanup": True,
            "stuck_reason": stuck_reason,
            "marked_failed_at": _iso(now),
        }
    )
    result["summary"] = summary
    row.result_json = result
    _clear_run_lease(row)
    # _clear_run_lease sets heartbeat_at=now and locked_until=null


async def _mark_one_run_failed_fail_close(
    db: AsyncSession,
    row: VisualPipelineRun,
    *,
    stuck_reason: str,
    reason: str,
    now: Any,
    criteria: dict[str, Any] | None,
    event_source: str,
    actor_type: str,
    actor_id: str,
    trigger: str,
    confirm_visual_run_id: str | None = None,
) -> dict[str, Any]:
    """Audit (fail-close) then mutate. Caller owns commit/rollback."""
    before_status = str(row.run_status or "").upper()
    before_locked_until = row.locked_until
    before_heartbeat_at = row.heartbeat_at
    before_attempt_count = int(row.attempt_count or 0)
    # Build after message preview for audit after_json
    preview_msg = f"Marked failed by ops cleanup: {reason}"[:500]
    try:
        audit_row = await record_ops_mark_failed_run_event(
            db,
            pipeline_id=row.pipeline_id,
            visual_run_id=row.visual_run_id,
            activation_id=row.activation_id,
            stuck_reason=stuck_reason,
            reason=reason,
            before_status=before_status,
            before_locked_until=before_locked_until,
            before_heartbeat_at=before_heartbeat_at,
            before_attempt_count=before_attempt_count,
            finished_at=now,
            error_message=preview_msg,
            event_source=event_source,
            actor_type=actor_type,
            actor_id=actor_id,
            trigger=trigger,
            criteria=criteria,
            confirm_visual_run_id=confirm_visual_run_id,
            fail_open=False,
        )
    except Exception as exc:  # noqa: BLE001
        raise MarkFailedError(CODE_AUDIT_REQUIRED_FAILED) from exc

    if audit_row is None:
        raise MarkFailedError(CODE_AUDIT_REQUIRED_FAILED)

    _apply_mark_failed(
        row,
        stuck_reason=stuck_reason,
        reason=reason,
        now=now,
    )
    return {
        "visual_run_id": row.visual_run_id,
        "pipeline_id": row.pipeline_id,
        "previous_status": before_status,
        "run_status": "FAILED",
        "reason": reason,
        "stuck_reason": stuck_reason,
        "audit_id": audit_row.audit_id,
        "changed": True,
    }


async def mark_single_stuck_run_failed(
    db: AsyncSession,
    visual_run_id: str,
    *,
    reason: str,
    confirm_visual_run_id: str,
    pending_age_seconds: int = DEFAULT_PENDING_AGE_SECONDS,
    running_lock_grace_seconds: int = DEFAULT_RUNNING_LOCK_GRACE_SECONDS,
    require_admin_flag: bool = True,
) -> dict[str, Any]:
    """Admin API single-run mark-failed with fail-close audit."""
    if require_admin_flag and not get_settings().vp_admin_actions_enabled:
        raise MarkFailedError(CODE_ADMIN_ACTIONS_DISABLED)

    reason_text = validate_mark_failed_reason(reason)
    if str(confirm_visual_run_id or "").strip() != str(visual_run_id).strip():
        raise MarkFailedError(CODE_CONFIRM_MISMATCH)

    now = utc_now()
    criteria = {
        "pending_age_seconds": max(0, int(pending_age_seconds)),
        "running_lock_grace_seconds": max(0, int(running_lock_grace_seconds)),
    }
    row = (
        await db.execute(
            select(VisualPipelineRun)
            .where(VisualPipelineRun.visual_run_id == visual_run_id)
            .with_for_update()
        )
    ).scalar_one_or_none()
    if row is None:
        raise MarkFailedError(CODE_RUN_NOT_FOUND)

    stuck_reason = evaluate_stuck_eligibility(
        row,
        now=now,
        pending_age_seconds=pending_age_seconds,
        running_lock_grace_seconds=running_lock_grace_seconds,
    )
    if stuck_reason is None:
        raise MarkFailedError(CODE_NOT_ELIGIBLE)

    try:
        result = await _mark_one_run_failed_fail_close(
            db,
            row,
            stuck_reason=stuck_reason,
            reason=reason_text,
            now=now,
            criteria=criteria,
            event_source=SOURCE_API,
            actor_type=ACTOR_USER,
            actor_id="mock_admin",
            trigger="admin_api",
            confirm_visual_run_id=str(confirm_visual_run_id).strip(),
        )
        await db.commit()
        return result
    except MarkFailedError:
        await db.rollback()
        raise
    except Exception:
        await db.rollback()
        raise


async def mark_stuck_runs_failed(
    db: AsyncSession,
    *,
    apply: bool = False,
    pending_age_seconds: int = DEFAULT_PENDING_AGE_SECONDS,
    running_lock_grace_seconds: int = DEFAULT_RUNNING_LOCK_GRACE_SECONDS,
    limit: int = DEFAULT_STUCK_LIMIT,
    reason: str = "manual ops cleanup",
) -> dict[str, Any]:
    """Dry-run or apply FAILED for eligible stuck runs. Apply uses per-run fail-close."""
    now = utc_now()
    stuck = await list_stuck_runs(
        db,
        pending_age_seconds=pending_age_seconds,
        running_lock_grace_seconds=running_lock_grace_seconds,
        limit=limit,
        now=now,
    )
    targets = stuck["items"]
    result: dict[str, Any] = {
        "apply": bool(apply),
        "dry_run": not bool(apply),
        "reason": reason,
        "criteria": stuck["criteria"],
        "candidates": targets,
        "updated": [],
        "updated_count": 0,
        "audit_failed_count": 0,
        "skipped_due_to_audit_failure": [],
        "failed_ids": [],
    }

    if not apply:
        await record_ops_mark_failed_batch_event(
            db,
            apply=False,
            reason=reason,
            criteria=stuck["criteria"],
            target_count=len(targets),
            changed_count=0,
            audit_failed_count=0,
            fail_open=True,
        )
        await db.commit()
        return result

    updated: list[dict[str, Any]] = []
    audit_failed: list[str] = []
    for item in targets:
        rid = item["visual_run_id"]
        try:
            async with db.begin_nested():
                row = (
                    await db.execute(
                        select(VisualPipelineRun)
                        .where(VisualPipelineRun.visual_run_id == rid)
                        .with_for_update()
                    )
                ).scalar_one_or_none()
                if row is None:
                    continue
                stuck_reason = evaluate_stuck_eligibility(
                    row,
                    now=now,
                    pending_age_seconds=pending_age_seconds,
                    running_lock_grace_seconds=running_lock_grace_seconds,
                )
                if stuck_reason is None:
                    continue
                one = await _mark_one_run_failed_fail_close(
                    db,
                    row,
                    stuck_reason=stuck_reason,
                    reason=reason,
                    now=now,
                    criteria=stuck["criteria"],
                    event_source=SOURCE_CLI,
                    actor_type=ACTOR_CLI,
                    actor_id="cli",
                    trigger="cli",
                )
                updated.append(
                    {
                        "visual_run_id": one["visual_run_id"],
                        "pipeline_id": one["pipeline_id"],
                        "previous_status": one["previous_status"],
                        "reason": item.get("reason") or stuck_reason,
                        "run_status": "FAILED",
                        "audit_id": one["audit_id"],
                    }
                )
        except MarkFailedError as exc:
            if exc.code == CODE_AUDIT_REQUIRED_FAILED:
                audit_failed.append(rid)
                continue
            raise
        except Exception:
            audit_failed.append(rid)
            continue

    await record_ops_mark_failed_batch_event(
        db,
        apply=True,
        reason=reason,
        criteria=stuck["criteria"],
        target_count=len(targets),
        changed_count=len(updated),
        audit_failed_count=len(audit_failed),
        fail_open=True,
    )
    await db.commit()
    result["updated"] = updated
    result["updated_count"] = len(updated)
    result["audit_failed_count"] = len(audit_failed)
    result["skipped_due_to_audit_failure"] = list(audit_failed)
    result["failed_ids"] = list(audit_failed)
    return result
