"""Wide-hour → long format 변환 (R10-S3 열수요 API)."""

from __future__ import annotations

import json
import re
from datetime import date, datetime, time, timedelta
from typing import Any
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.time import utc_now
from app.models.entities import ApiConnectorTransformConfig, PredictionEntity
from app.services.api_connector_loader import get_physical_columns
from app.services.external_code_mapping_service import resolve_or_log_unmapped
from app.services.standard_dataset_service import validate_target_table_allowed

TRANSFORM_TYPES = frozenset(
    {"NONE", "WIDE_HOUR_TO_LONG", "ASOS_HOURLY_TO_CANONICAL", "CALENDAR_SPECIAL_DAY_TO_DATE", "CALENDAR_DATE_TO_HOUR"}
)
TIMESTAMP_POLICIES = frozenset({"HOUR_LABEL_AS_END", "HOUR_LABEL_AS_START"})
HOUR_24_POLICIES = frozenset({"NEXT_DAY_00", "SAME_DAY_23"})
UNMAPPED_POLICIES = frozenset({"FAIL_LOAD", "SKIP_UNMAPPED", "LOG_ONLY"})
NULL_VALUE_POLICIES = frozenset({"SKIP_NULL", "INSERT_NULL", "FAIL_ON_NULL"})

DEFAULT_WIDE_HOUR_CONFIG: dict[str, Any] = {
    "transform_type": "WIDE_HOUR_TO_LONG",
    "source_system": "HEAT_DEMAND_API",
    "external_code_group": "NODE",
    "external_code_field": "ND_ID",
    "external_name_field": "ND_KORN_NM",
    "date_field": "BAS_YMD",
    "date_format": "YYYYMMDD",
    "hour_column_prefix": "HTDND_AMNT_",
    "hour_column_suffix": "HR",
    "hour_start": 1,
    "hour_end": 24,
    "value_output_field": "heat_demand",
    "measured_at_output_field": "measured_at",
    "entity_id_output_field": "entity_id",
    "entity_code_output_field": "site_id",
    "external_code_output_field": "external_node_id",
    "external_name_output_field": "external_node_name",
    "timestamp_policy": "HOUR_LABEL_AS_END",
    "hour_24_policy": "NEXT_DAY_00",
    "unmapped_policy": "FAIL_LOAD",
    "null_value_policy": "SKIP_NULL",
    "numeric_parse_policy": "ALLOW_COMMA",
    "active_yn": True,
    "station_code_field": "stnId",
    "observed_at_field": "tm",
    "value_field_mappings_json": None,
    "special_day_name_field": "dateName",
    "special_day_type_field": None,
    "default_special_day_type": "PUBLIC_HOLIDAY",
    "public_holiday_field": "isHoliday",
    "calendar_mode": "FULL_CALENDAR_WITH_OVERLAY",
    "calendar_year": None,
    "calendar_month": None,
    "hour_generation_yn": False,
    "station_unmapped_policy": "WARN_ONLY",
    "store_raw_json": True,
}

DEFAULT_CONFIG_BY_TYPE: dict[str, dict[str, Any]] = {
    "NONE": {"transform_type": "NONE", "active_yn": True},
    "WIDE_HOUR_TO_LONG": DEFAULT_WIDE_HOUR_CONFIG,
    "ASOS_HOURLY_TO_CANONICAL": {
        **DEFAULT_WIDE_HOUR_CONFIG,
        "transform_type": "ASOS_HOURLY_TO_CANONICAL",
        "source_system": "KMA_ASOS_API",
        "station_unmapped_policy": "WARN_ONLY",
        "store_raw_json": True,
    },
    "CALENDAR_SPECIAL_DAY_TO_DATE": {
        **DEFAULT_WIDE_HOUR_CONFIG,
        "transform_type": "CALENDAR_SPECIAL_DAY_TO_DATE",
        "source_system": "KASI_SPECIAL_DAY_API",
        "date_field": "locdate",
        "date_format": "YYYYMMDD",
        "calendar_mode": "FULL_CALENDAR_WITH_OVERLAY",
        "store_raw_json": True,
    },
    "CALENDAR_DATE_TO_HOUR": {
        **DEFAULT_WIDE_HOUR_CONFIG,
        "transform_type": "CALENDAR_DATE_TO_HOUR",
        "source_system": "KASI_SPECIAL_DAY_API",
        "date_field": "locdate",
        "date_format": "YYYYMMDD",
        "hour_start": 0,
        "hour_end": 23,
        "calendar_mode": "FULL_CALENDAR_WITH_OVERLAY",
        "hour_generation_yn": True,
        "store_raw_json": True,
    },
}

CONFIG_FIELD_KEYS = frozenset(DEFAULT_WIDE_HOUR_CONFIG.keys()) | frozenset(
    {
        "transform_type",
        "transform_name",
        "active_yn",
        "metadata_json",
    }
)


class WideHourTransformError(ValueError):
    def __init__(self, message: str, *, error_code: str = "WIDE_HOUR_TRANSFORM_ERROR"):
        self.error_code = error_code
        super().__init__(message)


def _new_id(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex[:8].upper()}"


def _config_dict(row: ApiConnectorTransformConfig) -> dict[str, Any]:
    return {
        "transform_config_id": row.transform_config_id,
        "operation_id": row.operation_id,
        "transform_type": row.transform_type,
        "transform_name": row.transform_name,
        "source_system": row.source_system,
        "external_code_group": row.external_code_group,
        "external_code_field": row.external_code_field,
        "external_name_field": row.external_name_field,
        "date_field": row.date_field,
        "date_format": row.date_format,
        "hour_column_prefix": row.hour_column_prefix,
        "hour_column_suffix": row.hour_column_suffix,
        "hour_start": row.hour_start,
        "hour_end": row.hour_end,
        "value_output_field": row.value_output_field,
        "measured_at_output_field": row.measured_at_output_field,
        "entity_id_output_field": row.entity_id_output_field,
        "entity_code_output_field": row.entity_code_output_field,
        "external_code_output_field": row.external_code_output_field,
        "external_name_output_field": row.external_name_output_field,
        "timestamp_policy": row.timestamp_policy,
        "hour_24_policy": row.hour_24_policy,
        "unmapped_policy": row.unmapped_policy,
        "null_value_policy": row.null_value_policy,
        "numeric_parse_policy": row.numeric_parse_policy,
        "active_yn": bool(row.active_yn),
        "metadata_json": row.metadata_json,
        "station_code_field": row.station_code_field,
        "observed_at_field": row.observed_at_field,
        "value_field_mappings_json": row.value_field_mappings_json,
        "special_day_name_field": row.special_day_name_field,
        "special_day_type_field": row.special_day_type_field,
        "default_special_day_type": row.default_special_day_type,
        "public_holiday_field": row.public_holiday_field,
        "calendar_mode": row.calendar_mode,
        "calendar_year": row.calendar_year,
        "calendar_month": row.calendar_month,
        "hour_generation_yn": bool(row.hour_generation_yn),
        "station_unmapped_policy": row.station_unmapped_policy,
        "store_raw_json": bool(row.store_raw_json),
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def validate_transform_config(config: dict[str, Any]) -> list[str]:
    warnings: list[str] = []
    ttype = (config.get("transform_type") or "NONE").upper()
    if ttype not in TRANSFORM_TYPES:
        raise WideHourTransformError("지원하지 않는 변환 유형입니다.")
    if ttype == "NONE":
        return warnings
    if ttype != "WIDE_HOUR_TO_LONG":
        return warnings
    if config.get("timestamp_policy") not in TIMESTAMP_POLICIES:
        raise WideHourTransformError("시간 해석 방식(timestamp_policy)이 올바르지 않습니다.")
    if config.get("hour_24_policy") not in HOUR_24_POLICIES:
        raise WideHourTransformError("24시간 처리 방식(hour_24_policy)이 올바르지 않습니다.")
    if config.get("unmapped_policy") not in UNMAPPED_POLICIES:
        raise WideHourTransformError("미매핑 처리 방식이 올바르지 않습니다.")
    if config.get("null_value_policy") not in NULL_VALUE_POLICIES:
        raise WideHourTransformError("NULL 값 처리 방식이 올바르지 않습니다.")
    hour_start = int(config.get("hour_start") or 1)
    hour_end = int(config.get("hour_end") or 24)
    if hour_start < 1 or hour_end > 24 or hour_start > hour_end:
        raise WideHourTransformError("시간 컬럼 범위(hour_start~hour_end)가 올바르지 않습니다.")
    warnings.append(
        "열수요 API의 1HR/24HR 의미는 기관 API 정의에 따라 다를 수 있습니다. "
        "운영 적용 전 1HR이 01:00 시점인지, 00:00~01:00 구간인지 확인하세요."
    )
    if config.get("unmapped_policy") == "LOG_ONLY":
        warnings.append("LOG_ONLY 정책은 entity_id/site_id 없이 변환됩니다. 학습용 데이터에는 권장하지 않습니다.")
    return warnings


async def get_transform_config(db: AsyncSession, operation_id: str) -> dict[str, Any] | None:
    row = (
        await db.execute(
            select(ApiConnectorTransformConfig).where(ApiConnectorTransformConfig.operation_id == operation_id)
        )
    ).scalar_one_or_none()
    if not row:
        return None
    return _config_dict(row)


def validate_connector_transform_config(config: dict[str, Any]) -> list[str]:
    ttype = (config.get("transform_type") or "NONE").upper()
    if ttype not in TRANSFORM_TYPES:
        raise WideHourTransformError("지원하지 않는 변환 유형입니다.")
    if ttype == "NONE":
        return []
    if ttype == "WIDE_HOUR_TO_LONG":
        return validate_transform_config(config)
    if ttype == "ASOS_HOURLY_TO_CANONICAL":
        from app.services.weather_observation_transform_service import validate_asos_transform_config

        return validate_asos_transform_config(config)
    if ttype == "CALENDAR_SPECIAL_DAY_TO_DATE":
        from app.services.calendar_transform_service import validate_calendar_transform_config

        return validate_calendar_transform_config(config, hour_mode=False)
    if ttype == "CALENDAR_DATE_TO_HOUR":
        from app.services.calendar_transform_service import validate_calendar_transform_config

        return validate_calendar_transform_config(config, hour_mode=True)
    return []


async def save_transform_config(db: AsyncSession, operation_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    existing = await get_transform_config(db, operation_id)
    ttype = (payload.get("transform_type") or (existing or {}).get("transform_type") or "NONE").upper()
    base_defaults = DEFAULT_CONFIG_BY_TYPE.get(ttype, DEFAULT_WIDE_HOUR_CONFIG)
    if existing:
        base_defaults = {**base_defaults, **{k: v for k, v in existing.items() if v is not None and k != "policy_warnings"}}
    merged = {**base_defaults, **{k: v for k, v in payload.items() if v is not None}}
    merged["transform_type"] = ttype
    warnings = validate_connector_transform_config(merged)
    now = utc_now()
    row = (
        await db.execute(
            select(ApiConnectorTransformConfig).where(ApiConnectorTransformConfig.operation_id == operation_id)
        )
    ).scalar_one_or_none()
    if row:
        for key in CONFIG_FIELD_KEYS:
            if key in merged:
                setattr(row, key, merged[key])
        row.updated_at = now
    else:
        fields = {k: merged[k] for k in CONFIG_FIELD_KEYS if k in merged}
        row = ApiConnectorTransformConfig(
            transform_config_id=_new_id("ACTC"),
            operation_id=operation_id,
            created_at=now,
            updated_at=now,
            **fields,
        )
        db.add(row)
    await db.flush()
    result = _config_dict(row)
    result["policy_warnings"] = warnings
    return result


def _item_field(item: dict[str, Any], field: str) -> Any:
    if field in item:
        return item[field]
    return None


def parse_date_value(value: Any, date_format: str) -> date:
    text = str(value).strip()
    if date_format == "YYYYMMDD" and len(text) == 8 and text.isdigit():
        return date(int(text[0:4]), int(text[4:6]), int(text[6:8]))
    if date_format == "YYYY-MM-DD":
        return date.fromisoformat(text[:10])
    raise WideHourTransformError(f"날짜 형식을 해석할 수 없습니다: {value}")


def build_measured_at(base_date: date, hour: int, config: dict[str, Any]) -> datetime:
    policy = config.get("timestamp_policy") or "HOUR_LABEL_AS_END"
    h24 = config.get("hour_24_policy") or "NEXT_DAY_00"
    if policy == "HOUR_LABEL_AS_END":
        if hour == 24:
            if h24 == "NEXT_DAY_00":
                return datetime.combine(base_date + timedelta(days=1), time(0, 0))
            return datetime.combine(base_date, time(23, 0))
        return datetime.combine(base_date, time(hour, 0))
    if hour == 24:
        return datetime.combine(base_date, time(23, 0))
    return datetime.combine(base_date, time(hour - 1, 0))


def hour_column_name(hour: int, config: dict[str, Any]) -> str:
    return f"{config.get('hour_column_prefix', 'HTDND_AMNT_')}{hour}{config.get('hour_column_suffix', 'HR')}"


def parse_numeric_value(value: Any, config: dict[str, Any]) -> tuple[float | None, str | None]:
    if value is None:
        return None, None
    text = str(value).strip()
    if not text:
        return None, None
    if config.get("numeric_parse_policy") == "ALLOW_COMMA":
        text = text.replace(",", "")
    try:
        return float(text), None
    except ValueError:
        return None, f"숫자로 변환할 수 없습니다: {value}"


async def _fetch_entity(db: AsyncSession, entity_id: str) -> PredictionEntity | None:
    return (
        await db.execute(select(PredictionEntity).where(PredictionEntity.entity_id == entity_id))
    ).scalar_one_or_none()


async def resolve_entity_for_item(
    db: AsyncSession,
    item: dict[str, Any],
    config: dict[str, Any],
    *,
    source_operation_id: str | None = None,
) -> dict[str, Any]:
    ext_code = _item_field(item, config.get("external_code_field") or "ND_ID")
    ext_name = _item_field(item, config.get("external_name_field") or "ND_KORN_NM")
    if ext_code is None or str(ext_code).strip() == "":
        return {"resolved": False, "warnings": ["외부 지점 코드가 비어 있습니다."]}
    resolved = await resolve_or_log_unmapped(
        db,
        source_system=config.get("source_system") or "HEAT_DEMAND_API",
        external_code_group=config.get("external_code_group") or "NODE",
        external_code=str(ext_code).strip(),
        target_type="PREDICTION_ENTITY",
        external_code_name=str(ext_name).strip() if ext_name else None,
        source_operation_id=source_operation_id,
        sample_payload_json={k: item.get(k) for k in list(item.keys())[:12]},
    )
    if not resolved.get("resolved"):
        return {
            **resolved,
            "external_code": str(ext_code).strip(),
            "external_code_name": ext_name,
        }
    entity = await _fetch_entity(db, resolved["target_id"])
    return {
        **resolved,
        "external_code": str(ext_code).strip(),
        "external_code_name": ext_name,
        "entity_code": entity.entity_code if entity else None,
        "entity_name": entity.entity_name if entity else resolved.get("target_display_name"),
    }


def build_output_row(
    item: dict[str, Any],
    hour: int,
    value: float | None,
    measured_at: datetime,
    entity_info: dict[str, Any],
    config: dict[str, Any],
    *,
    source_operation_id: str | None = None,
) -> dict[str, Any]:
    row: dict[str, Any] = {}
    row[config.get("value_output_field") or "heat_demand"] = value
    row[config.get("measured_at_output_field") or "measured_at"] = measured_at.isoformat(sep="T", timespec="seconds")
    row[config.get("external_code_output_field") or "external_node_id"] = entity_info.get("external_code")
    if entity_info.get("external_code_name") is not None:
        row[config.get("external_name_output_field") or "external_node_name"] = entity_info.get("external_code_name")
    if entity_info.get("resolved"):
        row[config.get("entity_id_output_field") or "entity_id"] = entity_info.get("target_id")
        if entity_info.get("entity_code"):
            row[config.get("entity_code_output_field") or "site_id"] = entity_info.get("entity_code")
    row["source_system"] = config.get("source_system") or "HEAT_DEMAND_API"
    if source_operation_id:
        row["source_operation_id"] = source_operation_id
    date_val = _item_field(item, config.get("date_field") or "BAS_YMD")
    if date_val is not None:
        row["raw_date"] = str(date_val)
    row["raw_hour"] = hour
    try:
        row["raw_json"] = json.dumps({k: item.get(k) for k in item if not re.match(r".*_\d+HR$", k)}, ensure_ascii=False)
    except (TypeError, ValueError):
        row["raw_json"] = None
    return row


async def transform_wide_hour_items(
    db: AsyncSession,
    raw_items: list[dict[str, Any]],
    config: dict[str, Any],
    *,
    source_operation_id: str | None = None,
) -> dict[str, Any]:
    warnings = validate_transform_config(config)
    hour_start = int(config.get("hour_start") or 1)
    hour_end = int(config.get("hour_end") or 24)
    unmapped_policy = config.get("unmapped_policy") or "FAIL_LOAD"
    null_policy = config.get("null_value_policy") or "SKIP_NULL"

    rows: list[dict[str, Any]] = []
    unmapped_codes: list[dict[str, Any]] = []
    skipped_null_count = 0
    invalid_numeric_count = 0
    skipped_unmapped_count = 0
    blocked = False
    block_reason: str | None = None

    for item in raw_items:
        entity_info = await resolve_entity_for_item(
            db, item, config, source_operation_id=source_operation_id
        )
        if not entity_info.get("resolved"):
            unmapped_codes.append(
                {
                    "external_code": entity_info.get("external_code"),
                    "external_code_name": entity_info.get("external_code_name"),
                    "unmapped_id": entity_info.get("unmapped_id"),
                }
            )
            if unmapped_policy == "FAIL_LOAD":
                blocked = True
                block_reason = "미매핑 외부 지점 코드가 있어 적재를 중단합니다. 외부 코드 매핑 화면에서 예측 대상과 연결하세요."
                break
            if unmapped_policy == "SKIP_UNMAPPED":
                skipped_unmapped_count += 1
                continue

        try:
            base_date = parse_date_value(
                _item_field(item, config.get("date_field") or "BAS_YMD"),
                config.get("date_format") or "YYYYMMDD",
            )
        except WideHourTransformError as exc:
            warnings.append(str(exc))
            continue

        for hour in range(hour_start, hour_end + 1):
            col = hour_column_name(hour, config)
            raw_val = item.get(col)
            if raw_val is None or str(raw_val).strip() == "":
                if null_policy == "FAIL_ON_NULL":
                    blocked = True
                    block_reason = f"{col} 값이 비어 있어 변환을 중단합니다."
                    break
                if null_policy == "SKIP_NULL":
                    skipped_null_count += 1
                    continue
                numeric_val = None
            else:
                numeric_val, num_err = parse_numeric_value(raw_val, config)
                if num_err:
                    invalid_numeric_count += 1
                    warnings.append(num_err)
                    continue
            measured_at = build_measured_at(base_date, hour, config)
            rows.append(
                build_output_row(
                    item,
                    hour,
                    numeric_val,
                    measured_at,
                    entity_info,
                    config,
                    source_operation_id=source_operation_id,
                )
            )
        if blocked:
            break

    diagnostics = {
        "transform_type": "WIDE_HOUR_TO_LONG",
        "raw_item_count": len(raw_items),
        "transformed_row_count": len(rows),
        "unmapped_code_count": len(unmapped_codes),
        "skipped_null_count": skipped_null_count,
        "skipped_unmapped_count": skipped_unmapped_count,
        "invalid_numeric_count": invalid_numeric_count,
        "timestamp_policy": config.get("timestamp_policy"),
        "hour_24_policy": config.get("hour_24_policy"),
        "warnings": warnings,
    }
    return {
        "rows": rows,
        "diagnostics": diagnostics,
        "unmapped_codes": unmapped_codes,
        "warnings": warnings,
        "blocked": blocked,
        "block_reason": block_reason,
    }


async def match_target_columns(
    db: AsyncSession,
    target_table: str,
    sample_row: dict[str, Any],
) -> dict[str, Any]:
    await validate_target_table_allowed(db, target_table)
    cols = await get_physical_columns(db, target_table)
    matched = {c: sample_row.get(c) for c in cols if c in sample_row}
    missing_required: list[str] = []
    for req in ("measured_at", "heat_demand"):
        if req in cols and req not in matched:
            missing_required.append(req)
    entity_cols = [c for c in ("entity_id", "site_id") if c in cols]
    if entity_cols and not any(c in matched for c in entity_cols):
        missing_required.append("entity_id 또는 site_id")
    return {
        "target_columns": cols,
        "matched_columns": list(matched.keys()),
        "column_matching": {c: c in sample_row for c in cols},
        "missing_required": missing_required,
    }


async def preview_wide_hour_transform(
    db: AsyncSession,
    *,
    operation_id: str,
    raw_items: list[dict[str, Any]],
    target_table: str | None = None,
) -> dict[str, Any]:
    config = await get_transform_config(db, operation_id)
    if not config or config.get("transform_type") != "WIDE_HOUR_TO_LONG" or not config.get("active_yn", True):
        raise WideHourTransformError("활성화된 WIDE_HOUR_TO_LONG 변환 설정이 없습니다.")
    result = await transform_wide_hour_items(
        db, raw_items, config, source_operation_id=operation_id
    )
    sample_rows = result["rows"][:10]
    column_info: dict[str, Any] = {}
    if target_table and sample_rows:
        column_info = await match_target_columns(db, target_table, sample_rows[0])
    return {
        "operation_id": operation_id,
        "target_table": target_table,
        "raw_item_count": len(raw_items),
        "transformed_row_count": len(result["rows"]),
        "sample_rows": sample_rows,
        "unmapped_codes": result["unmapped_codes"],
        "warnings": result["warnings"],
        "transform_summary": result["diagnostics"],
        "blocked": result["blocked"],
        "block_reason": result.get("block_reason"),
        **column_info,
    }


async def apply_wide_hour_transform_if_configured(
    db: AsyncSession,
    operation_id: str,
    raw_items: list[dict[str, Any]],
    config: dict[str, Any],
    *,
    for_load: bool = False,
) -> dict[str, Any]:
    result = await transform_wide_hour_items(
        db, raw_items, config, source_operation_id=operation_id
    )
    if for_load and result.get("blocked"):
        raise WideHourTransformError(
            result.get("block_reason") or "변환 중단",
            error_code="UNMAPPED_EXTERNAL_CODE",
        )
    return {
        "items": result["rows"],
        "transform_applied": True,
        "transform_summary": result["diagnostics"],
        "unmapped_codes": result["unmapped_codes"],
        "warnings": result.get("warnings", []),
        "blocked": result.get("blocked"),
        "block_reason": result.get("block_reason"),
    }


async def apply_transform_if_configured(
    db: AsyncSession,
    operation_id: str,
    raw_items: list[dict[str, Any]],
    *,
    for_load: bool = False,
) -> dict[str, Any]:
    """Backward-compatible shim — use connector_transform_service.apply_transform_if_configured."""
    from app.services.connector_transform_service import apply_transform_if_configured as _apply

    return await _apply(db, operation_id, raw_items, for_load=for_load)
