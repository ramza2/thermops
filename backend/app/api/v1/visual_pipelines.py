"""R11-S1 Visual Pipeline Studio — Component Catalog / Contract API (read-only)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.core.response import ok
from app.services.visual_pipeline.component_catalog_service import (
    get_component,
    list_components,
    list_connection_rules,
)

router = APIRouter(tags=["Visual Pipeline Studio"])


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
