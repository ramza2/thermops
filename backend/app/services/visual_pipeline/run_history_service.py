"""R11-S8-2 Visual Pipeline Run History — read-only list/detail over tb_visual_pipeline_run.

SELECT only. No insert/update/delete/commit. No migration / event table.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entities import VisualPipelineRun
from app.services.visual_pipeline.visual_pipeline_service import _get_visual_definition

ALLOWED_RUN_STATUSES = frozenset(
    {"PENDING", "RUNNING", "SUCCESS", "PARTIAL", "FAILED", "CANCELLED"}
)
ALLOWED_MODES = frozenset({"MANUAL", "SCHEDULED"})


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.isoformat()


def _issues_count(issues_json: Any) -> int:
    if isinstance(issues_json, list):
        return len(issues_json)
    return 0


def _result_summary(row: VisualPipelineRun) -> dict[str, Any] | None:
    result_json = dict(row.result_json or {})
    summary = result_json.get("summary") if isinstance(result_json.get("summary"), dict) else {}
    if not summary:
        return None
    return {
        "target_table": summary.get("target_table"),
        "operation_id": summary.get("operation_id"),
        "write_policy_id": summary.get("write_policy_id"),
        "transform_config_id": summary.get("transform_config_id"),
        "fetched_count": summary.get("fetched_count"),
        "inserted_count": summary.get("inserted_count"),
        "updated_count": summary.get("updated_count"),
        "skipped_count": summary.get("skipped_count"),
        "failed_count": summary.get("failed_count"),
        "cancelled": summary.get("cancelled"),
        "cancel_phase": summary.get("cancel_phase"),
    }


def _poll_url(pipeline_id: str, visual_run_id: str) -> str:
    return f"/api/v1/visual-pipelines/{pipeline_id}/runs/{visual_run_id}"


def _parse_dt(raw: str | None, *, field: str) -> datetime | None:
    if raw is None or str(raw).strip() == "":
        return None
    text = str(raw).strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(text)
    except ValueError as exc:
        raise ValueError(f"INVALID_{field.upper()}") from exc


def summarize_run_row(row: VisualPipelineRun) -> dict[str, Any]:
    """List-item shape (compatible with existing Studio latest list)."""
    summary = _result_summary(row) or {}
    # Keep legacy result_summary keys even when empty dict (previous behavior).
    legacy_summary = {
        "target_table": summary.get("target_table"),
        "inserted_count": summary.get("inserted_count"),
        "updated_count": summary.get("updated_count"),
        "skipped_count": summary.get("skipped_count"),
        "failed_count": summary.get("failed_count"),
    }
    return {
        "visual_run_id": row.visual_run_id,
        "pipeline_id": row.pipeline_id,
        "mode": row.mode,
        "execution_mode": row.execution_mode,
        "run_status": row.run_status,
        "compile_result_id": row.compile_result_id,
        "materialization_result_id": row.materialization_result_id,
        "graph_version_hash": row.graph_version_hash,
        "load_run_id": row.load_run_id,
        "activation_id": row.activation_id,
        "r10_schedule_id": row.r10_schedule_id,
        "scheduled_for": _iso(row.scheduled_for),
        "triggered_at": _iso(row.triggered_at),
        "started_at": _iso(row.started_at),
        "finished_at": _iso(row.finished_at),
        "created_at": _iso(row.created_at),
        "claimed_by": row.claimed_by,
        "claimed_at": _iso(row.claimed_at),
        "locked_until": _iso(row.locked_until),
        "heartbeat_at": _iso(row.heartbeat_at),
        "attempt_count": int(row.attempt_count or 0),
        "error_message": row.error_message,
        "issues_count": _issues_count(row.issues_json),
        "result_summary": legacy_summary,
        "retry_of_run_id": row.retry_of_run_id,
        "retry_attempt": int(row.retry_attempt or 0),
        "retry_reason": row.retry_reason,
        "retry_mode": row.retry_mode,
        "cancel_requested": row.cancel_requested_at is not None,
        "cancel_requested_at": _iso(row.cancel_requested_at),
        "cancel_acknowledged_at": _iso(row.cancel_acknowledged_at),
        "cancel_requested_by": row.cancel_requested_by,
        "cancel_reason": row.cancel_reason,
        "catchup_of_activation_id": row.catchup_of_activation_id,
        "catchup_for_scheduled_at": _iso(row.catchup_for_scheduled_at),
        "catchup_reason": row.catchup_reason,
        "catchup_requested_by": row.catchup_requested_by,
        "catchup_requested_at": _iso(row.catchup_requested_at),
    }


def detail_run_row(row: VisualPipelineRun) -> dict[str, Any]:
    """Detail shape: existing Manual Run fields + additive history fields."""
    result_json = dict(row.result_json or {})
    summary = result_json.get("summary") if isinstance(result_json.get("summary"), dict) else None
    if summary is not None and not summary:
        summary = None
    if str(row.run_status or "").upper() in {"PENDING", "RUNNING"} and not summary:
        summary = None

    return {
        "visual_run_id": row.visual_run_id,
        "pipeline_id": row.pipeline_id,
        "mode": row.mode,
        "execution_mode": row.execution_mode,
        "run_status": row.run_status,
        "compile_result_id": row.compile_result_id,
        "materialization_result_id": row.materialization_result_id,
        "graph_version_hash": row.graph_version_hash,
        "load_run_id": row.load_run_id,
        "activation_id": row.activation_id,
        "r10_schedule_id": row.r10_schedule_id,
        "scheduled_for": _iso(row.scheduled_for),
        "triggered_at": _iso(row.triggered_at),
        "started_at": _iso(row.started_at),
        "finished_at": _iso(row.finished_at),
        "created_at": _iso(row.created_at),
        "result": summary if summary else None,
        "issues": list(row.issues_json or []),
        "issues_count": _issues_count(row.issues_json),
        "error_message": row.error_message,
        "poll_url": _poll_url(row.pipeline_id, row.visual_run_id),
        "schedule_active_changed": False,
        "current_sync_status_changed": False,
        "persisted": True,
        # Additive S8-2 fields
        "dedup_key": row.dedup_key,
        "claimed_at": _iso(row.claimed_at),
        "claimed_by": row.claimed_by,
        "locked_until": _iso(row.locked_until),
        "heartbeat_at": _iso(row.heartbeat_at),
        "attempt_count": int(row.attempt_count or 0),
        "retry_of_run_id": row.retry_of_run_id,
        "retry_attempt": int(row.retry_attempt or 0),
        "retry_reason": row.retry_reason,
        "retry_mode": row.retry_mode,
        "cancel_requested": row.cancel_requested_at is not None,
        "cancel_requested_at": _iso(row.cancel_requested_at),
        "cancel_acknowledged_at": _iso(row.cancel_acknowledged_at),
        "cancel_requested_by": row.cancel_requested_by,
        "cancel_reason": row.cancel_reason,
        "catchup_of_activation_id": row.catchup_of_activation_id,
        "catchup_for_scheduled_at": _iso(row.catchup_for_scheduled_at),
        "catchup_reason": row.catchup_reason,
        "catchup_requested_by": row.catchup_requested_by,
        "catchup_requested_at": _iso(row.catchup_requested_at),
    }


async def list_visual_pipeline_runs_history(
    db: AsyncSession,
    pipeline_id: str,
    *,
    limit: int = 20,
    offset: int = 0,
    run_status: str | None = None,
    mode: str | None = None,
    activation_id: str | None = None,
    retry_of_run_id: str | None = None,
    created_from: str | None = None,
    created_to: str | None = None,
    scheduled_from: str | None = None,
    scheduled_to: str | None = None,
) -> dict[str, Any]:
    """Read-only filtered list. Does not mutate rows."""
    await _get_visual_definition(db, pipeline_id)

    lim = max(1, min(int(limit), 100))
    off = max(0, int(offset))

    filters: list[Any] = [VisualPipelineRun.pipeline_id == pipeline_id]

    if run_status is not None and str(run_status).strip():
        status = str(run_status).strip().upper()
        if status not in ALLOWED_RUN_STATUSES:
            raise ValueError("INVALID_RUN_STATUS")
        filters.append(VisualPipelineRun.run_status == status)

    if mode is not None and str(mode).strip():
        mode_norm = str(mode).strip().upper()
        if mode_norm not in ALLOWED_MODES:
            raise ValueError("INVALID_MODE")
        filters.append(VisualPipelineRun.mode == mode_norm)

    if activation_id is not None and str(activation_id).strip():
        filters.append(VisualPipelineRun.activation_id == str(activation_id).strip())

    if retry_of_run_id is not None and str(retry_of_run_id).strip():
        filters.append(VisualPipelineRun.retry_of_run_id == str(retry_of_run_id).strip())

    cf = _parse_dt(created_from, field="created_from")
    ct = _parse_dt(created_to, field="created_to")
    if cf is not None:
        filters.append(VisualPipelineRun.created_at >= cf)
    if ct is not None:
        filters.append(VisualPipelineRun.created_at <= ct)

    sf = _parse_dt(scheduled_from, field="scheduled_from")
    st = _parse_dt(scheduled_to, field="scheduled_to")
    if sf is not None:
        filters.append(VisualPipelineRun.scheduled_for >= sf)
    if st is not None:
        filters.append(VisualPipelineRun.scheduled_for <= st)

    total = int(
        (
            await db.execute(
                select(func.count()).select_from(VisualPipelineRun).where(*filters)
            )
        ).scalar_one()
        or 0
    )

    rows = (
        await db.execute(
            select(VisualPipelineRun)
            .where(*filters)
            .order_by(VisualPipelineRun.created_at.desc())
            .offset(off)
            .limit(lim)
        )
    ).scalars().all()

    return {
        "items": [summarize_run_row(r) for r in rows],
        "limit": lim,
        "offset": off,
        "total": total,
    }


async def get_visual_pipeline_run_history_detail(
    db: AsyncSession,
    pipeline_id: str,
    visual_run_id: str,
) -> dict[str, Any]:
    """Read-only detail. Does not mutate rows."""
    await _get_visual_definition(db, pipeline_id)
    row = (
        await db.execute(
            select(VisualPipelineRun).where(
                VisualPipelineRun.pipeline_id == pipeline_id,
                VisualPipelineRun.visual_run_id == visual_run_id,
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise LookupError("VISUAL_PIPELINE_RUN_NOT_FOUND")
    return detail_run_row(row)
