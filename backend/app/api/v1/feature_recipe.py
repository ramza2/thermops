from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.response import ok
from app.schemas.api import FeatureRecipePreviewRequest, FeatureRecipeValidateRequest
from app.services.feature_column_role_service import get_mapping_or_raise, list_column_roles
from app.services.feature_recipe_preview_service import preview_feature_recipe
from app.services.feature_recipe_template_service import (
    evaluate_template_availability,
    get_catalog_for_mapping,
    get_template_catalog,
    get_template_spec,
    validate_recipe_definition,
)

router = APIRouter(tags=["Feature Recipe"])


@router.get("/feature-recipe-templates")
async def list_feature_recipe_templates(
    mapping_id: str | None = Query(default=None),
    target_table: str | None = Query(default=None),
    category: str | None = Query(default=None),
    status: str | None = Query(default=None),
    include_availability: bool = Query(default=True),
    db: AsyncSession = Depends(get_db),
):
    _ = target_table
    try:
        if mapping_id and include_availability:
            result = await get_catalog_for_mapping(
                db,
                mapping_id,
                category=category,
                status=status,
                include_availability=True,
            )
            result["mapping_id"] = mapping_id
        else:
            result = get_template_catalog(
                role_summary=None,
                category=category,
                status=status,
                include_availability=False,
            )
            if mapping_id:
                result["mapping_id"] = mapping_id
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ok(result)


@router.get("/feature-recipe-templates/{recipe_type}")
async def get_feature_recipe_template(
    recipe_type: str,
    mapping_id: str | None = Query(default=None),
    include_availability: bool = Query(default=True),
    db: AsyncSession = Depends(get_db),
):
    spec = get_template_spec(recipe_type)
    if not spec:
        raise HTTPException(status_code=404, detail="NOT_FOUND")

    item = spec.to_dict()
    if mapping_id and include_availability:
        try:
            role_data = await list_column_roles(db, mapping_id=mapping_id, include_inferred=False)
            avail = evaluate_template_availability(spec, role_data.get("summary") or {})
            item["available"] = avail["available"]
            item["availability"] = avail
            item["mapping_id"] = mapping_id
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
    else:
        item["available"] = None
        item["availability"] = None

    return ok(item)


@router.post("/feature-recipes/validate")
async def validate_feature_recipe(
    body: FeatureRecipeValidateRequest,
    db: AsyncSession = Depends(get_db),
):
    recipe = body.model_dump()
    mapping_columns: list[dict] | None = None
    role_items: list[dict] | None = None

    if body.mapping_id:
        try:
            mapping = await get_mapping_or_raise(db, body.mapping_id)
            mapping_columns = list(mapping.columns or [])
            role_data = await list_column_roles(db, mapping_id=body.mapping_id, include_inferred=False)
            role_items = role_data.get("items") or []
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    result = await validate_recipe_definition(
        db,
        recipe,
        mapping_columns=mapping_columns,
        role_items=role_items,
    )
    return ok(result)


@router.post("/feature-recipes/preview")
async def preview_feature_recipe_api(
    body: FeatureRecipePreviewRequest,
    db: AsyncSession = Depends(get_db),
):
    result = await preview_feature_recipe(db, body.model_dump())
    return ok(result)
