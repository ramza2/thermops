"""R11-S8-3 Visual Pipeline Run Event — append-only progress events (fail-open).

Observability only; source of truth remains tb_visual_pipeline_run.run_status.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Awaitable, Callable
from typing import Any
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.time import utc_now
from app.models.entities import VisualPipelineRun, VisualPipelineRunEvent
from app.services.visual_pipeline.audit_service import sanitize_audit_payload
from app.services.visual_pipeline.visual_pipeline_service import _get_visual_definition

logger = logging.getLogger(__name__)

EVENT_RUN_CREATED = "RUN_CREATED"
EVENT_WORKER_CLAIMED = "WORKER_CLAIMED"
EVENT_RUN_STARTED = "RUN_STARTED"
EVENT_STEP_STARTED = "STEP_STARTED"
EVENT_STEP_COMPLETED = "STEP_COMPLETED"
EVENT_LOAD_FINALIZE = "LOAD_FINALIZE"
EVENT_RUN_COMPLETED = "RUN_COMPLETED"
EVENT_RUN_FAILED = "RUN_FAILED"
EVENT_RUN_CANCELLED = "RUN_CANCELLED"
EVENT_RUN_CANCEL_REQUESTED = "RUN_CANCEL_REQUESTED"
EVENT_RUN_RETRY_REQUESTED = "RUN_RETRY_REQUESTED"

STEP_SOURCE_FETCH = "SOURCE_FETCH"
STEP_TRANSFORM = "TRANSFORM"
STEP_UPSERT_LOAD = "UPSERT_LOAD"

STEP_ORDER = (STEP_SOURCE_FETCH, STEP_TRANSFORM, STEP_UPSERT_LOAD)

STEP_LABELS: dict[str, str] = {
    STEP_SOURCE_FETCH: "REST 데이터 조회",
    STEP_TRANSFORM: "변환 적용",
    STEP_UPSERT_LOAD: "적재 실행",
}

PROGRESS_BY_EVENT: dict[tuple[str, str | None], int] = {
    (EVENT_RUN_CREATED, None): 0,
    (EVENT_WORKER_CLAIMED, None): 5,
    (EVENT_RUN_STARTED, None): 10,
    (EVENT_STEP_STARTED, STEP_SOURCE_FETCH): 15,
    (EVENT_STEP_COMPLETED, STEP_SOURCE_FETCH): 30,
    (EVENT_STEP_STARTED, STEP_TRANSFORM): 35,
    (EVENT_STEP_COMPLETED, STEP_TRANSFORM): 50,
    (EVENT_STEP_STARTED, STEP_UPSERT_LOAD): 55,
    (EVENT_STEP_COMPLETED, STEP_UPSERT_LOAD): 85,
    (EVENT_LOAD_FINALIZE, None): 90,
    (EVENT_RUN_COMPLETED, None): 100,
    (EVENT_RUN_FAILED, None): 100,
    (EVENT_RUN_CANCELLED, None): 100,
}

MAX_EVENT_LIST_LIMIT = 200
DEFAULT_EVENT_LIST_LIMIT = 100

SECRET_VALUE_RE = re.compile(
    r"(Bearer\s+\S+|Authorization:\s*\S+|password=\S+|api_key=\S+)",
    re.IGNORECASE,
)


def _new_event_id() -> str:
    return f"VPRE-{uuid4().hex[:8].upper()}"


def _iso(dt: Any) -> str | None:
    if dt is None:
        return None
    text = dt.isoformat() if hasattr(dt, "isoformat") else str(dt)
    if text and not text.endswith("Z") and "+" not in text and "T" in text:
        return f"{text}Z"
    return text


def _progress_percent(event_type: str, step_key: str | None) -> int | None:
    return PROGRESS_BY_EVENT.get((event_type, step_key))


def _sanitize_message(message: str | None) -> str | None:
    if not message:
        return None
    text = str(message)[:500]
    if SECRET_VALUE_RE.search(text):
        return "Progress event (details redacted)."
    return text


def _row_to_item(row: VisualPipelineRunEvent) -> dict[str, Any]:
    return {
        "event_id": row.event_id,
        "visual_run_id": row.visual_run_id,
        "pipeline_id": row.pipeline_id,
        "event_type": row.event_type,
        "step_key": row.step_key,
        "step_name": row.step_name,
        "progress_percent": row.progress_percent,
        "message": row.message,
        "metadata_json": row.metadata_json or {},
        "created_at": _iso(row.created_at),
    }


async def emit_run_event_safe(
    db: AsyncSession,
    *,
    visual_run_id: str,
    pipeline_id: str,
    event_type: str,
    step_key: str | None = None,
    message: str | None = None,
    metadata_json: dict[str, Any] | None = None,
) -> VisualPipelineRunEvent | None:
    """Append a run event using a nested savepoint. Failures are logged and swallowed."""
    step_name = STEP_LABELS.get(step_key) if step_key else None
    progress = _progress_percent(event_type, step_key)
    meta = sanitize_audit_payload(metadata_json or {})

    async with db.begin_nested():
        try:
            row = VisualPipelineRunEvent(
                event_id=_new_event_id(),
                visual_run_id=visual_run_id,
                pipeline_id=pipeline_id,
                event_type=event_type,
                step_key=step_key,
                step_name=step_name,
                progress_percent=progress,
                message=_sanitize_message(message),
                metadata_json=meta,
                created_at=utc_now(),
            )
            db.add(row)
            await db.flush()
            return row
        except Exception:  # noqa: BLE001 — fail-open
            logger.warning(
                "failed to emit run event visual_run_id=%s event_type=%s",
                visual_run_id,
                event_type,
                exc_info=True,
            )
            return None


def build_step_progress_callback(
    db: AsyncSession,
    *,
    visual_run_id: str,
    pipeline_id: str,
) -> Callable[[dict[str, Any]], Awaitable[None]]:
    """Callback for run_load on_progress — delegates to emit_run_event_safe."""

    async def _on_progress(payload: dict[str, Any]) -> None:
        await emit_run_event_safe(
            db,
            visual_run_id=visual_run_id,
            pipeline_id=pipeline_id,
            event_type=str(payload.get("event_type") or EVENT_STEP_STARTED),
            step_key=payload.get("step_key"),
            message=payload.get("message"),
            metadata_json=payload.get("metadata") if isinstance(payload.get("metadata"), dict) else None,
        )

    return _on_progress


async def _assert_run_belongs(
    db: AsyncSession,
    pipeline_id: str,
    visual_run_id: str,
) -> VisualPipelineRun:
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
    return row


async def list_visual_pipeline_run_events(
    db: AsyncSession,
    pipeline_id: str,
    visual_run_id: str,
    *,
    limit: int = DEFAULT_EVENT_LIST_LIMIT,
    offset: int = 0,
) -> dict[str, Any]:
    """Read-only event timeline for a run."""
    await _assert_run_belongs(db, pipeline_id, visual_run_id)
    lim = max(1, min(int(limit), MAX_EVENT_LIST_LIMIT))
    off = max(0, int(offset))

    filters = [
        VisualPipelineRunEvent.pipeline_id == pipeline_id,
        VisualPipelineRunEvent.visual_run_id == visual_run_id,
    ]
    total = int(
        (
            await db.execute(
                select(func.count()).select_from(VisualPipelineRunEvent).where(*filters)
            )
        ).scalar_one()
        or 0
    )
    rows = (
        await db.execute(
            select(VisualPipelineRunEvent)
            .where(*filters)
            .order_by(VisualPipelineRunEvent.created_at.asc(), VisualPipelineRunEvent.event_id.asc())
            .offset(off)
            .limit(lim)
        )
    ).scalars().all()
    return {
        "items": [_row_to_item(r) for r in rows],
        "limit": lim,
        "offset": off,
        "total": total,
    }


def _derive_step_status(events: list[VisualPipelineRunEvent], step_key: str) -> str:
    started = False
    completed = False
    for ev in events:
        if ev.step_key != step_key:
            continue
        if ev.event_type == EVENT_STEP_STARTED:
            started = True
        elif ev.event_type == EVENT_STEP_COMPLETED:
            completed = True
    if completed:
        return "completed"
    if started:
        return "running"
    return "pending"


async def get_visual_pipeline_run_progress(
    db: AsyncSession,
    pipeline_id: str,
    visual_run_id: str,
) -> dict[str, Any]:
    """Read-only progress summary derived from events + run_status."""
    run_row = await _assert_run_belongs(db, pipeline_id, visual_run_id)
    events = (
        await db.execute(
            select(VisualPipelineRunEvent)
            .where(
                VisualPipelineRunEvent.pipeline_id == pipeline_id,
                VisualPipelineRunEvent.visual_run_id == visual_run_id,
            )
            .order_by(VisualPipelineRunEvent.created_at.asc(), VisualPipelineRunEvent.event_id.asc())
        )
    ).scalars().all()

    run_status = str(run_row.run_status or "").upper()
    terminal_statuses = {"SUCCESS", "PARTIAL", "FAILED", "CANCELLED"}
    is_terminal = run_status in terminal_statuses

    current_step_key: str | None = None
    current_step_name: str | None = None
    progress_percent: int | None = None
    last_event_at: str | None = None

    for ev in reversed(events):
        if last_event_at is None:
            last_event_at = _iso(ev.created_at)
        if ev.progress_percent is not None and progress_percent is None:
            progress_percent = int(ev.progress_percent)
        if (
            current_step_key is None
            and ev.step_key
            and ev.event_type in {EVENT_STEP_STARTED, EVENT_STEP_COMPLETED}
        ):
            current_step_key = ev.step_key
            current_step_name = ev.step_name or STEP_LABELS.get(ev.step_key)

    if is_terminal and run_status in {"SUCCESS", "PARTIAL"}:
        progress_percent = 100
    elif is_terminal and run_status == "FAILED":
        progress_percent = progress_percent if progress_percent is not None else 100
    elif is_terminal and run_status == "CANCELLED":
        progress_percent = progress_percent if progress_percent is not None else 0

    if not is_terminal and current_step_key:
        step_status = _derive_step_status(events, current_step_key)
        if step_status == "completed":
            idx = STEP_ORDER.index(current_step_key) if current_step_key in STEP_ORDER else -1
            if 0 <= idx < len(STEP_ORDER) - 1:
                next_key = STEP_ORDER[idx + 1]
                if _derive_step_status(events, next_key) == "pending":
                    current_step_key = next_key
                    current_step_name = STEP_LABELS.get(next_key)

    steps = []
    for step_key in STEP_ORDER:
        status = _derive_step_status(events, step_key)
        steps.append(
            {
                "step_key": step_key,
                "step_name": STEP_LABELS.get(step_key),
                "status": status,
            }
        )

    return {
        "visual_run_id": visual_run_id,
        "pipeline_id": pipeline_id,
        "run_status": run_status,
        "current_step_key": current_step_key,
        "current_step_name": current_step_name,
        "progress_percent": progress_percent,
        "is_terminal": is_terminal,
        "last_event_at": last_event_at,
        "steps": steps,
        "event_count": len(events),
        "cancel_requested": run_row.cancel_requested_at is not None,
        "cancel_requested_at": _iso(run_row.cancel_requested_at),
        "cancel_acknowledged_at": _iso(run_row.cancel_acknowledged_at),
        "cancel_requested_by": run_row.cancel_requested_by,
        "cancel_reason": run_row.cancel_reason,
    }
