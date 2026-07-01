"""Feature Recipe Preview (RAW_COLUMN, DATE_PART only — 저장/실행 없음)."""

from __future__ import annotations

import asyncio
import math
from datetime import datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entities import DataMapping, DataSource, FeatureDataset, HeatDemandActual, WeatherObservation
from app.services.feature_column_role_service import get_mapping_or_raise, list_column_roles
from app.services.feature_recipe_template_service import (
    PREVIEW_SUPPORTED_RECIPE_TYPES,
    generate_date_part_feature_names,
    get_template_spec,
    validate_recipe_definition,
)
from app.services.mapping_service import MappingValidationError, preview_mapping_data

DEFAULT_SAMPLE_SIZE = 100
MAX_SAMPLE_SIZE = 500

TABLE_MODELS: dict[str, type] = {
    "heat_demand_actual": HeatDemandActual,
    "weather_observation": WeatherObservation,
}

ENTITY_KEY_CANDIDATES = ("site_id", "weather_area_id")
TIME_KEY_DEFAULT = "measured_at"

PREVIEW_NOT_SUPPORTED_MSG = (
    "R3 단계에서는 RAW_COLUMN과 DATE_PART Preview만 지원합니다. "
    "LAG/ROLLING Preview는 R4에서 제공됩니다."
)


def _parse_optional_dt(value: Any) -> datetime | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.replace(tzinfo=None) if value.tzinfo else value
    text = str(value).strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(text).replace(tzinfo=None)
    except ValueError:
        return None


def _serialize_value(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    if hasattr(value, "__float__"):
        try:
            return float(value)
        except (TypeError, ValueError):
            pass
    return value


def _normalize_table_key(target_table: str | None) -> str:
    if not target_table:
        return ""
    return target_table.lower().replace("tb_", "")


def _allowed_columns(mapping: DataMapping) -> set[str]:
    cols: set[str] = set()
    for rule in mapping.columns or []:
        for key in ("source_column", "target_column"):
            val = rule.get(key)
            if val:
                cols.add(str(val))
    return cols


def _resolve_time_column(recipe: dict[str, Any], mapping: DataMapping) -> str:
    if recipe.get("time_key"):
        return str(recipe["time_key"])
    for rule in mapping.columns or []:
        tgt = str(rule.get("target_column") or "")
        if tgt in ("measured_at", "target_at"):
            return tgt
    return TIME_KEY_DEFAULT


def _resolve_entity_keys(recipe: dict[str, Any], mapping: DataMapping) -> list[str]:
    if recipe.get("entity_keys"):
        return [str(k) for k in recipe["entity_keys"]]
    allowed = _allowed_columns(mapping)
    for candidate in ENTITY_KEY_CANDIDATES:
        if candidate in allowed:
            return [candidate]
    return []


async def _get_source(db: AsyncSession, source_id: str) -> DataSource:
    row = (
        await db.execute(select(DataSource).where(DataSource.data_source_id == source_id))
    ).scalar_one_or_none()
    if not row:
        raise LookupError(f"데이터 소스를 찾을 수 없습니다: {source_id}")
    return row


async def _load_from_standard_table(
    db: AsyncSession,
    model: type,
    mapping: DataMapping,
    *,
    sample_size: int,
    start_at: datetime | None,
    end_at: datetime | None,
    time_key: str,
) -> list[dict[str, Any]]:
    allowed = _allowed_columns(mapping)
    model_cols = {c.name for c in model.__table__.columns}
    select_cols = sorted(allowed & model_cols)
    if not select_cols:
        return []

    attrs = [getattr(model, name) for name in select_cols]
    ts_attr = getattr(model, time_key, None) if time_key in model_cols else getattr(model, TIME_KEY_DEFAULT, None)
    q = select(*attrs)
    if ts_attr is not None:
        if start_at:
            q = q.where(ts_attr >= start_at)
        if end_at:
            q = q.where(ts_attr <= end_at)
        q = q.order_by(ts_attr.desc()).limit(sample_size)
    else:
        q = q.limit(sample_size)

    rows = (await db.execute(q)).mappings().all()
    serialized = [{k: _serialize_value(v) for k, v in dict(row).items()} for row in reversed(rows)]
    return serialized


async def load_preview_rows(
    db: AsyncSession,
    mapping: DataMapping,
    *,
    sample_size: int,
    start_at: datetime | None = None,
    end_at: datetime | None = None,
    time_key: str | None = None,
) -> list[dict[str, Any]]:
    table_key = _normalize_table_key(mapping.target_table)
    model = TABLE_MODELS.get(table_key)
    ts_col = time_key or TIME_KEY_DEFAULT

    if model:
        db_rows = await _load_from_standard_table(
            db,
            model,
            mapping,
            sample_size=sample_size,
            start_at=start_at,
            end_at=end_at,
            time_key=ts_col,
        )
        if db_rows:
            return db_rows

    source = await _get_source(db, mapping.source_id)
    try:
        return await asyncio.to_thread(
            preview_mapping_data,
            source,
            mapping,
            sample_size,
            start_at,
            end_at,
        )
    except (MappingValidationError, ValueError):
        return []


def _parse_row_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.replace(tzinfo=None) if value.tzinfo else value
    text = str(value).strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(text).replace(tzinfo=None)
    except ValueError:
        return None


def _compute_date_part_value(dt: datetime | None, part: str) -> tuple[Any, bool]:
    if dt is None:
        return None, True
    if part == "hour":
        return dt.hour, False
    if part == "day_of_week":
        return dt.weekday(), False
    if part == "month":
        return dt.month, False
    if part == "day":
        return dt.day, False
    if part == "is_weekend":
        return 1 if dt.weekday() >= 5 else 0, False
    if part == "week_of_year":
        return dt.isocalendar().week, False
    return None, True


def apply_raw_column_preview(
    rows: list[dict[str, Any]],
    *,
    source_column: str,
    output_name: str,
    entity_keys: list[str],
    time_key: str | None,
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for row in rows:
        out: dict[str, Any] = {}
        for key in entity_keys:
            if key in row:
                out[key] = _serialize_value(row[key])
        if time_key and time_key in row:
            out[time_key] = _serialize_value(row[time_key])
        out[output_name] = _serialize_value(row.get(source_column))
        result.append(out)
    return result


def apply_date_part_preview(
    rows: list[dict[str, Any]],
    *,
    source_column: str,
    time_key: str,
    parts: list[str],
    output_names: list[str],
    entity_keys: list[str],
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    invalid_counts: dict[str, int] = {name: 0 for name in output_names}
    result: list[dict[str, Any]] = []
    part_name_map = dict(zip(parts, output_names, strict=False))

    for row in rows:
        out: dict[str, Any] = {}
        for key in entity_keys:
            if key in row:
                out[key] = _serialize_value(row[key])
        if time_key in row:
            out[time_key] = _serialize_value(row[time_key])

        dt = _parse_row_datetime(row.get(source_column) or row.get(time_key))
        for part, feat_name in part_name_map.items():
            val, invalid = _compute_date_part_value(dt, part)
            if invalid:
                invalid_counts[feat_name] = invalid_counts.get(feat_name, 0) + 1
            out[feat_name] = val
        result.append(out)
    return result, invalid_counts


def compute_preview_stats(
    preview_rows: list[dict[str, Any]],
    output_feature_names: list[str],
    *,
    invalid_counts: dict[str, int] | None = None,
) -> dict[str, Any]:
    invalid_counts = invalid_counts or {}
    row_count = len(preview_rows)
    features: dict[str, Any] = {}

    for name in output_feature_names:
        values = [row.get(name) for row in preview_rows]
        null_count = sum(1 for v in values if v is None)
        numeric_vals = [float(v) for v in values if v is not None and isinstance(v, (int, float))]
        feat_stats: dict[str, Any] = {
            "null_count": null_count,
            "null_ratio": round(null_count / row_count, 4) if row_count else 0,
            "invalid_count": invalid_counts.get(name, 0),
        }
        if numeric_vals:
            feat_stats["min"] = min(numeric_vals)
            feat_stats["max"] = max(numeric_vals)
        features[name] = feat_stats

    return {
        "row_count": row_count,
        "sample_size": row_count,
        "features": features,
    }


def build_quality_preview(stats: dict[str, Any]) -> dict[str, Any]:
    warnings: list[str] = []
    estimated_status = "SUCCESS"
    for name, feat in (stats.get("features") or {}).items():
        if feat.get("invalid_count", 0) > 0:
            warnings.append(f"{name}: 날짜 파싱 실패 {feat['invalid_count']}건")
            estimated_status = "WARNING"
        if feat.get("null_ratio", 0) > 0.5:
            warnings.append(f"{name}: 결측 비율 {feat['null_ratio']:.0%}")
            estimated_status = "WARNING"
    return {"estimated_status": estimated_status, "warnings": warnings}


def _empty_preview_response(
  recipe_type: str,
  *,
  supported: bool,
  valid: bool,
  errors: list[dict[str, str]] | None = None,
  warnings: list[str] | None = None,
  infos: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "preview_id": f"PREVIEW-LOCAL-{uuid4().hex[:12].upper()}",
        "recipe_type": recipe_type,
        "supported": supported,
        "valid": valid,
        "generated_feature_names": [],
        "output_feature_names": [],
        "reusable_existing_features": [],
        "preview_rows": [],
        "stats": {"row_count": 0, "sample_size": 0, "features": {}},
        "lineage_preview": None,
        "quality_preview": {"estimated_status": "FAILED", "warnings": []},
        "errors": errors or [],
        "warnings": warnings or [],
        "infos": infos or [],
    }


async def preview_feature_recipe(db: AsyncSession, request: dict[str, Any]) -> dict[str, Any]:
    recipe_type = str(request.get("recipe_type") or "").strip()
    sample_size = min(
        max(1, int(request.get("sample_size") or DEFAULT_SAMPLE_SIZE)),
        MAX_SAMPLE_SIZE,
    )
    start_at = _parse_optional_dt(request.get("start_at"))
    end_at = _parse_optional_dt(request.get("end_at"))

    if recipe_type not in PREVIEW_SUPPORTED_RECIPE_TYPES:
        return _empty_preview_response(
            recipe_type,
            supported=False,
            valid=False,
            errors=[
                {
                    "code": "PREVIEW_NOT_SUPPORTED",
                    "message": PREVIEW_NOT_SUPPORTED_MSG,
                }
            ],
        )

    mapping_id = request.get("mapping_id")
    if not mapping_id:
        return _empty_preview_response(
            recipe_type,
            supported=True,
            valid=False,
            errors=[{"code": "MISSING_MAPPING_ID", "message": "mapping_id가 필요합니다."}],
        )

    try:
        mapping = await get_mapping_or_raise(db, mapping_id)
        role_data = await list_column_roles(db, mapping_id=mapping_id, include_inferred=False)
    except LookupError as exc:
        return _empty_preview_response(
            recipe_type,
            supported=True,
            valid=False,
            errors=[{"code": "MAPPING_NOT_FOUND", "message": str(exc)}],
        )

    recipe = {
        k: v
        for k, v in request.items()
        if k not in ("sample_size", "start_at", "end_at")
    }

    validate_result = await validate_recipe_definition(
        db,
        recipe,
        mapping_columns=list(mapping.columns or []),
        role_items=role_data.get("items") or [],
    )

    if not validate_result.get("valid"):
        return {
            **_empty_preview_response(recipe_type, supported=True, valid=False),
            "errors": validate_result.get("errors") or [],
            "warnings": validate_result.get("warnings") or [],
            "infos": validate_result.get("infos") or [],
            "generated_feature_names": validate_result.get("generated_feature_names") or [],
            "output_feature_names": validate_result.get("output_feature_names") or [],
            "reusable_existing_features": validate_result.get("reusable_existing_features") or [],
            "lineage_preview": validate_result.get("lineage_preview"),
        }

    output_names = list(
        validate_result.get("output_feature_names")
        or validate_result.get("generated_feature_names")
        or []
    )
    time_key = _resolve_time_column(recipe, mapping)
    entity_keys = _resolve_entity_keys(recipe, mapping)
    source_columns = list(recipe.get("source_columns") or [])
    source_column = source_columns[0] if source_columns else time_key

    rows = await load_preview_rows(
        db,
        mapping,
        sample_size=sample_size,
        start_at=start_at,
        end_at=end_at,
        time_key=time_key,
    )

    if not rows:
        return {
            **_empty_preview_response(
                recipe_type,
                supported=True,
                valid=True,
                warnings=["샘플 데이터가 없습니다. 적재 데이터 또는 소스 파일을 확인하세요."],
            ),
            "generated_feature_names": output_names,
            "output_feature_names": output_names,
            "reusable_existing_features": validate_result.get("reusable_existing_features") or [],
            "lineage_preview": validate_result.get("lineage_preview"),
            "quality_preview": {"estimated_status": "WARNING", "warnings": ["샘플 데이터 없음"]},
            "infos": validate_result.get("infos") or [],
        }

    invalid_counts: dict[str, int] = {}
    if recipe_type == "RAW_COLUMN":
        preview_rows = apply_raw_column_preview(
            rows,
            source_column=source_column,
            output_name=output_names[0],
            entity_keys=entity_keys,
            time_key=time_key,
        )
    else:
        params = recipe.get("params") or {}
        parts = params.get("parts") or ["hour"]
        if isinstance(parts, str):
            parts = [parts]
        spec = get_template_spec("DATE_PART")
        if spec and len(output_names) != len(parts):
            output_names = generate_date_part_feature_names(recipe, spec)
        preview_rows, invalid_counts = apply_date_part_preview(
            rows,
            source_column=source_column,
            time_key=time_key,
            parts=parts,
            output_names=output_names,
            entity_keys=entity_keys,
        )

    stats = compute_preview_stats(preview_rows, output_names, invalid_counts=invalid_counts)
    quality_preview = build_quality_preview(stats)

    return {
        "preview_id": f"PREVIEW-LOCAL-{uuid4().hex[:12].upper()}",
        "recipe_type": recipe_type,
        "supported": True,
        "valid": True,
        "generated_feature_names": output_names,
        "output_feature_names": output_names,
        "reusable_existing_features": validate_result.get("reusable_existing_features") or [],
        "duplicate_policy": validate_result.get("duplicate_policy"),
        "preview_rows": preview_rows,
        "stats": stats,
        "lineage_preview": validate_result.get("lineage_preview"),
        "quality_preview": quality_preview,
        "errors": [],
        "warnings": validate_result.get("warnings") or [],
        "infos": validate_result.get("infos") or [],
    }


async def count_feature_dataset_rows(db: AsyncSession) -> int:
    return int((await db.execute(select(func.count()).select_from(FeatureDataset))).scalar_one())
