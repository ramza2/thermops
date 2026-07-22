"""R11-S6-2 Visual Pipeline Compile Result persistence (Option C).

Persists compile-preview artifacts and updates current_sync_status.
Does not materialize R10 targets, run connectors, or activate schedules.
"""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.time import utc_now
from app.models.entities import VisualPipelineCompileResult
from app.services.visual_pipeline.compile_preview_service import (
    calculate_graph_version_hash,
    compile_visual_pipeline_preview,
)
from app.services.visual_pipeline.visual_pipeline_service import (
    SYNC_NOT_COMPILED,
    VISUAL_PIPELINE_KIND,
    _get_visual_definition,
)

COMPILE_VERSION = "R11-S6-2"
SOURCE_COMPILE_API = "COMPILE_API"

SYNC_IN_SYNC = "IN_SYNC"
SYNC_STALE = "STALE"
SYNC_COMPILE_FAILED = "COMPILE_FAILED"


def _new_compile_result_id() -> str:
    return f"VPC-{uuid4().hex[:8].upper()}"


def _row_to_response(row: VisualPipelineCompileResult) -> dict[str, Any]:
    compiled_at = row.created_at.isoformat() if row.created_at else None
    if compiled_at and not compiled_at.endswith("Z") and "+" not in compiled_at:
        compiled_at = f"{compiled_at}Z" if "T" in compiled_at else compiled_at
    return {
        "compile_result_id": row.compile_result_id,
        "pipeline_id": row.pipeline_id,
        "compile_status": row.compile_status,
        "validation_level": row.validation_level,
        "graph_version_hash": row.graph_version_hash,
        "config_hash": row.config_hash,
        "compiled_at": compiled_at,
        "compile_version": row.compile_version,
        "compiled_artifact": row.compiled_artifact_json,
        "issues": list(row.issues_json or []),
        "persisted": True,
        "error_message": row.error_message,
        "source": row.source,
    }


async def get_latest_compile_result_row(
    db: AsyncSession,
    pipeline_id: str,
    *,
    status: str | None = None,
) -> VisualPipelineCompileResult | None:
    stmt = select(VisualPipelineCompileResult).where(
        VisualPipelineCompileResult.pipeline_id == pipeline_id
    )
    if status:
        stmt = stmt.where(VisualPipelineCompileResult.compile_status == status)
    stmt = stmt.order_by(VisualPipelineCompileResult.created_at.desc()).limit(1)
    return (await db.execute(stmt)).scalar_one_or_none()


async def count_compile_results(db: AsyncSession, pipeline_id: str) -> int:
    result = await db.execute(
        select(func.count())
        .select_from(VisualPipelineCompileResult)
        .where(VisualPipelineCompileResult.pipeline_id == pipeline_id)
    )
    return int(result.scalar_one() or 0)


async def resolve_sync_status_after_graph_update(
    db: AsyncSession,
    pipeline_id: str,
    new_graph: dict[str, Any] | None,
) -> str:
    """Resolve sync status using S6-1 graph hash vs persisted SUCCESS results."""
    new_hash = calculate_graph_version_hash(new_graph if isinstance(new_graph, dict) else {})
    latest_success = await get_latest_compile_result_row(db, pipeline_id, status="SUCCESS")
    if latest_success is None:
        return SYNC_NOT_COMPILED
    success_hash = latest_success.graph_version_hash or ""
    if new_hash != success_hash:
        return SYNC_STALE
    latest_any = await get_latest_compile_result_row(db, pipeline_id)
    if (
        latest_any is not None
        and latest_any.compile_status == "FAILED"
        and (latest_any.graph_version_hash or "") == new_hash
    ):
        return SYNC_COMPILE_FAILED
    return SYNC_IN_SYNC


async def persist_compile_result_row(
    db: AsyncSession,
    *,
    pipeline_id: str,
    preview: dict[str, Any],
    created_by: str | None = None,
) -> VisualPipelineCompileResult:
    status = str(preview.get("compile_status") or "FAILED").upper()
    issues = list(preview.get("issues") or [])
    error_message = None
    if status != "SUCCESS":
        error_codes = [i.get("code") for i in issues if isinstance(i, dict) and i.get("code")]
        error_message = ", ".join(str(c) for c in error_codes[:5]) if error_codes else "COMPILE_FAILED"

    row = VisualPipelineCompileResult(
        compile_result_id=_new_compile_result_id(),
        pipeline_id=pipeline_id,
        compile_status=status if status in {"SUCCESS", "FAILED"} else "FAILED",
        validation_level=str(preview.get("validation_level") or "STRICT"),
        graph_version_hash=preview.get("graph_version_hash"),
        config_hash=preview.get("config_hash"),
        compile_version=COMPILE_VERSION,
        compiled_artifact_json=preview.get("compiled_artifact") if status == "SUCCESS" else None,
        issues_json=issues,
        error_message=error_message,
        source=SOURCE_COMPILE_API,
        created_by=created_by,
        created_at=utc_now(),
    )
    db.add(row)
    await db.flush()
    return row


async def update_pipeline_sync_status_after_compile(
    db: AsyncSession,
    pipeline_id: str,
    compile_status: str,
) -> None:
    defn = await _get_visual_definition(db, pipeline_id)
    if compile_status == "SUCCESS":
        defn.current_sync_status = SYNC_IN_SYNC
    else:
        defn.current_sync_status = SYNC_COMPILE_FAILED
    defn.updated_at = utc_now()
    await db.flush()


async def compile_and_persist_visual_pipeline(
    db: AsyncSession,
    pipeline_id: str,
    *,
    validation_level: str = "STRICT",
    created_by: str | None = None,
) -> dict[str, Any]:
    """Compile saved graph, persist result row, update sync status. No R10 writes."""
    defn = await _get_visual_definition(db, pipeline_id)
    if (defn.pipeline_kind or "") != VISUAL_PIPELINE_KIND:
        raise LookupError("VISUAL_PIPELINE_NOT_FOUND")

    graph = defn.current_graph_json if isinstance(defn.current_graph_json, dict) else {}
    preview = compile_visual_pipeline_preview(
        pipeline_id,
        graph,
        validation_level=validation_level,
    )
    row = await persist_compile_result_row(
        db,
        pipeline_id=pipeline_id,
        preview=preview,
        created_by=created_by,
    )
    await update_pipeline_sync_status_after_compile(db, pipeline_id, row.compile_status)
    response = _row_to_response(row)
    # Prefer preview compiled_at formatting when present; keep persisted timestamps from row
    if preview.get("compiled_at") and row.compile_status == preview.get("compile_status"):
        # Keep DB created_at as source of truth for persisted_at
        pass
    return response


async def get_latest_visual_pipeline_compile_result(
    db: AsyncSession,
    pipeline_id: str,
) -> dict[str, Any]:
    await _get_visual_definition(db, pipeline_id)
    row = await get_latest_compile_result_row(db, pipeline_id)
    if row is None:
        raise LookupError("COMPILE_RESULT_NOT_FOUND")
    return _row_to_response(row)
