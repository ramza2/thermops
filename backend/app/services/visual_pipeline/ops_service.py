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


async def mark_stuck_runs_failed(
    db: AsyncSession,
    *,
    apply: bool = False,
    pending_age_seconds: int = DEFAULT_PENDING_AGE_SECONDS,
    running_lock_grace_seconds: int = DEFAULT_RUNNING_LOCK_GRACE_SECONDS,
    limit: int = DEFAULT_STUCK_LIMIT,
    reason: str = "manual ops cleanup",
) -> dict[str, Any]:
    """Dry-run or apply FAILED for eligible stuck runs. Does not touch activations."""
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
    }
    if not apply or not targets:
        return result

    updated: list[dict[str, Any]] = []
    for item in targets:
        rid = item["visual_run_id"]
        row = (
            await db.execute(
                select(VisualPipelineRun).where(VisualPipelineRun.visual_run_id == rid)
            )
        ).scalar_one_or_none()
        if row is None:
            continue
        status = str(row.run_status or "").upper()
        if status in {"SUCCESS", "FAILED", "PARTIAL", "CANCELLED"}:
            continue
        if status == "PENDING" and item["reason"] != REASON_PENDING_TOO_OLD:
            continue
        if status == "RUNNING":
            if item["reason"] != REASON_RUNNING_LOCK_EXPIRED:
                continue
            if row.locked_until is None:
                continue
        _apply_mark_failed(
            row,
            stuck_reason=str(item["reason"]),
            reason=reason,
            now=now,
        )
        updated.append(
            {
                "visual_run_id": row.visual_run_id,
                "pipeline_id": row.pipeline_id,
                "previous_status": status,
                "reason": item["reason"],
                "run_status": "FAILED",
            }
        )

    if updated:
        await db.commit()
    result["updated"] = updated
    result["updated_count"] = len(updated)
    return result
