"""R11 Visual Pipeline Studio API — catalog (S1) + graph CRUD (S2)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.response import ok
from app.services.visual_pipeline.component_catalog_service import (
    get_component,
    list_components,
    list_connection_rules,
)
from app.services.visual_pipeline.graph_schema_service import VisualPipelineGraphError
from app.services.visual_pipeline.visual_pipeline_service import (
    VisualPipelineError,
    archive_visual_pipeline,
    create_visual_pipeline,
    create_visual_pipeline_version,
    get_visual_pipeline,
    get_visual_pipeline_version,
    list_visual_pipeline_versions,
    list_visual_pipelines,
    update_visual_pipeline,
)

router = APIRouter(tags=["Visual Pipeline Studio"])


class VisualPipelineCreateBody(BaseModel):
    pipeline_name: str
    description: str | None = None
    graph: Any = None
    created_by: str | None = None


class VisualPipelineUpdateBody(BaseModel):
    pipeline_name: str | None = None
    description: str | None = None
    status: str | None = None
    graph: Any = None
    change_summary: str | None = None
    create_version: bool = False


class VisualPipelineVersionCreateBody(BaseModel):
    change_summary: str | None = Field(default=None)


class VisualPipelineValidateGraphBody(BaseModel):
    graph: Any = None
    pipeline_id: str | None = None
    validation_level: str = Field(default="BASIC", description="BASIC | STRICT")


class VisualPipelineValidateBody(BaseModel):
    graph: Any = None
    validation_level: str = Field(default="BASIC", description="BASIC | STRICT")


# --- S1 Catalog (static paths before /{pipeline_id}) ---


@router.get("/visual-pipelines/components")
async def get_visual_pipeline_components(
    status: str | None = Query(default=None, description="ACTIVE | DISABLED | EXPERIMENTAL"),
    category: str | None = Query(default=None, description="DATA_INPUT | TRANSFORM | LOAD | ..."),
):
    data = list_components(status=status, category=category)
    return ok(data)


@router.get("/visual-pipelines/components/{component_type}")
async def get_visual_pipeline_component(component_type: str):
    try:
        item = get_component(component_type)
    except LookupError:
        raise HTTPException(status_code=404, detail="COMPONENT_NOT_FOUND") from None
    return ok(item)


@router.get("/visual-pipelines/connection-rules")
async def get_visual_pipeline_connection_rules():
    return ok(list_connection_rules())


@router.post("/visual-pipelines/validate-graph")
async def post_validate_visual_pipeline_graph(body: VisualPipelineValidateGraphBody):
    """Validate a client graph. Does not write to DB."""
    from app.services.visual_pipeline.graph_validation_service import validate_visual_pipeline_graph

    result = validate_visual_pipeline_graph(
        body.graph,
        validation_level=body.validation_level,
        pipeline_id=body.pipeline_id,
    )
    return ok(result)


# --- S2 CRUD / versions ---


@router.get("/visual-pipelines")
async def get_visual_pipelines(
    status: str | None = Query(default=None),
    q: str | None = Query(default=None),
    include_archived: bool = Query(default=False),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    data = await list_visual_pipelines(
        db,
        status=status,
        q=q,
        include_archived=include_archived,
        limit=limit,
        offset=offset,
    )
    return ok(data)


@router.post("/visual-pipelines")
async def post_visual_pipeline(body: VisualPipelineCreateBody, db: AsyncSession = Depends(get_db)):
    try:
        item = await create_visual_pipeline(db, body.model_dump())
    except VisualPipelineGraphError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except VisualPipelineError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ok(item, message="Visual Pipeline이 생성되었습니다.")


@router.get("/visual-pipelines/{pipeline_id}/versions")
async def get_visual_pipeline_versions(pipeline_id: str, db: AsyncSession = Depends(get_db)):
    try:
        data = await list_visual_pipeline_versions(db, pipeline_id)
    except LookupError:
        raise HTTPException(status_code=404, detail="VISUAL_PIPELINE_NOT_FOUND") from None
    return ok(data)


@router.post("/visual-pipelines/{pipeline_id}/versions")
async def post_visual_pipeline_version(
    pipeline_id: str,
    body: VisualPipelineVersionCreateBody | None = None,
    db: AsyncSession = Depends(get_db),
):
    payload = body.model_dump() if body else {}
    try:
        item = await create_visual_pipeline_version(
            db, pipeline_id, change_summary=payload.get("change_summary")
        )
    except LookupError:
        raise HTTPException(status_code=404, detail="VISUAL_PIPELINE_NOT_FOUND") from None
    except VisualPipelineError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ok(item, message="Visual Pipeline version이 생성되었습니다.")


@router.get("/visual-pipelines/{pipeline_id}/versions/{version_id}")
async def get_visual_pipeline_version_detail(
    pipeline_id: str,
    version_id: str,
    db: AsyncSession = Depends(get_db),
):
    try:
        item = await get_visual_pipeline_version(db, pipeline_id, version_id)
    except LookupError as exc:
        detail = str(exc) if str(exc) else "VISUAL_PIPELINE_VERSION_NOT_FOUND"
        raise HTTPException(status_code=404, detail=detail) from None
    return ok(item)


@router.post("/visual-pipelines/{pipeline_id}/archive")
async def post_archive_visual_pipeline(pipeline_id: str, db: AsyncSession = Depends(get_db)):
    try:
        item = await archive_visual_pipeline(db, pipeline_id)
    except LookupError:
        raise HTTPException(status_code=404, detail="VISUAL_PIPELINE_NOT_FOUND") from None
    return ok(item, message="Visual Pipeline이 보관 처리되었습니다.")


@router.post("/visual-pipelines/{pipeline_id}/validate")
async def post_validate_visual_pipeline(
    pipeline_id: str,
    body: VisualPipelineValidateBody | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Validate body graph or saved current_graph_json. Does not write to DB."""
    from app.services.visual_pipeline.graph_validation_service import validate_visual_pipeline_graph

    payload = body.model_dump() if body else {}
    graph = payload.get("graph")
    level = payload.get("validation_level") or "BASIC"
    if graph is None:
        try:
            detail = await get_visual_pipeline(db, pipeline_id)
        except LookupError:
            raise HTTPException(status_code=404, detail="VISUAL_PIPELINE_NOT_FOUND") from None
        graph = detail.get("graph")
    result = validate_visual_pipeline_graph(graph, validation_level=level, pipeline_id=pipeline_id)
    return ok(result)


@router.get("/visual-pipelines/{pipeline_id}")
async def get_visual_pipeline_detail(pipeline_id: str, db: AsyncSession = Depends(get_db)):
    try:
        item = await get_visual_pipeline(db, pipeline_id)
    except LookupError:
        raise HTTPException(status_code=404, detail="VISUAL_PIPELINE_NOT_FOUND") from None
    return ok(item)


@router.put("/visual-pipelines/{pipeline_id}")
async def put_visual_pipeline(
    pipeline_id: str,
    body: VisualPipelineUpdateBody,
    db: AsyncSession = Depends(get_db),
):
    try:
        item = await update_visual_pipeline(db, pipeline_id, body.model_dump(exclude_unset=True))
    except LookupError:
        raise HTTPException(status_code=404, detail="VISUAL_PIPELINE_NOT_FOUND") from None
    except VisualPipelineGraphError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except VisualPipelineError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ok(item, message="Visual Pipeline이 수정되었습니다.")
