"""R11-S7-8 Visual Pipeline Schedule Activation.

Activation toggles schedule authority only — never calls run_load or creates run rows.
Due enqueue is handled by schedule_worker_service / vp-schedule-worker.
R10 tb_data_load_schedule.active_yn stays false (D15).
"""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.time import utc_now
from app.models.entities import (
    DataLoadSchedule,
    VisualPipelineCompileResult,
    VisualPipelineMaterializationResult,
    VisualPipelineScheduleActivation,
)
from app.services.schedule_time_service import compute_next_run_at
from app.services.visual_pipeline.compile_preview_service import calculate_graph_version_hash
from app.services.visual_pipeline.compile_result_service import SYNC_IN_SYNC
from app.services.visual_pipeline.visual_pipeline_service import (
    VISUAL_PIPELINE_KIND,
    _get_visual_definition,
    get_visual_pipeline,
)

ACTIVATION_VERSION = "R11-S7-8"
STATUS_ACTIVE = "ACTIVE"
STATUS_INACTIVE = "INACTIVE"
MIRROR_ACTIVE = "ACTIVE"
MIRROR_INACTIVE = "INACTIVE"
DEFAULT_TZ = "Asia/Seoul"


class ActivationPreconditionError(Exception):
    """HTTP 409."""

    def __init__(self, code: str, message: str | None = None) -> None:
        self.code = code
        self.message = message or code
        super().__init__(self.message)


class ActivationNotFoundError(Exception):
    """HTTP 404."""

    def __init__(self, code: str = "SCHEDULE_ACTIVATION_NOT_FOUND") -> None:
        self.code = code
        super().__init__(code)


def _new_activation_id() -> str:
    return f"VPA-{uuid4().hex[:8].upper()}"


def _iso(dt: Any) -> str | None:
    if dt is None:
        return None
    text = dt.isoformat() if hasattr(dt, "isoformat") else str(dt)
    if text and not text.endswith("Z") and "+" not in text and "T" in text:
        return f"{text}Z"
    return text


def _schedule_dict_from_row(row: DataLoadSchedule) -> dict[str, Any]:
    return {
        "schedule_type": row.schedule_type,
        "cron_expression": row.cron_expression,
        "timezone": row.timezone or DEFAULT_TZ,
        "start_at": row.start_at,
        "end_at": row.end_at,
        "active_yn": False,
    }


def _row_to_response(row: VisualPipelineScheduleActivation) -> dict[str, Any]:
    meta = dict(row.metadata_json or {})
    return {
        "activation_id": row.activation_id,
        "pipeline_id": row.pipeline_id,
        "materialization_result_id": row.materialization_result_id,
        "compile_result_id": row.compile_result_id,
        "r10_schedule_id": row.r10_schedule_id,
        "activation_status": row.activation_status,
        "cron_expression": row.cron_expression,
        "timezone": row.timezone,
        "activated_at": _iso(row.activated_at),
        "deactivated_at": _iso(row.deactivated_at),
        "next_due_at": _iso(row.next_due_at),
        "last_triggered_at": _iso(row.last_triggered_at),
        "trigger_count": int(row.trigger_count or 0),
        "metadata": meta,
        "created_at": _iso(row.created_at),
        "updated_at": _iso(row.updated_at),
    }


def assert_schedule_activation_enabled() -> None:
    if not get_settings().vp_schedule_activation_enabled:
        raise ActivationPreconditionError(
            "SCHEDULE_ACTIVATION_DISABLED",
            "THERMOOPS_VP_SCHEDULE_ACTIVATION_ENABLED is false.",
        )


async def _latest_success_compile(
    db: AsyncSession, pipeline_id: str
) -> VisualPipelineCompileResult:
    row = (
        await db.execute(
            select(VisualPipelineCompileResult)
            .where(
                VisualPipelineCompileResult.pipeline_id == pipeline_id,
                VisualPipelineCompileResult.compile_status == "SUCCESS",
            )
            .order_by(VisualPipelineCompileResult.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if row is None:
        raise ActivationPreconditionError("COMPILE_REQUIRED")
    return row


async def _latest_success_materialization(
    db: AsyncSession, pipeline_id: str
) -> VisualPipelineMaterializationResult:
    row = (
        await db.execute(
            select(VisualPipelineMaterializationResult)
            .where(
                VisualPipelineMaterializationResult.pipeline_id == pipeline_id,
                VisualPipelineMaterializationResult.materialization_status == "SUCCESS",
            )
            .order_by(VisualPipelineMaterializationResult.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if row is None:
        raise ActivationPreconditionError("MATERIALIZATION_REQUIRED")
    return row


async def _get_active_activation(
    db: AsyncSession, pipeline_id: str
) -> VisualPipelineScheduleActivation | None:
    return (
        await db.execute(
            select(VisualPipelineScheduleActivation).where(
                VisualPipelineScheduleActivation.pipeline_id == pipeline_id,
                VisualPipelineScheduleActivation.activation_status == STATUS_ACTIVE,
            )
        )
    ).scalar_one_or_none()


async def activate_schedule(
    db: AsyncSession,
    pipeline_id: str,
    body: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Create ACTIVE activation. Does not call run_load or create run rows."""
    assert_schedule_activation_enabled()
    _ = body  # reserved for future options

    defn = await _get_visual_definition(db, pipeline_id)
    if (defn.pipeline_kind or "") != VISUAL_PIPELINE_KIND:
        raise LookupError("VISUAL_PIPELINE_NOT_FOUND")

    detail = await get_visual_pipeline(db, pipeline_id)
    graph = detail.get("graph") if isinstance(detail.get("graph"), dict) else {}
    current_hash = calculate_graph_version_hash(graph)

    if (defn.current_sync_status or "") != SYNC_IN_SYNC:
        raise ActivationPreconditionError("PIPELINE_STALE")

    if await _get_active_activation(db, pipeline_id) is not None:
        raise ActivationPreconditionError("ACTIVE_ACTIVATION_EXISTS")

    compile_row = await _latest_success_compile(db, pipeline_id)
    mat_row = await _latest_success_materialization(db, pipeline_id)

    compile_hash = compile_row.graph_version_hash or ""
    mat_hash = mat_row.graph_version_hash or ""
    if current_hash != compile_hash or current_hash != mat_hash:
        raise ActivationPreconditionError("PIPELINE_STALE")

    objects = dict(mat_row.objects_json or {})
    r10_schedule_id = str(objects.get("schedule_id") or "").strip()
    if not r10_schedule_id:
        created = dict(mat_row.created_json or {})
        updated = dict(mat_row.updated_json or {})
        r10_schedule_id = str(created.get("schedule_id") or updated.get("schedule_id") or "").strip()
    if not r10_schedule_id:
        raise ActivationPreconditionError("R10_SCHEDULE_MISSING")

    schedule = (
        await db.execute(
            select(DataLoadSchedule).where(DataLoadSchedule.schedule_id == r10_schedule_id)
        )
    ).scalar_one_or_none()
    if schedule is None:
        raise ActivationPreconditionError("R10_SCHEDULE_MISSING")

    cron_expression = (schedule.cron_expression or "").strip() or None
    schedule_type = str(schedule.schedule_type or "").upper()
    if schedule_type == "CRON" and not cron_expression:
        raise ActivationPreconditionError("CRON_MISSING")
    if schedule_type == "MANUAL":
        raise ActivationPreconditionError("CRON_MISSING")

    tz = (schedule.timezone or DEFAULT_TZ).strip() or DEFAULT_TZ
    now = utc_now()
    next_due = compute_next_run_at(_schedule_dict_from_row(schedule), from_time=now)
    if next_due is None:
        raise ActivationPreconditionError("CRON_MISSING")

    # Keep R10 inactive — VP schedule-worker owns due detection.
    if schedule.active_yn:
        schedule.active_yn = False

    activation = VisualPipelineScheduleActivation(
        activation_id=_new_activation_id(),
        pipeline_id=pipeline_id,
        materialization_result_id=mat_row.materialization_result_id,
        compile_result_id=compile_row.compile_result_id,
        r10_schedule_id=r10_schedule_id,
        activation_status=STATUS_ACTIVE,
        cron_expression=cron_expression,
        timezone=tz,
        activated_at=now,
        deactivated_at=None,
        next_due_at=next_due,
        last_triggered_at=None,
        trigger_count=0,
        metadata_json={
            "graph_version_hash": current_hash,
            "r10_active_yn": False,
            "source": "visual_pipeline_schedule_activation",
            "activation_version": ACTIVATION_VERSION,
            "schedule_type": schedule_type,
        },
        created_at=now,
        updated_at=now,
    )
    db.add(activation)

    mat_row.activation = MIRROR_ACTIVE
    await db.flush()
    await db.commit()
    await db.refresh(activation)
    return _row_to_response(activation)


async def deactivate_schedule(
    db: AsyncSession,
    pipeline_id: str,
    activation_id: str,
) -> dict[str, Any]:
    """Set activation INACTIVE. Idempotent if already inactive. Does not cancel runs."""
    assert_schedule_activation_enabled()

    defn = await _get_visual_definition(db, pipeline_id)
    if (defn.pipeline_kind or "") != VISUAL_PIPELINE_KIND:
        raise LookupError("VISUAL_PIPELINE_NOT_FOUND")

    row = (
        await db.execute(
            select(VisualPipelineScheduleActivation).where(
                VisualPipelineScheduleActivation.activation_id == activation_id,
                VisualPipelineScheduleActivation.pipeline_id == pipeline_id,
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise ActivationNotFoundError()

    now = utc_now()
    if row.activation_status != STATUS_INACTIVE:
        row.activation_status = STATUS_INACTIVE
        row.deactivated_at = now
        row.updated_at = now

        mat_row = (
            await db.execute(
                select(VisualPipelineMaterializationResult).where(
                    VisualPipelineMaterializationResult.materialization_result_id
                    == row.materialization_result_id,
                    VisualPipelineMaterializationResult.pipeline_id == pipeline_id,
                )
            )
        ).scalar_one_or_none()
        if mat_row is not None:
            mat_row.activation = MIRROR_INACTIVE

        # Never flip R10 active_yn to true; ensure false if somehow true.
        schedule = (
            await db.execute(
                select(DataLoadSchedule).where(DataLoadSchedule.schedule_id == row.r10_schedule_id)
            )
        ).scalar_one_or_none()
        if schedule is not None and schedule.active_yn:
            schedule.active_yn = False

        await db.flush()
        await db.commit()
        await db.refresh(row)
    return _row_to_response(row)


async def get_current_activation(db: AsyncSession, pipeline_id: str) -> dict[str, Any] | None:
    defn = await _get_visual_definition(db, pipeline_id)
    if (defn.pipeline_kind or "") != VISUAL_PIPELINE_KIND:
        raise LookupError("VISUAL_PIPELINE_NOT_FOUND")

    active = await _get_active_activation(db, pipeline_id)
    if active is not None:
        return _row_to_response(active)

    latest = (
        await db.execute(
            select(VisualPipelineScheduleActivation)
            .where(VisualPipelineScheduleActivation.pipeline_id == pipeline_id)
            .order_by(VisualPipelineScheduleActivation.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    return _row_to_response(latest) if latest else None


async def list_activations(
    db: AsyncSession,
    pipeline_id: str,
    *,
    limit: int = 20,
) -> dict[str, Any]:
    defn = await _get_visual_definition(db, pipeline_id)
    if (defn.pipeline_kind or "") != VISUAL_PIPELINE_KIND:
        raise LookupError("VISUAL_PIPELINE_NOT_FOUND")

    rows = (
        await db.execute(
            select(VisualPipelineScheduleActivation)
            .where(VisualPipelineScheduleActivation.pipeline_id == pipeline_id)
            .order_by(VisualPipelineScheduleActivation.created_at.desc())
            .limit(max(1, min(limit, 100)))
        )
    ).scalars().all()
    return {
        "items": [_row_to_response(r) for r in rows],
        "total": len(rows),
    }
