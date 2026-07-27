"""R11-S8-5 Visual Pipeline soft-cancel — PENDING immediate + RUNNING cooperative cancel.

Does not kill processes. RUNNING cancel records a request; execution checks at step boundaries.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.time import utc_now
from app.models.entities import VisualPipelineRun
from app.services.visual_pipeline.audit_service import (
    ACTOR_USER,
    SOURCE_API,
    STATUS_SUCCESS,
    record_visual_pipeline_audit_event,
)
from app.services.visual_pipeline.run_event_service import (
    EVENT_RUN_CANCEL_REQUESTED,
    EVENT_RUN_CANCELLED,
    emit_run_event_safe,
)
from app.services.visual_pipeline.visual_pipeline_service import _get_visual_definition

logger = logging.getLogger(__name__)


class VisualPipelineCancelRequested(Exception):
    """Raised at step boundary when cancel_requested_at is set on a RUNNING run."""

    def __init__(self, visual_run_id: str, message: str | None = None) -> None:
        self.visual_run_id = visual_run_id
        self.message = message or "Cancel requested for visual pipeline run."
        super().__init__(self.message)


class RunCancelError(Exception):
    def __init__(self, code: str, message: str | None = None, *, http_status: int = 409) -> None:
        self.code = code
        self.message = message or code
        self.http_status = http_status
        super().__init__(self.message)


def _iso(dt: Any) -> str | None:
    if dt is None:
        return None
    text = dt.isoformat() if hasattr(dt, "isoformat") else str(dt)
    if text and not text.endswith("Z") and "+" not in text and "T" in text:
        return f"{text}Z"
    return text


def _poll_url(pipeline_id: str, visual_run_id: str) -> str:
    return f"/api/v1/visual-pipelines/{pipeline_id}/runs/{visual_run_id}"


def _issue(code: str, message: str, *, step_id: str | None = None) -> dict[str, Any]:
    return {
        "severity": "ERROR",
        "code": code,
        "message": message,
        "phase": "RUN",
        "step_id": step_id,
        "node_id": None,
        "details": {},
    }


def _clear_run_lease(run_row: VisualPipelineRun) -> None:
    run_row.locked_until = None
    run_row.heartbeat_at = utc_now()


def _cancel_response(
    row: VisualPipelineRun,
    *,
    message: str,
    already_requested: bool = False,
) -> dict[str, Any]:
    """Cancel API response — includes run fields for Studio setRunResult compatibility."""
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
        "result": None,
        "issues": list(row.issues_json or []),
        "error_message": row.error_message,
        "poll_url": _poll_url(row.pipeline_id, row.visual_run_id),
        "persisted": True,
        "cancel_requested": row.cancel_requested_at is not None
        or str(row.run_status or "").upper() == "CANCELLED",
        "cancel_requested_at": _iso(row.cancel_requested_at),
        "cancel_acknowledged_at": _iso(row.cancel_acknowledged_at),
        "cancel_requested_by": row.cancel_requested_by,
        "cancel_reason": row.cancel_reason,
        "already_requested": already_requested,
        "message": message,
    }


async def raise_if_visual_run_cancel_requested(db: AsyncSession, visual_run_id: str) -> None:
    """Select run; raise VisualPipelineCancelRequested when RUNNING has cancel_requested_at."""
    row = (
        await db.execute(
            select(VisualPipelineRun).where(VisualPipelineRun.visual_run_id == visual_run_id)
        )
    ).scalar_one_or_none()
    if row is None:
        return
    if str(row.run_status or "").upper() != "RUNNING":
        return
    if row.cancel_requested_at is None:
        return
    raise VisualPipelineCancelRequested(
        visual_run_id,
        message=row.cancel_reason or "Cancel requested for visual pipeline run.",
    )


async def apply_cancel_acknowledged(
    db: AsyncSession,
    run_row: VisualPipelineRun,
    *,
    message: str | None = None,
) -> None:
    """Mark RUNNING run as CANCELLED after boundary detection. Caller flushes/commits."""
    now = utc_now()
    run_row.run_status = "CANCELLED"
    run_row.cancel_acknowledged_at = now
    run_row.finished_at = now
    run_row.error_message = message or "중단 요청에 따라 실행이 취소되었습니다."
    issues = list(run_row.issues_json or [])
    issues.append(
        _issue(
            "RUN_CANCELLED_BY_REQUEST",
            run_row.error_message,
            step_id="cancel",
        )
    )
    run_row.issues_json = issues
    result = dict(run_row.result_json or {})
    summary = dict(result.get("summary") or {}) if isinstance(result.get("summary"), dict) else {}
    summary.update(
        {
            "cancelled": True,
            "cancel_phase": "RUNNING",
            "cancel_reason": run_row.cancel_reason,
        }
    )
    result["summary"] = summary
    run_row.result_json = result
    _clear_run_lease(run_row)
    await emit_run_event_safe(
        db,
        visual_run_id=run_row.visual_run_id,
        pipeline_id=run_row.pipeline_id,
        event_type=EVENT_RUN_CANCELLED,
        message=run_row.error_message,
        metadata_json={
            "cancel_phase": "RUNNING",
            "cancel_requested_at": _iso(run_row.cancel_requested_at),
            "cancel_acknowledged_at": _iso(now),
            "cancel_reason": run_row.cancel_reason,
        },
    )
    try:
        await record_visual_pipeline_audit_event(
            db,
            event_type=EVENT_RUN_CANCELLED,
            event_source=SOURCE_API,
            action_status=STATUS_SUCCESS,
            pipeline_id=run_row.pipeline_id,
            visual_run_id=run_row.visual_run_id,
            activation_id=run_row.activation_id,
            actor_type=ACTOR_USER,
            actor_id=run_row.cancel_requested_by or "system",
            reason=run_row.cancel_reason,
            before_json={"run_status": "RUNNING"},
            after_json={
                "run_status": "CANCELLED",
                "cancel_acknowledged_at": _iso(now),
                "finished_at": _iso(now),
            },
            metadata_json={"cancel_phase": "RUNNING"},
            fail_open=True,
        )
    except Exception:  # noqa: BLE001
        logger.warning(
            "soft-cancel acknowledged audit failed visual_run_id=%s",
            run_row.visual_run_id,
            exc_info=True,
        )


async def cancel_visual_pipeline_run(
    db: AsyncSession,
    pipeline_id: str,
    visual_run_id: str,
    *,
    reason: str | None = None,
    confirm_visual_run_id: str | None = None,
    actor_type: str = ACTOR_USER,
    actor_id: str = "mock_admin",
) -> dict[str, Any]:
    """PENDING → immediate CANCELLED; RUNNING → cancel request (cooperative)."""
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

    status = str(row.run_status or "").upper()
    reason_text = str(reason or "").strip() if reason is not None else ""

    if status == "CANCELLED":
        return _cancel_response(
            row,
            message="이미 취소된 Run입니다.",
            already_requested=True,
        )

    if status in {"SUCCESS", "FAILED", "PARTIAL"}:
        raise RunCancelError(
            "RUN_CANCEL_NOT_ALLOWED_STATUS",
            f"Cancel is not allowed for run_status={status}.",
            http_status=409,
        )

    if status == "RUNNING":
        confirm = str(confirm_visual_run_id or "").strip()
        if confirm != visual_run_id:
            raise RunCancelError(
                "RUN_CANCEL_CONFIRM_MISMATCH",
                "confirm_visual_run_id must match the path visual_run_id.",
                http_status=400,
            )
        if len(reason_text) < 5 or len(reason_text) > 300:
            raise RunCancelError(
                "RUN_CANCEL_REASON_REQUIRED",
                "reason must be between 5 and 300 characters.",
                http_status=400,
            )
        if row.cancel_requested_at is not None:
            return _cancel_response(
                row,
                message="이미 중단 요청이 접수된 Run입니다.",
                already_requested=True,
            )

        try:
            audit_row = await record_visual_pipeline_audit_event(
                db,
                event_type=EVENT_RUN_CANCEL_REQUESTED,
                event_source=SOURCE_API,
                action_status=STATUS_SUCCESS,
                pipeline_id=pipeline_id,
                visual_run_id=visual_run_id,
                activation_id=row.activation_id,
                actor_type=actor_type,
                actor_id=actor_id,
                reason=reason_text[:200],
                before_json={"run_status": "RUNNING"},
                after_json={
                    "run_status": "RUNNING",
                    "cancel_requested": True,
                },
                metadata_json={"cancel_phase": "RUNNING_REQUEST"},
                fail_open=False,
            )
        except Exception as exc:  # noqa: BLE001
            raise RunCancelError(
                "RUN_CANCEL_AUDIT_REQUIRED_FAILED",
                "Audit recording failed; cancel request was not recorded.",
                http_status=409,
            ) from exc
        if audit_row is None:
            raise RunCancelError(
                "RUN_CANCEL_AUDIT_REQUIRED_FAILED",
                "Audit recording failed; cancel request was not recorded.",
                http_status=409,
            )

        now = utc_now()
        row.cancel_requested_at = now
        row.cancel_requested_by = actor_id[:120]
        row.cancel_reason = reason_text[:300]
        await emit_run_event_safe(
            db,
            visual_run_id=visual_run_id,
            pipeline_id=pipeline_id,
            event_type=EVENT_RUN_CANCEL_REQUESTED,
            message="Cancel requested; will stop at next step boundary",
            metadata_json={
                "cancel_requested_at": _iso(now),
                "actor_id": actor_id,
                "reason": reason_text[:300],
            },
        )
        await db.commit()
        await db.refresh(row)
        return _cancel_response(
            row,
            message="중단 요청이 접수되었습니다. 현재 단계가 끝난 뒤 중단됩니다.",
            already_requested=False,
        )

    if status != "PENDING":
        raise RunCancelError(
            "RUN_CANCEL_NOT_ALLOWED_STATUS",
            f"Cancel is not allowed for run_status={status}.",
            http_status=409,
        )

    pending_reason = reason_text if len(reason_text) >= 5 else "Cancelled before execution"
    try:
        audit_row = await record_visual_pipeline_audit_event(
            db,
            event_type=EVENT_RUN_CANCELLED,
            event_source=SOURCE_API,
            action_status=STATUS_SUCCESS,
            pipeline_id=pipeline_id,
            visual_run_id=visual_run_id,
            activation_id=row.activation_id,
            actor_type=actor_type,
            actor_id=actor_id,
            reason=pending_reason[:200],
            before_json={"run_status": "PENDING"},
            after_json={"run_status": "CANCELLED"},
            metadata_json={"cancel_phase": "PENDING"},
            fail_open=False,
        )
    except Exception as exc:  # noqa: BLE001
        raise RunCancelError(
            "RUN_CANCEL_AUDIT_REQUIRED_FAILED",
            "Audit recording failed; cancel was not applied.",
            http_status=409,
        ) from exc
    if audit_row is None:
        raise RunCancelError(
            "RUN_CANCEL_AUDIT_REQUIRED_FAILED",
            "Audit recording failed; cancel was not applied.",
            http_status=409,
        )

    now = utc_now()
    row.run_status = "CANCELLED"
    row.finished_at = now
    row.cancel_requested_at = now
    row.cancel_requested_by = actor_id[:120]
    row.cancel_reason = pending_reason[:300]
    row.cancel_acknowledged_at = now
    row.error_message = "Cancelled before execution"
    issues = list(row.issues_json or [])
    issues.append(
        _issue(
            "RUN_CANCELLED_BEFORE_EXECUTION",
            "Run was cancelled before execution.",
            step_id="cancel",
        )
    )
    row.issues_json = issues
    row.result_json = {
        "summary": {
            "cancelled": True,
            "cancel_phase": "PENDING",
        }
    }
    _clear_run_lease(row)
    await emit_run_event_safe(
        db,
        visual_run_id=visual_run_id,
        pipeline_id=pipeline_id,
        event_type=EVENT_RUN_CANCELLED,
        message="Cancelled before execution",
        metadata_json={"cancel_phase": "PENDING"},
    )
    await db.commit()
    await db.refresh(row)
    return _cancel_response(
        row,
        message="대기 중인 Run이 취소되었습니다.",
        already_requested=False,
    )
