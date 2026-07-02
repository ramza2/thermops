from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.response import ok
from app.schemas.api import (
    FeatureRecipeComparePreviewBuildRequest,
    FeatureRecipeCreateRequest,
    FeatureRecipePreviewRequest,
    FeatureRecipePreviewSavedRequest,
    FeatureRecipeUpdateRequest,
    FeatureRecipeValidateRequest,
)
from app.services.feature_recipe_build_ops_service import (
    compare_preview_with_build,
    list_recipe_build_history,
)
from app.services.feature_column_role_service import get_mapping_or_raise, list_column_roles
from app.services.feature_recipe_preview_service import preview_feature_recipe
from app.services.feature_recipe_service import (
    RecipeServiceError,
    archive_recipe,
    create_recipe,
    get_recipe_or_raise,
    list_recipes,
    preview_saved_recipe,
    publish_recipe,
    recipe_to_dict,
    update_recipe,
    validate_saved_recipe,
)
from app.services.feature_recipe_template_service import (
    evaluate_template_availability,
    get_catalog_for_mapping,
    get_template_catalog,
    get_template_spec,
    validate_recipe_definition,
)

router = APIRouter(tags=["Feature Recipe"])


def _recipe_error(exc: RecipeServiceError) -> HTTPException:
    return HTTPException(
        status_code=exc.status_code,
        detail={"code": exc.code, "message": exc.message},
    )


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


@router.post("/feature-recipes")
async def create_feature_recipe(
    body: FeatureRecipeCreateRequest,
    db: AsyncSession = Depends(get_db),
):
    try:
        result = await create_recipe(db, body.model_dump())
    except RecipeServiceError as exc:
        raise _recipe_error(exc) from exc
    return ok(result, message="Recipe 초안이 저장되었습니다.")


@router.get("/feature-recipes")
async def list_feature_recipes(
    status: str | None = Query(default=None),
    recipe_type: str | None = Query(default=None),
    mapping_id: str | None = Query(default=None),
    feature_name: str | None = Query(default=None),
    include_archived: bool = Query(default=False),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    result = await list_recipes(
        db,
        status=status,
        recipe_type=recipe_type,
        mapping_id=mapping_id,
        feature_name=feature_name,
        include_archived=include_archived,
        limit=limit,
        offset=offset,
    )
    return ok(result)


@router.get("/feature-recipes/{recipe_id}")
async def get_feature_recipe(recipe_id: str, db: AsyncSession = Depends(get_db)):
    try:
        recipe = await get_recipe_or_raise(db, recipe_id)
    except RecipeServiceError as exc:
        raise _recipe_error(exc) from exc
    return ok(recipe_to_dict(recipe))


@router.put("/feature-recipes/{recipe_id}")
async def update_feature_recipe(
    recipe_id: str,
    body: FeatureRecipeUpdateRequest,
    db: AsyncSession = Depends(get_db),
):
    payload = {k: v for k, v in body.model_dump().items() if v is not None}
    try:
        result = await update_recipe(db, recipe_id, payload)
    except RecipeServiceError as exc:
        raise _recipe_error(exc) from exc
    return ok(result, message="Recipe가 수정되었습니다.")


@router.post("/feature-recipes/{recipe_id}/archive")
async def archive_feature_recipe(recipe_id: str, db: AsyncSession = Depends(get_db)):
    try:
        result = await archive_recipe(db, recipe_id)
    except RecipeServiceError as exc:
        raise _recipe_error(exc) from exc
    return ok(result, message="Recipe가 보관되었습니다.")


@router.post("/feature-recipes/{recipe_id}/validate")
async def validate_saved_feature_recipe(recipe_id: str, db: AsyncSession = Depends(get_db)):
    try:
        result = await validate_saved_recipe(db, recipe_id)
    except RecipeServiceError as exc:
        raise _recipe_error(exc) from exc
    return ok(result)


@router.post("/feature-recipes/{recipe_id}/preview")
async def preview_saved_feature_recipe_api(
    recipe_id: str,
    body: FeatureRecipePreviewSavedRequest | None = None,
    db: AsyncSession = Depends(get_db),
):
    sample_size = body.sample_size if body else 100
    try:
        result = await preview_saved_recipe(db, recipe_id, sample_size=sample_size)
    except RecipeServiceError as exc:
        raise _recipe_error(exc) from exc
    return ok(result)


@router.post("/feature-recipes/{recipe_id}/publish")
async def publish_feature_recipe(recipe_id: str, db: AsyncSession = Depends(get_db)):
    try:
        result = await publish_recipe(db, recipe_id)
    except RecipeServiceError as exc:
        raise _recipe_error(exc) from exc
    return ok(result, message="Recipe가 발행되어 Feature Catalog에 등록되었습니다.")


@router.get("/feature-recipes/{recipe_id}/build-history")
async def get_recipe_build_history(
    recipe_id: str,
    limit: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    try:
        result = await list_recipe_build_history(db, recipe_id, limit=limit)
    except RecipeServiceError as exc:
        raise _recipe_error(exc) from exc
    return ok(result)


@router.post("/feature-recipes/{recipe_id}/compare-preview-build")
async def compare_recipe_preview_build(
    recipe_id: str,
    body: FeatureRecipeComparePreviewBuildRequest,
    db: AsyncSession = Depends(get_db),
):
    try:
        result = await compare_preview_with_build(
            db,
            recipe_id,
            dataset_version_id=body.dataset_version_id,
            feature_set_id=body.feature_set_id,
            sample_size=body.sample_size,
        )
    except RecipeServiceError as exc:
        raise _recipe_error(exc) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ok(result)
