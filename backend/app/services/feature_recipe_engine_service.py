"""Recipe Engine — PUBLISHED TEMPLATE Recipe Feature Build (Phase R6)."""

from __future__ import annotations

from typing import Any

import pandas as pd

from app.models.entities import FeatureRecipe
from app.services.feature_recipe_preview_service import (
    _compute_date_part_value,
    apply_lag_preview,
    apply_rolling_preview,
    compute_time_gap_warnings,
)
from app.services.feature_recipe_template_service import PREVIEW_SUPPORTED_RECIPE_TYPES

RECIPE_ENGINE_VERSION = "R6"

BUILD_SUPPORTED_RECIPE_TYPES = frozenset(PREVIEW_SUPPORTED_RECIPE_TYPES)

BUILD_UNSUPPORTED_RECIPE_TYPES = frozenset({
    "DIFF",
    "RATIO",
    "BINNING",
    "FILL_NULL",
    "CATEGORY_ENCODING",
})

MAX_TIME_GAP_WARNINGS = 5

DEFAULT_ENTITY_KEYS = ("site_id",)
DEFAULT_TIME_KEY = "measured_at"


def is_recipe_build_supported(recipe_type: str) -> bool:
    return recipe_type in BUILD_SUPPORTED_RECIPE_TYPES


def validate_recipe_build_support(recipe: FeatureRecipe) -> dict[str, Any]:
    """Recipe가 R6 Build 대상인지 판별."""
    recipe_type = str(recipe.recipe_type or "")
    if recipe.status != "PUBLISHED":
        return {
            "supported": False,
            "reason": "NOT_PUBLISHED",
            "message": f"Recipe 상태가 PUBLISHED가 아닙니다: {recipe.status}",
        }
    if recipe.active_yn != "Y":
        return {
            "supported": False,
            "reason": "INACTIVE",
            "message": "비활성 Recipe는 Build 대상이 아닙니다.",
        }
    if recipe_type in BUILD_UNSUPPORTED_RECIPE_TYPES:
        return {
            "supported": False,
            "reason": "UNSUPPORTED_TYPE",
            "message": f"R6에서는 {recipe_type} Build 계산을 지원하지 않습니다.",
        }
    if not is_recipe_build_supported(recipe_type):
        return {
            "supported": False,
            "reason": "UNSUPPORTED_TYPE",
            "message": f"R6에서는 {recipe_type} Build 계산을 지원하지 않습니다.",
        }
    return {"supported": True, "reason": None, "message": "Recipe Engine Build 지원"}


def recipe_definition_from_entity(recipe: FeatureRecipe) -> dict[str, Any]:
    source_columns = list(recipe.source_columns or [])
    params = dict(recipe.params or {})
    definition: dict[str, Any] = {
        "recipe_type": recipe.recipe_type,
        "source_columns": source_columns,
        "params": params,
        "feature_name": recipe.feature_name,
    }
    if recipe.entity_keys:
        definition["entity_keys"] = list(recipe.entity_keys)
    if recipe.time_key:
        definition["time_key"] = recipe.time_key
    if recipe.target_column:
        definition["target_column"] = recipe.target_column
    if recipe.output_feature_names:
        definition["output_feature_name"] = recipe.output_feature_names[0]
    return definition


def _resolve_entity_keys(recipe: FeatureRecipe) -> list[str]:
    if recipe.entity_keys:
        return [str(k) for k in recipe.entity_keys]
    return list(DEFAULT_ENTITY_KEYS)


def _resolve_time_key(recipe: FeatureRecipe) -> str:
    return str(recipe.time_key or DEFAULT_TIME_KEY)


def _output_feature_name(recipe: FeatureRecipe) -> str:
    if recipe.feature_name:
        return str(recipe.feature_name)
    outputs = list(recipe.output_feature_names or [])
    if outputs:
        return str(outputs[0])
    raise ValueError(f"Recipe {recipe.recipe_id}에 output feature_name이 없습니다.")


def build_template_lineage(recipe: FeatureRecipe, output_feature_name: str) -> dict[str, Any]:
    source_columns = list(recipe.source_columns or [])
    return {
        "feature_name": output_feature_name,
        "calc_method": "TEMPLATE",
        "source_columns": source_columns,
        "recipe_id": recipe.recipe_id,
        "recipe_type": recipe.recipe_type,
        "params": dict(recipe.params or {}),
        "entity_keys": _resolve_entity_keys(recipe),
        "time_key": _resolve_time_key(recipe),
        "source_recipe_status": recipe.status,
        "recipe_engine_version": RECIPE_ENGINE_VERSION,
    }


def _apply_date_part_build(
    df: pd.DataFrame,
    *,
    source_column: str,
    time_key: str,
    parts: list[str],
    output_name: str,
) -> tuple[pd.Series, list[str]]:
    warnings: list[str] = []
    col = source_column if source_column in df.columns else time_key
    if col not in df.columns:
        return pd.Series([None] * len(df), index=df.index), [f"datetime 컬럼 없음: {source_column}/{time_key}"]

    dts = pd.to_datetime(df[col], errors="coerce")
    part = parts[0] if parts else "hour"
    invalid_count = int(dts.isna().sum())

    if part == "hour":
        result = dts.dt.hour
    elif part == "day_of_week":
        result = dts.dt.weekday
    elif part == "month":
        result = dts.dt.month
    elif part == "day":
        result = dts.dt.day
    elif part == "is_weekend":
        result = dts.dt.weekday.apply(lambda w: 1 if w >= 5 else 0)
    elif part == "week_of_year":
        result = dts.dt.isocalendar().week.astype("Int64")
    else:
        values = []
        for raw in dts:
            if pd.isna(raw):
                values.append(None)
            else:
                dt = raw.to_pydatetime() if hasattr(raw, "to_pydatetime") else raw
                val, _ = _compute_date_part_value(dt, part)
                values.append(val)
        result = pd.Series(values, index=df.index)

    if invalid_count > 0:
        warnings.append(f"{output_name}: datetime 변환 실패 {invalid_count}건 (null 처리)")
    return result, warnings


def apply_template_recipe(
    df: pd.DataFrame,
    recipe: FeatureRecipe,
) -> dict[str, Any]:
    """단일 Recipe를 base DataFrame에 적용."""
    support = validate_recipe_build_support(recipe)
    output_name = _output_feature_name(recipe)
    result: dict[str, Any] = {
        "feature_name": output_name,
        "recipe_id": recipe.recipe_id,
        "recipe_type": recipe.recipe_type,
        "generated": False,
        "series": None,
        "warnings": [],
        "errors": [],
        "lineage": None,
    }

    if not support["supported"]:
        result["errors"].append(support["message"])
        return result

    source_columns = list(recipe.source_columns or [])
    if not source_columns:
        result["errors"].append("source_columns가 비어 있습니다.")
        return result

    source_column = str(source_columns[0])
    entity_keys = _resolve_entity_keys(recipe)
    time_key = _resolve_time_key(recipe)
    recipe_type = str(recipe.recipe_type)
    params = dict(recipe.params or {})
    warnings: list[str] = []

    if recipe_type == "RAW_COLUMN":
        if source_column not in df.columns:
            result["errors"].append(f"base frame에 source_column 없음: {source_column}")
            return result
        series = df[source_column].copy()
    elif recipe_type == "DATE_PART":
        parts = params.get("parts") or ["hour"]
        if isinstance(parts, str):
            parts = [parts]
        series, part_warnings = _apply_date_part_build(
            df,
            source_column=source_column,
            time_key=time_key,
            parts=parts,
            output_name=output_name,
        )
        warnings.extend(part_warnings)
    elif recipe_type in ("LAG", "ROLLING_MEAN", "ROLLING_SUM"):
        if source_column not in df.columns:
            result["errors"].append(f"base frame에 source_column 없음: {source_column}")
            return result
        if time_key not in df.columns:
            result["errors"].append(f"base frame에 time_key 없음: {time_key}")
            return result

        work = df.copy()
        work["_build_ord"] = range(len(work))
        sort_cols = [c for c in (*entity_keys, time_key) if c in work.columns]
        work[time_key] = pd.to_datetime(work[time_key], errors="coerce")
        work[source_column] = pd.to_numeric(work[source_column], errors="coerce")
        work = work.sort_values(sort_cols)

        granularity = str(params.get("granularity", "1h"))
        gap_warnings, _ = compute_time_gap_warnings(
            work,
            entity_keys=entity_keys,
            time_key=time_key,
            expected_granularity=granularity,
        )
        warnings.extend(gap_warnings[:MAX_TIME_GAP_WARNINGS])

        if recipe_type == "LAG":
            offset_steps = int(params.get("offset_steps", 24))
            if offset_steps < 1:
                result["errors"].append("offset_steps는 1 이상이어야 합니다.")
                return result
            work, insufficient = apply_lag_preview(
                work,
                entity_keys=entity_keys,
                time_key=time_key,
                source_column=source_column,
                output_name=output_name,
                offset_steps=offset_steps,
            )
            if insufficient > 0:
                warnings.append(f"{output_name}: 이력 부족 null {insufficient}건")
        else:
            window_steps = int(params.get("window_steps", 24))
            min_periods = int(params.get("min_periods", window_steps))
            include_current_row = bool(params.get("include_current_row", False))
            agg = "mean" if recipe_type == "ROLLING_MEAN" else "sum"
            work, insufficient = apply_rolling_preview(
                work,
                entity_keys=entity_keys,
                source_column=source_column,
                output_name=output_name,
                window_steps=window_steps,
                min_periods=min_periods,
                include_current_row=include_current_row,
                agg=agg,
            )
            if insufficient > 0:
                warnings.append(f"{output_name}: 이력 부족 null {insufficient}건")
            target_column = recipe.target_column
            if include_current_row and target_column and source_column == target_column:
                warnings.append(
                    f"{output_name}: include_current_row=true이고 source가 target과 동일 — 누수 위험"
                )

        if output_name not in work.columns:
            result["errors"].append(f"{recipe_type} 계산 결과 컬럼 생성 실패")
            return result

        work = work.sort_values("_build_ord")
        series = work[output_name].reset_index(drop=True)
        series.index = df.index
    else:
        result["errors"].append(f"지원하지 않는 recipe_type: {recipe_type}")
        return result

    result["generated"] = True
    result["series"] = series
    result["warnings"] = warnings
    result["lineage"] = build_template_lineage(recipe, output_name)
    return result


def build_template_features(
    base_df: pd.DataFrame,
    recipes: list[FeatureRecipe],
) -> dict[str, Any]:
    """Published Recipe 목록을 base DataFrame에 적용."""
    if base_df.empty or not recipes:
        return {
            "feature_frame": base_df,
            "generated_features": [],
            "unsupported_features": [],
            "failed_features": [],
            "warnings": [],
            "lineage_items": [],
            "template_recipe_features": [],
            "time_gap_warnings": [],
        }

    work = base_df.copy()
    generated: list[str] = []
    unsupported: list[str] = []
    failed: list[str] = []
    warnings: list[str] = []
    lineage_items: list[dict[str, Any]] = []
    template_features: list[str] = []
    time_gap_warnings: list[str] = []

    for recipe in recipes:
        fname = _output_feature_name(recipe)
        template_features.append(fname)
        support = validate_recipe_build_support(recipe)
        if not support["supported"]:
            if support.get("reason") == "UNSUPPORTED_TYPE":
                unsupported.append(fname)
            else:
                failed.append(fname)
            warnings.append(f"{fname}: {support['message']}")
            continue

        applied = apply_template_recipe(work, recipe)
        warnings.extend(applied.get("warnings") or [])
        for w in applied.get("warnings") or []:
            if "간격" in w or "row step" in w:
                time_gap_warnings.append(w)

        if applied.get("errors"):
            failed.append(fname)
            warnings.extend(applied["errors"])
            continue

        series = applied.get("series")
        if series is None or not applied.get("generated"):
            failed.append(fname)
            continue

        work[fname] = series
        generated.append(fname)
        if applied.get("lineage"):
            lineage_items.append(applied["lineage"])

    return {
        "feature_frame": work,
        "generated_features": generated,
        "unsupported_features": unsupported,
        "failed_features": failed,
        "warnings": warnings,
        "lineage_items": lineage_items,
        "template_recipe_features": template_features,
        "time_gap_warnings": time_gap_warnings[:MAX_TIME_GAP_WARNINGS],
    }


def summarize_template_build_result(
    template_result: dict[str, Any],
    *,
    code_feature_count: int,
) -> dict[str, Any]:
    """result_summary용 TEMPLATE Build 요약."""
    generated = template_result.get("generated_features") or []
    unsupported = template_result.get("unsupported_features") or []
    failed = template_result.get("failed_features") or []
    recipe_features = template_result.get("template_recipe_features") or []
    return {
        "code_feature_count": code_feature_count,
        "template_feature_count": len(recipe_features),
        "template_generated_feature_count": len(generated),
        "template_missing_feature_count": len(unsupported) + len(failed),
        "template_recipe_features": recipe_features,
        "template_build_unsupported_features": unsupported,
        "template_build_failed_features": failed,
        "template_build_warnings": (template_result.get("warnings") or [])[:20],
        "template_time_gap_warnings": template_result.get("time_gap_warnings") or [],
        "recipe_engine_version": RECIPE_ENGINE_VERSION,
    }


def split_feature_names_by_recipe(
    feature_names: list[str],
    published_recipes: dict[str, FeatureRecipe],
) -> tuple[list[str], list[FeatureRecipe]]:
    """Feature Set features를 CODE vs TEMPLATE Recipe로 분리."""
    code_features: list[str] = []
    template_recipes: list[FeatureRecipe] = []
    seen_recipe_ids: set[str] = set()

    for name in feature_names:
        recipe = published_recipes.get(name)
        if recipe and recipe.recipe_id not in seen_recipe_ids:
            template_recipes.append(recipe)
            seen_recipe_ids.add(recipe.recipe_id)
        elif not recipe:
            code_features.append(name)

    return code_features, template_recipes
