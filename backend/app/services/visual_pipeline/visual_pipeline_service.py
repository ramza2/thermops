"""R11-S2 Visual Pipeline CRUD / version storage on tb_pipeline_*."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.time import utc_now
from app.models.entities import PipelineDefinition, PipelineDefinitionVersion, PipelineTemplate
from app.services.visual_pipeline.component_catalog_service import COMPONENT_CONTRACT_VERSION
from app.services.visual_pipeline.graph_schema_service import (
    VisualPipelineGraphError,
    empty_graph,
    graph_counts,
    normalize_graph,
)

VISUAL_PIPELINE_KIND = "VISUAL_DATA_LOAD"
VISUAL_PIPELINE_TYPE = "DATA_LOAD"
VISUAL_TEMPLATE_ID = "PT-VISUAL-DATA-LOAD"
SYNC_NOT_COMPILED = "NOT_COMPILED"
SYNC_IN_SYNC = "IN_SYNC"
SYNC_STALE = "STALE"
SYNC_COMPILE_FAILED = "COMPILE_FAILED"


class VisualPipelineError(ValueError):
    def __init__(self, message: str, *, error_code: str = "VISUAL_PIPELINE_ERROR") -> None:
        super().__init__(message)
        self.error_code = error_code


def _graph_or_empty(raw: Any) -> dict[str, Any]:
    if not raw or not isinstance(raw, dict):
        return empty_graph()
    return raw


def _definition_dict(defn: PipelineDefinition, *, include_graph: bool = True) -> dict[str, Any]:
    graph = _graph_or_empty(defn.current_graph_json)
    node_count, edge_count = graph_counts(graph)
    item: dict[str, Any] = {
        "pipeline_id": defn.pipeline_id,
        "pipeline_name": defn.pipeline_name,
        "description": defn.description,
        "template_id": defn.template_id,
        "pipeline_kind": defn.pipeline_kind or VISUAL_PIPELINE_KIND,
        "pipeline_type": defn.pipeline_type,
        "status": defn.status,
        "current_sync_status": defn.current_sync_status or SYNC_NOT_COMPILED,
        "created_by": defn.created_by,
        "created_at": defn.created_at.isoformat() if defn.created_at else None,
        "updated_at": defn.updated_at.isoformat() if defn.updated_at else None,
        "has_graph": bool(node_count or edge_count or defn.current_graph_json),
        "node_count": node_count,
        "edge_count": edge_count,
        "component_contract_version": COMPONENT_CONTRACT_VERSION,
    }
    if include_graph:
        item["graph"] = graph
    return item


def _version_dict(row: PipelineDefinitionVersion) -> dict[str, Any]:
    snap = row.snapshot_json or {}
    graph = snap.get("graph") if isinstance(snap, dict) else None
    node_count, edge_count = graph_counts(graph if isinstance(graph, dict) else None)
    return {
        "version_id": row.version_id,
        "pipeline_id": row.pipeline_id,
        "version_no": row.version_no,
        "change_summary": row.change_summary,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "snapshot": snap,
        "has_graph": "graph" in snap if isinstance(snap, dict) else False,
        "node_count": node_count,
        "edge_count": edge_count,
    }


async def _ensure_visual_template(db: AsyncSession) -> PipelineTemplate:
    tmpl = (
        await db.execute(
            select(PipelineTemplate).where(PipelineTemplate.template_id == VISUAL_TEMPLATE_ID)
        )
    ).scalar_one_or_none()
    if not tmpl:
        raise VisualPipelineError(
            f"skeleton template {VISUAL_TEMPLATE_ID}가 없습니다. apply_dev_migrations.py를 실행하세요.",
            error_code="VISUAL_TEMPLATE_MISSING",
        )
    return tmpl


async def _get_visual_definition(db: AsyncSession, pipeline_id: str) -> PipelineDefinition:
    defn = (
        await db.execute(
            select(PipelineDefinition).where(PipelineDefinition.pipeline_id == pipeline_id)
        )
    ).scalar_one_or_none()
    if not defn or (defn.pipeline_kind or "") != VISUAL_PIPELINE_KIND:
        raise LookupError("VISUAL_PIPELINE_NOT_FOUND")
    return defn


async def _next_version_no(db: AsyncSession, pipeline_id: str) -> int:
    current = (
        await db.execute(
            select(func.max(PipelineDefinitionVersion.version_no)).where(
                PipelineDefinitionVersion.pipeline_id == pipeline_id
            )
        )
    ).scalar()
    return int(current or 0) + 1


async def _save_visual_version(
    db: AsyncSession,
    defn: PipelineDefinition,
    *,
    change_summary: str | None = None,
) -> PipelineDefinitionVersion:
    version_no = await _next_version_no(db, defn.pipeline_id)
    graph = _graph_or_empty(defn.current_graph_json)
    row = PipelineDefinitionVersion(
        version_id=f"PDV-{uuid4().hex[:8].upper()}",
        pipeline_id=defn.pipeline_id,
        version_no=version_no,
        snapshot_json={
            "pipeline_name": defn.pipeline_name,
            "description": defn.description,
            "pipeline_kind": VISUAL_PIPELINE_KIND,
            "pipeline_type": defn.pipeline_type,
            "status": defn.status,
            "graph": graph,
            "component_contract_version": COMPONENT_CONTRACT_VERSION,
            "validation_result": None,
            "compiled_target": None,
        },
        change_summary=change_summary,
        created_at=utc_now(),
    )
    db.add(row)
    await db.flush()
    return row


async def list_visual_pipelines(
    db: AsyncSession,
    *,
    status: str | None = None,
    q: str | None = None,
    include_archived: bool = False,
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    limit = max(1, min(int(limit or 50), 200))
    offset = max(0, int(offset or 0))
    base = select(PipelineDefinition).where(
        PipelineDefinition.pipeline_kind == VISUAL_PIPELINE_KIND
    )
    if not include_archived:
        base = base.where(PipelineDefinition.status != "ARCHIVED")
        base = base.where(PipelineDefinition.active_yn == "Y")
    if status:
        base = base.where(PipelineDefinition.status == status.strip().upper())
    if q and q.strip():
        like = f"%{q.strip()}%"
        base = base.where(
            or_(
                PipelineDefinition.pipeline_name.ilike(like),
                PipelineDefinition.description.ilike(like),
                PipelineDefinition.pipeline_id.ilike(like),
            )
        )
    total = int(
        (
            await db.execute(select(func.count()).select_from(base.order_by(None).subquery()))
        ).scalar()
        or 0
    )
    rows = (
        await db.execute(
            base.order_by(
                PipelineDefinition.updated_at.desc(),
                PipelineDefinition.created_at.desc(),
            )
            .offset(offset)
            .limit(limit)
        )
    ).scalars().all()
    return {
        "items": [_definition_dict(r, include_graph=False) for r in rows],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


async def create_visual_pipeline(db: AsyncSession, payload: dict[str, Any]) -> dict[str, Any]:
    await _ensure_visual_template(db)
    name = str(payload.get("pipeline_name") or "").strip()
    if not name:
        raise VisualPipelineError("pipeline_name이 필요합니다.", error_code="PIPELINE_NAME_REQUIRED")
    try:
        graph = normalize_graph(payload.get("graph"))
    except VisualPipelineGraphError:
        raise

    pipeline_id = f"PIPE-{uuid4().hex[:6].upper()}"
    defn = PipelineDefinition(
        pipeline_id=pipeline_id,
        template_id=VISUAL_TEMPLATE_ID,
        pipeline_name=name,
        description=payload.get("description"),
        pipeline_type=VISUAL_PIPELINE_TYPE,
        pipeline_kind=VISUAL_PIPELINE_KIND,
        airflow_dag_id=None,
        node_config_json={},
        edge_config_json={"edges": []},
        runtime_params_json=None,
        schedule_config_json=None,
        validation_result_json=None,
        current_graph_json=graph,
        current_sync_status=SYNC_NOT_COMPILED,
        status="DRAFT",
        active_yn="Y",
        created_by=payload.get("created_by"),
        created_at=utc_now(),
        updated_at=utc_now(),
    )
    db.add(defn)
    await db.flush()
    await _save_visual_version(db, defn, change_summary="initial create")
    return _definition_dict(defn)


async def get_visual_pipeline(db: AsyncSession, pipeline_id: str) -> dict[str, Any]:
    defn = await _get_visual_definition(db, pipeline_id)
    return _definition_dict(defn)


async def update_visual_pipeline(
    db: AsyncSession,
    pipeline_id: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    defn = await _get_visual_definition(db, pipeline_id)
    if defn.status == "ARCHIVED":
        raise VisualPipelineError("ARCHIVED Visual Pipeline은 수정할 수 없습니다.", error_code="ARCHIVED")

    if payload.get("pipeline_name") is not None:
        name = str(payload.get("pipeline_name") or "").strip()
        if not name:
            raise VisualPipelineError("pipeline_name이 비어 있을 수 없습니다.", error_code="PIPELINE_NAME_REQUIRED")
        defn.pipeline_name = name
    if "description" in payload:
        defn.description = payload.get("description")
    if payload.get("status") is not None:
        status = str(payload["status"]).strip().upper()
        if status not in {"DRAFT", "VALIDATED", "ACTIVE", "ARCHIVED"}:
            raise VisualPipelineError(f"지원하지 않는 status입니다: {status}", error_code="INVALID_STATUS")
        defn.status = status
        if status == "ARCHIVED":
            defn.active_yn = "N"
        else:
            defn.active_yn = "Y"
    if "graph" in payload:
        try:
            new_graph = normalize_graph(payload.get("graph"))
        except VisualPipelineGraphError:
            raise
        defn.current_graph_json = new_graph
        from app.services.visual_pipeline.compile_result_service import (
            resolve_sync_status_after_graph_update,
        )

        defn.current_sync_status = await resolve_sync_status_after_graph_update(
            db,
            pipeline_id,
            new_graph,
        )

    defn.updated_at = utc_now()
    await db.flush()
    create_version = bool(payload.get("create_version", False))
    if "graph" in payload and create_version:
        await _save_visual_version(
            db,
            defn,
            change_summary=payload.get("change_summary") or "graph update",
        )
    return _definition_dict(defn)


async def archive_visual_pipeline(db: AsyncSession, pipeline_id: str) -> dict[str, Any]:
    defn = await _get_visual_definition(db, pipeline_id)
    defn.status = "ARCHIVED"
    defn.active_yn = "N"
    defn.updated_at = utc_now()
    await db.flush()
    await _save_visual_version(db, defn, change_summary="archive")
    return _definition_dict(defn)


async def create_visual_pipeline_version(
    db: AsyncSession,
    pipeline_id: str,
    *,
    change_summary: str | None = None,
) -> dict[str, Any]:
    defn = await _get_visual_definition(db, pipeline_id)
    if defn.status == "ARCHIVED":
        raise VisualPipelineError("ARCHIVED Visual Pipeline은 version을 생성할 수 없습니다.", error_code="ARCHIVED")
    row = await _save_visual_version(
        db,
        defn,
        change_summary=change_summary or "manual snapshot",
    )
    return _version_dict(row)


async def list_visual_pipeline_versions(db: AsyncSession, pipeline_id: str) -> dict[str, Any]:
    await _get_visual_definition(db, pipeline_id)
    rows = (
        await db.execute(
            select(PipelineDefinitionVersion)
            .where(PipelineDefinitionVersion.pipeline_id == pipeline_id)
            .order_by(PipelineDefinitionVersion.version_no.desc())
        )
    ).scalars().all()
    return {"items": [_version_dict(r) for r in rows], "total": len(rows)}


async def get_visual_pipeline_version(
    db: AsyncSession,
    pipeline_id: str,
    version_id: str,
) -> dict[str, Any]:
    await _get_visual_definition(db, pipeline_id)
    row = (
        await db.execute(
            select(PipelineDefinitionVersion).where(
                PipelineDefinitionVersion.pipeline_id == pipeline_id,
                PipelineDefinitionVersion.version_id == version_id,
            )
        )
    ).scalar_one_or_none()
    if not row:
        raise LookupError("VISUAL_PIPELINE_VERSION_NOT_FOUND")
    return _version_dict(row)
