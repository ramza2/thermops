"""R11-S7-10/S7-13/S7-14 Visual Pipeline Ops API — summary, stuck, audit, mark-failed."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.response import ok
from app.services.visual_pipeline.audit_service import (
    DEFAULT_AUDIT_LIST_LIMIT,
    MAX_AUDIT_LIST_LIMIT,
    get_audit_log,
    list_audit_logs,
)
from app.services.visual_pipeline.ops_service import (
    DEFAULT_PENDING_AGE_SECONDS,
    DEFAULT_RUNNING_LOCK_GRACE_SECONDS,
    DEFAULT_STUCK_LIMIT,
    MarkFailedError,
    get_ops_summary,
    list_stuck_runs,
    mark_single_stuck_run_failed,
)

router = APIRouter(prefix="/visual-pipeline-ops", tags=["Visual Pipeline Ops"])


class MarkStuckRunFailedBody(BaseModel):
    reason: str = Field(..., min_length=1, max_length=200)
    confirm_visual_run_id: str = Field(..., min_length=1, max_length=50)
    pending_age_seconds: int | None = Field(default=None, ge=0, le=86400)
    running_lock_grace_seconds: int | None = Field(default=None, ge=0, le=86400)


@router.get("/summary")
async def get_visual_pipeline_ops_summary(
    pending_age_seconds: int = Query(default=DEFAULT_PENDING_AGE_SECONDS, ge=0, le=86400),
    running_lock_grace_seconds: int = Query(
        default=DEFAULT_RUNNING_LOCK_GRACE_SECONDS, ge=0, le=86400
    ),
    db: AsyncSession = Depends(get_db),
):
    """Read-only ops summary. Does not execute workers or mutate runs/activations."""
    data = await get_ops_summary(
        db,
        pending_age_seconds=pending_age_seconds,
        running_lock_grace_seconds=running_lock_grace_seconds,
    )
    return ok(data)


@router.get("/stuck-runs")
async def get_visual_pipeline_ops_stuck_runs(
    pending_age_seconds: int = Query(default=DEFAULT_PENDING_AGE_SECONDS, ge=0, le=86400),
    running_lock_grace_seconds: int = Query(
        default=DEFAULT_RUNNING_LOCK_GRACE_SECONDS, ge=0, le=86400
    ),
    limit: int = Query(default=DEFAULT_STUCK_LIMIT, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
):
    """List stuck PENDING/RUNNING runs. Read-only."""
    data = await list_stuck_runs(
        db,
        pending_age_seconds=pending_age_seconds,
        running_lock_grace_seconds=running_lock_grace_seconds,
        limit=limit,
    )
    return ok(data)


@router.post("/stuck-runs/{visual_run_id}/mark-failed")
async def post_visual_pipeline_ops_mark_failed(
    visual_run_id: str,
    body: MarkStuckRunFailedBody,
    db: AsyncSession = Depends(get_db),
):
    """Mark one eligible stuck run FAILED. Audit required (fail-close). Feature-flagged."""
    try:
        data = await mark_single_stuck_run_failed(
            db,
            visual_run_id,
            reason=body.reason,
            confirm_visual_run_id=body.confirm_visual_run_id,
            pending_age_seconds=(
                body.pending_age_seconds
                if body.pending_age_seconds is not None
                else DEFAULT_PENDING_AGE_SECONDS
            ),
            running_lock_grace_seconds=(
                body.running_lock_grace_seconds
                if body.running_lock_grace_seconds is not None
                else DEFAULT_RUNNING_LOCK_GRACE_SECONDS
            ),
            require_admin_flag=True,
        )
    except MarkFailedError as exc:
        code = exc.code
        if code in {"RUN_MARK_FAILED_CONFIRM_MISMATCH", "RUN_MARK_FAILED_REASON_INVALID"}:
            raise HTTPException(status_code=400, detail=code) from None
        if code == "VISUAL_PIPELINE_RUN_NOT_FOUND":
            raise HTTPException(status_code=404, detail=code) from None
        raise HTTPException(status_code=409, detail=code) from None
    return ok(data)


@router.get("/audit-logs")
async def get_visual_pipeline_ops_audit_logs(
    event_type: str | None = Query(default=None),
    pipeline_id: str | None = Query(default=None),
    visual_run_id: str | None = Query(default=None),
    activation_id: str | None = Query(default=None),
    created_from: str | None = Query(default=None),
    created_to: str | None = Query(default=None),
    limit: int = Query(default=DEFAULT_AUDIT_LIST_LIMIT, ge=1, le=MAX_AUDIT_LIST_LIMIT),
    db: AsyncSession = Depends(get_db),
):
    """List audit logs (list payload minimized). Read-only."""
    data = await list_audit_logs(
        db,
        event_type=event_type,
        pipeline_id=pipeline_id,
        visual_run_id=visual_run_id,
        activation_id=activation_id,
        created_from=created_from,
        created_to=created_to,
        limit=limit,
    )
    return ok(data)


@router.get("/audit-logs/{audit_id}")
async def get_visual_pipeline_ops_audit_log(
    audit_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Audit log detail including before/after/metadata JSON. Read-only."""
    data = await get_audit_log(db, audit_id)
    if data is None:
        raise HTTPException(status_code=404, detail="AUDIT_LOG_NOT_FOUND")
    return ok(data)
