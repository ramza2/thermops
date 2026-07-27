"""R11-S8-4 Visual Pipeline Run Retry — new PENDING run + lineage (SAME_SNAPSHOT).

Does not call run_load or BackgroundTasks. Worker claims the new PENDING row.
Original run is never mutated. Audit is required (fail-close).
"""

from __future__ import annotations

import copy
import logging
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.time import utc_now
from app.models.entities import VisualPipelineRun
from app.services.visual_pipeline.audit_service import (
    ACTOR_USER,
    record_run_retry_enqueued_event,
)
from app.services.visual_pipeline.manual_run_service import (
    EXECUTOR_WORKER,
    RunPreconditionError,
    _assert_no_active_run,
    _new_visual_run_id,
    _poll_url,
)
from app.services.visual_pipeline.run_event_service import (
    EVENT_RUN_CREATED,
    EVENT_RUN_RETRY_REQUESTED,
    emit_run_event_safe,
)
from app.services.visual_pipeline.visual_pipeline_service import _get_visual_definition

logger = logging.getLogger(__name__)

RETRY_MODE_SAME_SNAPSHOT = "SAME_SNAPSHOT"
ALLOWED_RETRY_STATUSES = frozenset({"FAILED", "PARTIAL"})


class RunRetryError(Exception):
    """Retry validation / policy failure."""

    def __init__(self, code: str, message: str | None = None, *, http_status: int = 409) -> None:
        self.code = code
        self.message = message or code
        self.http_status = http_status
        super().__init__(self.message)


async def _resolve_root_visual_run_id(db: AsyncSession, source: VisualPipelineRun) -> str:
    """Walk retry_of_run_id chain (or request_json.retry.root) to find lineage root."""
    req = source.request_json if isinstance(source.request_json, dict) else {}
    retry_meta = req.get("retry") if isinstance(req.get("retry"), dict) else {}
    if retry_meta.get("root_visual_run_id"):
        return str(retry_meta["root_visual_run_id"])

    current = source
    seen: set[str] = set()
    while current.retry_of_run_id:
        parent_id = str(current.retry_of_run_id)
        if parent_id in seen:
            break
        seen.add(parent_id)
        parent = (
            await db.execute(
                select(VisualPipelineRun).where(VisualPipelineRun.visual_run_id == parent_id)
            )
        ).scalar_one_or_none()
        if parent is None:
            return parent_id
        current = parent
    return str(current.visual_run_id)


def _build_retry_dedup_key(root_id: str, retry_attempt: int, new_id: str) -> str:
    return f"RETRY:{root_id}:{retry_attempt}:{new_id}"


async def _max_retry_attempt_in_lineage(db: AsyncSession, root_visual_run_id: str) -> int:
    """Max retry_attempt among runs that share this lineage root."""
    # Direct children of root + root itself
    direct_max = (
        await db.execute(
            select(func.max(VisualPipelineRun.retry_attempt)).where(
                or_(
                    VisualPipelineRun.retry_of_run_id == root_visual_run_id,
                    VisualPipelineRun.visual_run_id == root_visual_run_id,
                )
            )
        )
    ).scalar_one()
    direct_max_i = int(direct_max or 0)

    # Descendants that stored root in request_json.retry.root_visual_run_id
    rows = (
        await db.execute(
            select(VisualPipelineRun.retry_attempt, VisualPipelineRun.request_json).where(
                VisualPipelineRun.retry_attempt > 0
            )
        )
    ).all()
    json_max = 0
    for attempt, req in rows:
        if not isinstance(req, dict):
            continue
        retry_meta = req.get("retry") if isinstance(req.get("retry"), dict) else {}
        if str(retry_meta.get("root_visual_run_id") or "") == root_visual_run_id:
            json_max = max(json_max, int(attempt or 0))
    return max(direct_max_i, json_max)


async def retry_visual_pipeline_run(
    db: AsyncSession,
    *,
    pipeline_id: str,
    source_visual_run_id: str,
    reason: str,
    confirm_visual_run_id: str,
    retry_mode: str = RETRY_MODE_SAME_SNAPSHOT,
    actor_type: str = ACTOR_USER,
    actor_id: str = "mock_admin",
) -> dict[str, Any]:
    """Enqueue a new PENDING retry run from a FAILED/PARTIAL source. Commits."""
    confirm = str(confirm_visual_run_id or "").strip()
    if confirm != source_visual_run_id:
        raise RunRetryError(
            "RUN_RETRY_CONFIRM_MISMATCH",
            "confirm_visual_run_id must match the path visual_run_id.",
            http_status=400,
        )

    reason_text = str(reason or "").strip()
    if len(reason_text) < 5 or len(reason_text) > 300:
        raise RunRetryError(
            "RUN_RETRY_REASON_REQUIRED",
            "reason must be between 5 and 300 characters.",
            http_status=400,
        )

    mode = str(retry_mode or RETRY_MODE_SAME_SNAPSHOT).strip().upper() or RETRY_MODE_SAME_SNAPSHOT
    if mode != RETRY_MODE_SAME_SNAPSHOT:
        raise RunRetryError(
            "RUN_RETRY_MODE_NOT_SUPPORTED",
            "Only retry_mode=SAME_SNAPSHOT is supported.",
            http_status=400,
        )

    max_attempts = int(get_settings().vp_run_retry_max_attempts)
    if max_attempts <= 0:
        raise RunRetryError(
            "RUN_RETRY_MAX_ATTEMPT_EXCEEDED",
            "Retry is disabled (THERMOOPS_VP_RUN_RETRY_MAX_ATTEMPTS=0).",
            http_status=409,
        )

    await _get_visual_definition(db, pipeline_id)

    source = (
        await db.execute(
            select(VisualPipelineRun).where(
                VisualPipelineRun.pipeline_id == pipeline_id,
                VisualPipelineRun.visual_run_id == source_visual_run_id,
            )
        )
    ).scalar_one_or_none()
    if source is None:
        raise RunRetryError(
            "RUN_RETRY_SOURCE_NOT_FOUND",
            "Source run not found for this pipeline.",
            http_status=404,
        )

    status = str(source.run_status or "").upper()
    if status not in ALLOWED_RETRY_STATUSES:
        raise RunRetryError(
            "RUN_RETRY_NOT_ALLOWED_STATUS",
            f"Retry is not allowed for run_status={status}.",
            http_status=409,
        )

    try:
        await _assert_no_active_run(db, pipeline_id)
    except RunPreconditionError as exc:
        if exc.code == "RUN_CONCURRENT_RUN_EXISTS":
            raise RunRetryError(
                "RUN_RETRY_ACTIVE_RUN_EXISTS",
                "An active PENDING/RUNNING run exists for this pipeline.",
                http_status=409,
            ) from exc
        raise RunRetryError(exc.code, exc.message, http_status=409) from exc

    root_id = await _resolve_root_visual_run_id(db, source)
    current_max = await _max_retry_attempt_in_lineage(db, root_id)
    next_attempt = current_max + 1
    if next_attempt > max_attempts:
        raise RunRetryError(
            "RUN_RETRY_MAX_ATTEMPT_EXCEEDED",
            f"Maximum retry attempts ({max_attempts}) exceeded.",
            http_status=409,
        )

    new_id = _new_visual_run_id()
    dedup = _build_retry_dedup_key(root_id, next_attempt, new_id)
    request_json = copy.deepcopy(source.request_json) if isinstance(source.request_json, dict) else {}
    if not isinstance(request_json, dict):
        request_json = {}
    request_json = dict(request_json)
    request_json["retry"] = {
        "source_visual_run_id": source.visual_run_id,
        "root_visual_run_id": root_id,
        "retry_attempt": next_attempt,
        "retry_mode": mode,
        "reason": reason_text[:300],
    }
    # Prefer worker for retry enqueue (no BackgroundTasks registration from this API).
    request_json["executor"] = EXECUTOR_WORKER

    try:
        audit_row = await record_run_retry_enqueued_event(
            db,
            pipeline_id=pipeline_id,
            source_visual_run_id=source.visual_run_id,
            retry_visual_run_id=new_id,
            retry_attempt=next_attempt,
            retry_mode=mode,
            reason=reason_text,
            activation_id=source.activation_id,
            materialization_result_id=source.materialization_result_id,
            r10_schedule_id=source.r10_schedule_id,
            source_run_status=status,
            actor_type=actor_type,
            actor_id=actor_id,
            fail_open=False,
        )
    except Exception as exc:  # noqa: BLE001 — map audit failure to policy error
        logger.warning("retry audit failed pipeline_id=%s source=%s", pipeline_id, source_visual_run_id)
        raise RunRetryError(
            "RUN_RETRY_AUDIT_REQUIRED_FAILED",
            "Audit recording failed; retry run was not created.",
            http_status=409,
        ) from exc
    if audit_row is None:
        raise RunRetryError(
            "RUN_RETRY_AUDIT_REQUIRED_FAILED",
            "Audit recording failed; retry run was not created.",
            http_status=409,
        )

    now = utc_now()
    retry_row = VisualPipelineRun(
        visual_run_id=new_id,
        pipeline_id=pipeline_id,
        compile_result_id=source.compile_result_id,
        materialization_result_id=source.materialization_result_id,
        graph_version_hash=source.graph_version_hash,
        load_run_id=None,
        mode=source.mode,
        execution_mode=source.execution_mode or "BACKGROUND",
        run_status="PENDING",
        request_json=request_json,
        result_json={},
        issues_json=[],
        error_message=None,
        activation_id=source.activation_id,
        r10_schedule_id=source.r10_schedule_id,
        scheduled_for=source.scheduled_for,
        triggered_at=source.triggered_at,
        dedup_key=dedup,
        claimed_at=None,
        claimed_by=None,
        locked_until=None,
        heartbeat_at=None,
        attempt_count=0,
        retry_of_run_id=source.visual_run_id,
        retry_attempt=next_attempt,
        retry_reason=reason_text[:300],
        retry_mode=mode,
        started_at=None,
        finished_at=None,
        created_at=now,
    )
    db.add(retry_row)
    await db.flush()

    await emit_run_event_safe(
        db,
        visual_run_id=source.visual_run_id,
        pipeline_id=pipeline_id,
        event_type=EVENT_RUN_RETRY_REQUESTED,
        message="Retry requested; new PENDING run enqueued",
        metadata_json={
            "retry_visual_run_id": new_id,
            "retry_attempt": next_attempt,
            "retry_mode": mode,
        },
    )
    await emit_run_event_safe(
        db,
        visual_run_id=new_id,
        pipeline_id=pipeline_id,
        event_type=EVENT_RUN_CREATED,
        message="Retry run created (PENDING)",
        metadata_json={
            "retry_of_run_id": source.visual_run_id,
            "root_visual_run_id": root_id,
            "retry_attempt": next_attempt,
            "retry_mode": mode,
            "mode": source.mode,
            "executor": EXECUTOR_WORKER,
        },
    )

    await db.commit()
    await db.refresh(retry_row)

    return {
        "original_visual_run_id": source.visual_run_id,
        "retry_visual_run_id": retry_row.visual_run_id,
        "pipeline_id": pipeline_id,
        "retry_attempt": next_attempt,
        "retry_mode": mode,
        "run_status": "PENDING",
        "reason": reason_text,
        "poll_url": _poll_url(pipeline_id, retry_row.visual_run_id),
    }
