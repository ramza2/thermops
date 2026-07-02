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
RECIPE_ENGINE_DIAGNOSTICS_VERSION = "R6-S1"

MAX_DIAGNOSTICS = 30

DIAGNOSTIC_MESSAGES: dict[str, str] = {
    "RECIPE_NOT_PUBLISHED": "PUBLISHED 상태의 Recipe만 Build 대상입니다.",
    "RECIPE_ARCHIVED": "보관(ARCHIVED)된 Recipe는 Build 대상이 아닙니다.",
    "UNSUPPORTED_RECIPE_TYPE": "현재 R6에서는 해당 Recipe Type Build를 지원하지 않습니다.",
    "SOURCE_COLUMN_MISSING": "base frame에 source column이 없습니다.",
    "ENTITY_KEY_MISSING": "entity key 컬럼이 base frame에 없습니다.",
    "TIME_KEY_MISSING": "time key 컬럼이 base frame에 없습니다.",
    "INVALID_PARAM": "Recipe 파라미터가 유효하지 않습니다.",
    "NUMERIC_CONVERSION_FAILED": "숫자 변환에 실패한 값이 있습니다.",
    "DATETIME_CONVERSION_FAILED": "datetime 변환에 실패한 값이 null 처리되었습니다.",
    "INSUFFICIENT_HISTORY": "offset/window에 필요한 이력이 부족하여 null이 발생했습니다.",
    "TIME_GAP_DETECTED": "시간 간격이 기대 granularity와 다릅니다 (row step 기준).",
    "LEAKAGE_RISK": "include_current_row와 target 동일로 누수 위험이 있습니다.",
    "UNKNOWN_BUILD_ERROR": "알 수 없는 Build 오류가 발생했습니다.",
}

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


def _classify_warning_codes(warnings: list[str]) -> list[str]:
    codes: list[str] = []
    for msg in warnings:
        text = str(msg)
        if "이력 부족" in text or "insufficient" in text.lower():
            codes.append("INSUFFICIENT_HISTORY")
        elif "간격" in text or "row step" in text:
            codes.append("TIME_GAP_DETECTED")
        elif "누수" in text or "leakage" in text.lower():
            codes.append("LEAKAGE_RISK")
        elif "datetime" in text.lower() or "변환 실패" in text:
            codes.append("DATETIME_CONVERSION_FAILED")
        elif "숫자" in text or "numeric" in text.lower():
            codes.append("NUMERIC_CONVERSION_FAILED")
    return list(dict.fromkeys(codes))


def _classify_error_codes(errors: list[str], support: dict[str, Any] | None = None) -> list[str]:
    if support and not support.get("supported"):
        reason = str(support.get("reason") or "")
        if reason == "NOT_PUBLISHED":
            return ["RECIPE_NOT_PUBLISHED"]
        if reason == "INACTIVE":
            return ["RECIPE_NOT_PUBLISHED"]
        if reason in ("UNSUPPORTED_TYPE",):
            return ["UNSUPPORTED_RECIPE_TYPE"]
    codes: list[str] = []
    for msg in errors:
        text = str(msg)
        if "source_column" in text or "source column" in text.lower():
            codes.append("SOURCE_COLUMN_MISSING")
        elif "time_key" in text:
            codes.append("TIME_KEY_MISSING")
        elif "entity" in text.lower():
            codes.append("ENTITY_KEY_MISSING")
        elif "offset_steps" in text or "파라미터" in text:
            codes.append("INVALID_PARAM")
        elif "지원하지 않는" in text:
            codes.append("UNSUPPORTED_RECIPE_TYPE")
        else:
            codes.append("UNKNOWN_BUILD_ERROR")
    return list(dict.fromkeys(codes)) or ["UNKNOWN_BUILD_ERROR"]


def _series_stats(series: pd.Series | None) -> dict[str, Any]:
    if series is None or series.empty:
        return {"null_count": 0, "null_ratio": 0.0, "invalid_count": 0, "row_count": 0}
    row_count = len(series)
    null_count = int(series.isna().sum())
    numeric = pd.to_numeric(series, errors="coerce")
    invalid_count = int((numeric.isna() & series.notna()).sum())
    return {
        "null_count": null_count,
        "null_ratio": round(null_count / row_count, 4) if row_count else 0.0,
        "invalid_count": invalid_count,
        "row_count": row_count,
    }


def _diagnostic_entry(
    feature_name: str,
    *,
    severity: str,
    code: str,
    message: str | None = None,
) -> dict[str, Any]:
    return {
        "feature_name": feature_name,
        "severity": severity,
        "code": code,
        "message": message or DIAGNOSTIC_MESSAGES.get(code, code),
    }


def build_template_diagnostics(
    recipes: list[FeatureRecipe],
    template_result: dict[str, Any],
    feature_frame: pd.DataFrame,
) -> dict[str, Any]:
    """R6-S1: Feature별 Build 상태·진단 코드·통계."""
    generated = set(template_result.get("generated_features") or [])
    unsupported = set(template_result.get("unsupported_features") or [])
    failed = set(template_result.get("failed_features") or [])
    per_applied: dict[str, dict[str, Any]] = template_result.get("per_feature_applied") or {}

    status_by_feature: dict[str, dict[str, Any]] = {}
    diagnostics: list[dict[str, Any]] = []
    counts = {"generated": 0, "failed": 0, "unsupported": 0, "warning": 0}

    for recipe in recipes:
        fname = _output_feature_name(recipe)
        support = validate_recipe_build_support(recipe)
        applied = per_applied.get(fname, {})
        warning_codes = list(applied.get("warning_codes") or [])
        error_codes = list(applied.get("error_codes") or [])
        stats = _series_stats(feature_frame[fname] if fname in feature_frame.columns else None)

        if fname in unsupported:
            status = "UNSUPPORTED"
            error_codes = error_codes or _classify_error_codes(applied.get("errors") or [], support)
            message = support.get("message", "Build 미지원")
            counts["unsupported"] += 1
        elif fname in failed:
            status = "FAILED"
            error_codes = error_codes or _classify_error_codes(applied.get("errors") or [], support)
            message = (applied.get("errors") or ["Build 실패"])[0]
            counts["failed"] += 1
        elif fname in generated:
            status = "GENERATED_WITH_WARNING" if warning_codes else "GENERATED"
            message = "정상 생성" if status == "GENERATED" else "생성됨 (경고 있음)"
            counts["generated"] += 1
            if warning_codes:
                counts["warning"] += 1
        else:
            status = "SKIPPED"
            message = "Build 대상에서 제외됨"
            counts["failed"] += 1

        status_by_feature[fname] = {
            "feature_name": fname,
            "recipe_id": recipe.recipe_id,
            "recipe_type": recipe.recipe_type,
            "status": status,
            "build_supported": bool(support.get("supported")),
            "message": message,
            "warning_codes": warning_codes,
            "error_codes": error_codes,
            "source_columns": list(recipe.source_columns or []),
            "entity_keys": _resolve_entity_keys(recipe),
            "time_key": _resolve_time_key(recipe),
            **stats,
        }

        for code in error_codes:
            diagnostics.append(_diagnostic_entry(fname, severity="ERROR", code=code))
        for code in warning_codes:
            diagnostics.append(_diagnostic_entry(fname, severity="WARNING", code=code))

    return {
        "template_build_status_by_feature": status_by_feature,
        "template_build_status_counts": counts,
        "template_build_diagnostics": diagnostics[:MAX_DIAGNOSTICS],
        "recipe_engine_diagnostics_version": RECIPE_ENGINE_DIAGNOSTICS_VERSION,
    }


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


def _attach_error_codes(result: dict[str, Any], support: dict[str, Any] | None = None) -> dict[str, Any]:
    if result.get("errors"):
        result["error_codes"] = _classify_error_codes(result["errors"], support)
    return result


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
        result["error_codes"] = _classify_error_codes(result["errors"], support)
        return result

    source_columns = list(recipe.source_columns or [])
    if not source_columns:
        result["errors"].append("source_columns가 비어 있습니다.")
        return _attach_error_codes(result)

    source_column = str(source_columns[0])
    entity_keys = _resolve_entity_keys(recipe)
    time_key = _resolve_time_key(recipe)
    recipe_type = str(recipe.recipe_type)
    params = dict(recipe.params or {})
    warnings: list[str] = []

    if recipe_type == "RAW_COLUMN":
        if source_column not in df.columns:
            result["errors"].append(f"base frame에 source_column 없음: {source_column}")
            return _attach_error_codes(result)
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
            return _attach_error_codes(result)
        if time_key not in df.columns:
            result["errors"].append(f"base frame에 time_key 없음: {time_key}")
            return _attach_error_codes(result)

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
                return _attach_error_codes(result)
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
            return _attach_error_codes(result)

        work = work.sort_values("_build_ord")
        series = work[output_name].reset_index(drop=True)
        series.index = df.index
    else:
        result["errors"].append(f"지원하지 않는 recipe_type: {recipe_type}")
        return _attach_error_codes(result)

    result["generated"] = True
    result["series"] = series
    result["warnings"] = warnings
    result["warning_codes"] = _classify_warning_codes(warnings)
    result["error_codes"] = _classify_error_codes(result.get("errors") or [])
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
    per_feature_applied: dict[str, dict[str, Any]] = {}
    time_gap_warnings: list[str] = []

    for recipe in recipes:
        fname = _output_feature_name(recipe)
        template_features.append(fname)
        support = validate_recipe_build_support(recipe)
        if not support["supported"]:
            applied_stub: dict[str, Any] = {
                "errors": [support["message"]],
                "warnings": [],
                "error_codes": _classify_error_codes([support["message"]], support),
                "warning_codes": [],
            }
            per_feature_applied[fname] = applied_stub
            if support.get("reason") == "UNSUPPORTED_TYPE":
                unsupported.append(fname)
            else:
                failed.append(fname)
            warnings.append(f"{fname}: {support['message']}")
            continue

        applied = apply_template_recipe(work, recipe)
        per_feature_applied[fname] = applied
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
        "per_feature_applied": per_feature_applied,
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
