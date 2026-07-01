"""Feature Recipe 저장·발행·Feature Set 연동 (Phase R5)."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.time import utc_now
from app.models.entities import DataMapping, Feature, FeatureRecipe, FeatureRecipeVersion, FeatureSet
from app.services.feature_column_role_service import get_mapping_or_raise, list_column_roles
from app.services.feature_recipe_preview_service import preview_feature_recipe
from app.services.feature_recipe_template_service import (
    PREVIEW_SUPPORTED_RECIPE_TYPES,
    validate_recipe_definition,
)
from app.services.feature_registration_service import is_tpl_feature_set

RECIPE_STATUSES = frozenset({"DRAFT", "VALIDATED", "PUBLISHED", "ARCHIVED"})
EDITABLE_STATUSES = frozenset({"DRAFT", "VALIDATED"})
BUILDER_SUPPORTED_TYPES = frozenset({
    "RAW_COLUMN",
    "DATE_PART",
    "LAG",
    "ROLLING_MEAN",
    "ROLLING_SUM",
})

R5_BUILD_WARNING = (
    "R5에서는 Recipe Feature Build 계산이 아직 연결되지 않았습니다. "
    "실제 Feature Dataset 계산은 R6 Recipe Engine에서 제공됩니다."
)


class RecipeServiceError(Exception):
    def __init__(self, code: str, message: str, *, status_code: int = 400) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


def _new_recipe_id() -> str:
    return f"RCP-{uuid4().hex[:10].upper()}"


def _new_version_id() -> str:
    return f"RCV-{uuid4().hex[:10].upper()}"


def build_template_calc_summary(recipe: dict[str, Any]) -> str:
    recipe_type = str(recipe.get("recipe_type") or "")
    source_columns = list(recipe.get("source_columns") or [])
    src = source_columns[0] if source_columns else "?"
    params = recipe.get("params") or {}
    if recipe_type == "RAW_COLUMN":
        return f"TEMPLATE Recipe: RAW_COLUMN(source={src})"
    if recipe_type == "DATE_PART":
        parts = params.get("parts") or ["hour"]
        return f"TEMPLATE Recipe: DATE_PART(time_key={src}, parts={parts})"
    if recipe_type == "LAG":
        return (
            f"TEMPLATE Recipe: LAG(source={src}, offset={params.get('offset_steps')}, "
            f"granularity={params.get('granularity', '1h')})"
        )
    if recipe_type in ("ROLLING_MEAN", "ROLLING_SUM"):
        agg = "mean" if recipe_type == "ROLLING_MEAN" else "sum"
        return (
            f"TEMPLATE Recipe: ROLLING_{agg}(source={src}, window={params.get('window_steps')}, "
            f"granularity={params.get('granularity', '1h')}, "
            f"include_current_row={params.get('include_current_row', False)})"
        )
    return f"TEMPLATE Recipe: {recipe_type}(source={src})"


def build_recipe_snapshot(recipe: FeatureRecipe) -> dict[str, Any]:
    return recipe_to_dict(recipe)


def recipe_to_dict(recipe: FeatureRecipe) -> dict[str, Any]:
    return {
        "recipe_id": recipe.recipe_id,
        "feature_name": recipe.feature_name,
        "display_name": recipe.display_name,
        "description": recipe.description,
        "domain": recipe.domain,
        "task_type": recipe.task_type,
        "calc_mode": recipe.calc_mode,
        "recipe_type": recipe.recipe_type,
        "mapping_id": recipe.mapping_id,
        "data_source_id": recipe.data_source_id,
        "source_table": recipe.source_table,
        "target_table": recipe.target_table,
        "source_columns": list(recipe.source_columns or []),
        "entity_keys": list(recipe.entity_keys or []) if recipe.entity_keys else [],
        "time_key": recipe.time_key,
        "target_column": recipe.target_column,
        "params": dict(recipe.params or {}),
        "output_feature_names": list(recipe.output_feature_names or []),
        "output_data_type": recipe.output_data_type,
        "unit": recipe.unit,
        "null_handling": recipe.null_handling,
        "leakage_policy": recipe.leakage_policy,
        "validation_summary": recipe.validation_summary,
        "preview_summary": recipe.preview_summary,
        "lineage_preview": recipe.lineage_preview,
        "quality_preview": recipe.quality_preview,
        "status": recipe.status,
        "version": recipe.version,
        "owner": recipe.owner,
        "active_yn": recipe.active_yn,
        "published_at": recipe.published_at.isoformat() if recipe.published_at else None,
        "created_at": recipe.created_at.isoformat() if recipe.created_at else None,
        "updated_at": recipe.updated_at.isoformat() if recipe.updated_at else None,
        "build_supported": recipe.status == "PUBLISHED" and False,
    }


def recipe_definition_from_row(recipe: FeatureRecipe) -> dict[str, Any]:
    definition: dict[str, Any] = {
        "recipe_type": recipe.recipe_type,
        "source_columns": list(recipe.source_columns or []),
        "params": dict(recipe.params or {}),
    }
    if recipe.mapping_id:
        definition["mapping_id"] = recipe.mapping_id
    if recipe.entity_keys:
        definition["entity_keys"] = list(recipe.entity_keys)
    if recipe.time_key:
        definition["time_key"] = recipe.time_key
    if recipe.target_column:
        definition["target_column"] = recipe.target_column
    if recipe.output_feature_names:
        definition["output_feature_name"] = recipe.output_feature_names[0]
    return definition


async def _load_mapping_context(
    db: AsyncSession,
    mapping_id: str | None,
) -> tuple[list[dict], list[dict], DataMapping | None]:
    if not mapping_id:
        return [], [], None
    mapping = await get_mapping_or_raise(db, mapping_id)
    role_data = await list_column_roles(db, mapping_id=mapping_id, include_inferred=False)
    return list(mapping.columns or []), role_data.get("items") or [], mapping


def _default_display_name(recipe_type: str, output_name: str | None) -> str:
    if output_name:
        return output_name
    return f"{recipe_type} Recipe"


def _infer_output_data_type(recipe_type: str) -> str:
    if recipe_type == "DATE_PART":
        return "CATEGORICAL"
    return "NUMERIC"


async def create_recipe(db: AsyncSession, payload: dict[str, Any]) -> dict[str, Any]:
    recipe_type = str(payload.get("recipe_type") or "").strip()
    if recipe_type not in BUILDER_SUPPORTED_TYPES:
        raise RecipeServiceError("UNSUPPORTED_RECIPE_TYPE", f"R5에서 지원하지 않는 recipe_type: {recipe_type}")

    mapping_id = payload.get("mapping_id")
    mapping_columns, role_items, mapping = await _load_mapping_context(db, mapping_id)

    definition = {
        k: v
        for k, v in payload.items()
        if k not in ("display_name", "description", "domain", "task_type", "owner", "output_data_type", "unit")
    }
    validate_result = await validate_recipe_definition(
        db,
        definition,
        mapping_columns=mapping_columns,
        role_items=role_items,
    )
    output_names = list(
        validate_result.get("output_feature_names")
        or validate_result.get("generated_feature_names")
        or []
    )
    output_name = payload.get("output_feature_name") or (output_names[0] if output_names else None)
    if output_name and output_names:
        output_names = [str(output_name)]

    now = utc_now()
    recipe = FeatureRecipe(
        recipe_id=_new_recipe_id(),
        feature_name=None,
        display_name=str(payload.get("display_name") or _default_display_name(recipe_type, output_name)),
        description=payload.get("description"),
        domain=payload.get("domain"),
        task_type=payload.get("task_type"),
        calc_mode="TEMPLATE",
        recipe_type=recipe_type,
        mapping_id=mapping_id,
        data_source_id=mapping.source_id if mapping else payload.get("data_source_id"),
        source_table=mapping.target_table if mapping else payload.get("source_table"),
        target_table=mapping.target_table if mapping else payload.get("target_table"),
        source_columns=list(payload.get("source_columns") or []),
        entity_keys=list(payload.get("entity_keys") or []) or None,
        time_key=payload.get("time_key"),
        target_column=payload.get("target_column"),
        params=dict(payload.get("params") or {}),
        output_feature_names=output_names or None,
        output_data_type=payload.get("output_data_type") or _infer_output_data_type(recipe_type),
        unit=payload.get("unit"),
        null_handling=payload.get("null_handling"),
        leakage_policy=payload.get("leakage_policy"),
        validation_summary=validate_result if validate_result.get("valid") else None,
        preview_summary=None,
        lineage_preview=validate_result.get("lineage_preview"),
        quality_preview=None,
        status="VALIDATED" if validate_result.get("valid") else "DRAFT",
        version=1,
        owner=payload.get("owner"),
        active_yn="Y",
        published_at=None,
        created_at=now,
        updated_at=now,
    )
    db.add(recipe)
    await db.flush()
    return {
        **recipe_to_dict(recipe),
        "validate_result": validate_result,
    }


async def list_recipes(
    db: AsyncSession,
    *,
    status: str | None = None,
    recipe_type: str | None = None,
    mapping_id: str | None = None,
    feature_name: str | None = None,
    include_archived: bool = False,
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    q = select(FeatureRecipe).where(FeatureRecipe.active_yn == "Y")
    if not include_archived:
        q = q.where(FeatureRecipe.status != "ARCHIVED")
    if status:
        q = q.where(FeatureRecipe.status == status)
    if recipe_type:
        q = q.where(FeatureRecipe.recipe_type == recipe_type)
    if mapping_id:
        q = q.where(FeatureRecipe.mapping_id == mapping_id)
    if feature_name:
        q = q.where(FeatureRecipe.feature_name == feature_name)
    q = q.order_by(FeatureRecipe.updated_at.desc())
    rows = (await db.execute(q)).scalars().all()
    total = len(rows)
    page = rows[offset: offset + limit]
    return {
        "items": [recipe_to_dict(r) for r in page],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


async def get_recipe_or_raise(db: AsyncSession, recipe_id: str) -> FeatureRecipe:
    recipe = (
        await db.execute(
            select(FeatureRecipe).where(
                FeatureRecipe.recipe_id == recipe_id,
                FeatureRecipe.active_yn == "Y",
            )
        )
    ).scalar_one_or_none()
    if not recipe:
        raise RecipeServiceError("RECIPE_NOT_FOUND", f"Recipe를 찾을 수 없습니다: {recipe_id}", status_code=404)
    return recipe


async def update_recipe(db: AsyncSession, recipe_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    recipe = await get_recipe_or_raise(db, recipe_id)
    if recipe.status not in EDITABLE_STATUSES:
        raise RecipeServiceError(
            "RECIPE_NOT_EDITABLE",
            f"상태가 {recipe.status}인 Recipe는 수정할 수 없습니다.",
        )

    for field in (
        "display_name", "description", "domain", "task_type", "owner",
        "output_data_type", "unit", "null_handling", "leakage_policy",
    ):
        if field in payload:
            setattr(recipe, field, payload[field])

    for field in (
        "mapping_id", "source_columns", "entity_keys", "time_key",
        "target_column", "params", "recipe_type",
    ):
        if field in payload and payload[field] is not None:
            setattr(recipe, field, payload[field])

    if payload.get("output_feature_name"):
        recipe.output_feature_names = [str(payload["output_feature_name"])]

    mapping_columns, role_items, mapping = await _load_mapping_context(db, recipe.mapping_id)
    if mapping:
        recipe.data_source_id = mapping.source_id
        recipe.target_table = mapping.target_table

    definition = recipe_definition_from_row(recipe)
    validate_result = await validate_recipe_definition(
        db,
        definition,
        mapping_columns=mapping_columns,
        role_items=role_items,
    )
    output_names = list(
        validate_result.get("output_feature_names")
        or validate_result.get("generated_feature_names")
        or []
    )
    if output_names:
        recipe.output_feature_names = output_names

    recipe.validation_summary = validate_result
    recipe.lineage_preview = validate_result.get("lineage_preview")
    recipe.status = "VALIDATED" if validate_result.get("valid") else "DRAFT"
    recipe.updated_at = utc_now()
    await db.flush()
    return {**recipe_to_dict(recipe), "validate_result": validate_result}


async def archive_recipe(db: AsyncSession, recipe_id: str) -> dict[str, Any]:
    recipe = await get_recipe_or_raise(db, recipe_id)
    recipe.status = "ARCHIVED"
    recipe.active_yn = "N"
    recipe.updated_at = utc_now()
    return recipe_to_dict(recipe)


async def validate_saved_recipe(db: AsyncSession, recipe_id: str) -> dict[str, Any]:
    recipe = await get_recipe_or_raise(db, recipe_id)
    mapping_columns, role_items, _ = await _load_mapping_context(db, recipe.mapping_id)
    definition = recipe_definition_from_row(recipe)
    result = await validate_recipe_definition(
        db,
        definition,
        mapping_columns=mapping_columns,
        role_items=role_items,
    )
    recipe.validation_summary = result
    recipe.lineage_preview = result.get("lineage_preview")
    if recipe.status in EDITABLE_STATUSES:
        recipe.status = "VALIDATED" if result.get("valid") else "DRAFT"
    recipe.updated_at = utc_now()
    return {"recipe": recipe_to_dict(recipe), "validation": result}


def _preview_summary_from_result(result: dict[str, Any]) -> dict[str, Any]:
    stats = result.get("stats") or {}
    features = stats.get("features") or {}
    feat_stats = next(iter(features.values()), {})
    return {
        "preview_id": result.get("preview_id"),
        "supported": result.get("supported"),
        "valid": result.get("valid"),
        "row_count": stats.get("row_count"),
        "sample_size": stats.get("sample_size"),
        "output_feature_names": result.get("output_feature_names") or result.get("generated_feature_names"),
        "null_ratio": feat_stats.get("null_ratio"),
        "insufficient_history_count": feat_stats.get("insufficient_history_count"),
        "time_gap_warning_count": stats.get("time_gap_warning_count"),
        "quality_preview": result.get("quality_preview"),
        "warning_count": len(result.get("warnings") or [])
            + len(result.get("time_gap_warnings") or [])
            + len(result.get("leakage_warnings") or []),
    }


async def preview_saved_recipe(
    db: AsyncSession,
    recipe_id: str,
    *,
    sample_size: int = 100,
) -> dict[str, Any]:
    recipe = await get_recipe_or_raise(db, recipe_id)
    if recipe.recipe_type not in PREVIEW_SUPPORTED_RECIPE_TYPES:
        raise RecipeServiceError("PREVIEW_NOT_SUPPORTED", "이 Recipe 타입은 Preview를 지원하지 않습니다.")

    request = recipe_definition_from_row(recipe)
    request["sample_size"] = sample_size
    result = await preview_feature_recipe(db, request)
    summary = _preview_summary_from_result(result)
    recipe.preview_summary = summary
    recipe.quality_preview = result.get("quality_preview")
    recipe.updated_at = utc_now()
    return {"recipe": recipe_to_dict(recipe), "preview": result, "preview_summary": summary}


async def ensure_publishable(db: AsyncSession, recipe: FeatureRecipe) -> dict[str, Any]:
    if recipe.status == "PUBLISHED":
        raise RecipeServiceError("ALREADY_PUBLISHED", "이미 발행된 Recipe입니다.")
    if recipe.status == "ARCHIVED":
        raise RecipeServiceError("RECIPE_ARCHIVED", "보관된 Recipe는 발행할 수 없습니다.")

    mapping_columns, role_items, _ = await _load_mapping_context(db, recipe.mapping_id)
    definition = recipe_definition_from_row(recipe)
    result = await validate_recipe_definition(
        db,
        definition,
        mapping_columns=mapping_columns,
        role_items=role_items,
    )
    if not result.get("valid"):
        raise RecipeServiceError(
            "VALIDATION_FAILED",
            "Publish 전 validate가 통과해야 합니다.",
        )

    output_names = list(
        result.get("output_feature_names")
        or result.get("generated_feature_names")
        or recipe.output_feature_names
        or []
    )
    if len(output_names) != 1:
        raise RecipeServiceError(
            "MULTIPLE_OUTPUT_NOT_SUPPORTED",
            "R5에서는 Recipe 1개당 Feature 1개만 발행할 수 있습니다.",
        )

    reusable = result.get("reusable_existing_features") or []
    if reusable:
        names = ", ".join(r.get("feature_name", "") for r in reusable)
        raise RecipeServiceError(
            "REUSE_EXISTING_FEATURE",
            f"기존 Feature를 재사용할 수 있습니다: {names}. Publish 대신 Feature Set에 기존 Feature를 추가하세요.",
        )

    feature_name = output_names[0]
    existing_feature = (
        await db.execute(select(Feature).where(Feature.feature_name == feature_name))
    ).scalar_one_or_none()
    if existing_feature:
        raise RecipeServiceError(
            "DUPLICATE_FEATURE_NAME",
            f"Feature명 '{feature_name}'이(가) 이미 카탈로그에 있습니다.",
        )

    return {**result, "feature_name": feature_name}


async def publish_recipe(db: AsyncSession, recipe_id: str) -> dict[str, Any]:
    recipe = await get_recipe_or_raise(db, recipe_id)
    publish_check = await ensure_publishable(db, recipe)
    feature_name = publish_check["feature_name"]
    definition = recipe_definition_from_row(recipe)

    calc_expression = build_template_calc_summary(definition)
    feature_id = f"FEAT-{uuid4().hex[:6].upper()}"
    now = utc_now()
    feature = Feature(
        feature_id=feature_id,
        feature_name=feature_name,
        feature_group=recipe.recipe_type,
        feature_type="TEMPLATE",
        calc_expression=calc_expression[:500],
        status="ACTIVE",
        description=recipe.description or recipe.display_name,
        created_at=now,
    )
    db.add(feature)

    recipe.feature_name = feature_name
    recipe.output_feature_names = [feature_name]
    recipe.status = "PUBLISHED"
    recipe.published_at = now
    recipe.validation_summary = publish_check
    recipe.lineage_preview = publish_check.get("lineage_preview")
    recipe.version = int(recipe.version or 1) + 1
    recipe.updated_at = now

    snapshot = build_recipe_snapshot(recipe)
    version = FeatureRecipeVersion(
        version_id=_new_version_id(),
        recipe_id=recipe.recipe_id,
        version_no=recipe.version,
        recipe_snapshot=snapshot,
        change_reason="PUBLISH",
        created_at=now,
    )
    db.add(version)
    await db.flush()

    warnings: list[str] = []
    if not recipe.preview_summary:
        warnings.append("Preview를 실행하지 않고 발행했습니다. Preview 실행을 권장합니다.")
    warnings.append(R5_BUILD_WARNING)

    return {
        "recipe": recipe_to_dict(recipe),
        "feature": {
            "feature_id": feature_id,
            "feature_name": feature_name,
            "feature_type": "TEMPLATE",
            "calc_expression": calc_expression,
        },
        "version_id": version.version_id,
        "warnings": warnings,
    }


async def add_recipe_feature_to_feature_set(
    db: AsyncSession,
    feature_set_id: str,
    *,
    recipe_id: str,
    feature_name: str | None = None,
) -> dict[str, Any]:
    if is_tpl_feature_set(feature_set_id):
        raise RecipeServiceError(
            "TPL_FEATURE_SET_BLOCKED",
            "공식 TPL Feature Set에는 Recipe Feature를 추가할 수 없습니다.",
        )

    recipe = await get_recipe_or_raise(db, recipe_id)
    if recipe.status != "PUBLISHED":
        raise RecipeServiceError(
            "RECIPE_NOT_PUBLISHED",
            "PUBLISHED 상태의 Recipe만 Feature Set에 추가할 수 있습니다.",
        )

    target_name = feature_name or recipe.feature_name
    if not target_name:
        raise RecipeServiceError("MISSING_FEATURE_NAME", "feature_name이 필요합니다.")
    if recipe.feature_name and target_name != recipe.feature_name:
        raise RecipeServiceError(
            "FEATURE_NAME_MISMATCH",
            f"Recipe의 feature_name({recipe.feature_name})과 일치해야 합니다.",
        )

    fs = (
        await db.execute(select(FeatureSet).where(FeatureSet.feature_set_id == feature_set_id))
    ).scalar_one_or_none()
    if not fs:
        raise RecipeServiceError("FEATURE_SET_NOT_FOUND", "Feature Set을 찾을 수 없습니다.", status_code=404)

    features = list(fs.features or [])
    if target_name in features:
        return {
            "feature_set_id": feature_set_id,
            "feature_name": target_name,
            "recipe_id": recipe_id,
            "added": False,
            "features": features,
            "warnings": [R5_BUILD_WARNING],
            "message": "이미 Feature Set에 포함되어 있습니다.",
        }

    features.append(target_name)
    fs.features = features
    return {
        "feature_set_id": feature_set_id,
        "feature_name": target_name,
        "recipe_id": recipe_id,
        "added": True,
        "features": features,
        "warnings": [R5_BUILD_WARNING],
        "message": "Recipe Feature가 Feature Set에 추가되었습니다.",
    }


async def load_published_recipe_map(db: AsyncSession) -> dict[str, FeatureRecipe]:
    rows = (
        await db.execute(
            select(FeatureRecipe).where(
                FeatureRecipe.status == "PUBLISHED",
                FeatureRecipe.active_yn == "Y",
                FeatureRecipe.feature_name.isnot(None),
            )
        )
    ).scalars().all()
    return {r.feature_name: r for r in rows if r.feature_name}


async def get_published_recipe_by_feature_name(
    db: AsyncSession,
    feature_name: str,
) -> FeatureRecipe | None:
    return (
        await db.execute(
            select(FeatureRecipe).where(
                FeatureRecipe.feature_name == feature_name,
                FeatureRecipe.status == "PUBLISHED",
                FeatureRecipe.active_yn == "Y",
            )
        )
    ).scalar_one_or_none()


def recipe_registration_metadata(recipe: FeatureRecipe) -> dict[str, Any]:
    return {
        "template_recipe_registered": True,
        "recipe_id": recipe.recipe_id,
        "recipe_type": recipe.recipe_type,
        "recipe_status": recipe.status,
        "build_supported": False,
        "registration_status": "TEMPLATE_PUBLISHED",
    }
