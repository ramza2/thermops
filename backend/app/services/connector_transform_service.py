"""API Connector 변환 디스패처 (R10-S3~S4)."""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.calendar_transform_service import (
    CalendarTransformError,
    preview_calendar_hour_transform,
    preview_special_day_transform,
    transform_calendar_date_to_hour_items,
    transform_special_day_items,
)
from app.services.weather_observation_transform_service import (
    WeatherObservationTransformError,
    apply_weather_transform_if_configured,
    preview_asos_hourly_transform,
)
from app.services.wide_hour_transform_service import (
    WideHourTransformError,
    apply_wide_hour_transform_if_configured,
    get_transform_config,
    preview_wide_hour_transform,
    save_transform_config,
    validate_connector_transform_config,
)

ALL_TRANSFORM_TYPES = frozenset(
    {
        "NONE",
        "WIDE_HOUR_TO_LONG",
        "ASOS_HOURLY_TO_CANONICAL",
        "CALENDAR_SPECIAL_DAY_TO_DATE",
        "CALENDAR_DATE_TO_HOUR",
    }
)

TRANSFORM_ERROR_TYPES = (WideHourTransformError, WeatherObservationTransformError, CalendarTransformError)


async def preview_transform(
    db: AsyncSession,
    *,
    operation_id: str,
    raw_items: list[dict[str, Any]],
    target_table: str | None,
) -> dict[str, Any]:
    config = await get_transform_config(db, operation_id)
    ttype = (config or {}).get("transform_type") or "NONE"
    if ttype == "WIDE_HOUR_TO_LONG":
        return await preview_wide_hour_transform(
            db, operation_id=operation_id, raw_items=raw_items, target_table=target_table
        )
    if ttype == "ASOS_HOURLY_TO_CANONICAL":
        if not config:
            raise WeatherObservationTransformError("변환 설정이 없습니다.")
        return await preview_asos_hourly_transform(
            db,
            operation_id=operation_id,
            raw_items=raw_items,
            config=config,
            target_table=target_table,
        )
    if ttype == "CALENDAR_SPECIAL_DAY_TO_DATE":
        if not config:
            raise CalendarTransformError("변환 설정이 없습니다.")
        return await preview_special_day_transform(
            db,
            operation_id=operation_id,
            raw_items=raw_items,
            config=config,
            target_table=target_table,
        )
    if ttype == "CALENDAR_DATE_TO_HOUR":
        if not config:
            raise CalendarTransformError("변환 설정이 없습니다.")
        return await preview_calendar_hour_transform(
            db,
            operation_id=operation_id,
            raw_items=raw_items,
            config=config,
            target_table=target_table,
        )
    return {
        "operation_id": operation_id,
        "target_table": target_table,
        "raw_item_count": len(raw_items),
        "transformed_row_count": len(raw_items),
        "sample_rows": raw_items[:10],
        "unmapped_codes": [],
        "warnings": [],
        "transform_summary": None,
        "blocked": False,
        "block_reason": None,
    }


async def apply_transform_if_configured(
    db: AsyncSession,
    operation_id: str,
    raw_items: list[dict[str, Any]],
    *,
    for_load: bool = False,
) -> dict[str, Any]:
    config = await get_transform_config(db, operation_id)
    if not config or not config.get("active_yn", True):
        return {
            "items": raw_items,
            "transform_applied": False,
            "transform_summary": None,
            "unmapped_codes": [],
            "warnings": [],
        }
    ttype = (config.get("transform_type") or "NONE").upper()
    if ttype == "NONE":
        return {
            "items": raw_items,
            "transform_applied": False,
            "transform_summary": None,
            "unmapped_codes": [],
            "warnings": [],
        }
    if ttype == "WIDE_HOUR_TO_LONG":
        return await apply_wide_hour_transform_if_configured(
            db, operation_id, raw_items, config, for_load=for_load
        )
    if ttype == "ASOS_HOURLY_TO_CANONICAL":
        return await apply_weather_transform_if_configured(
            db, operation_id, raw_items, config, for_load=for_load
        )
    if ttype == "CALENDAR_SPECIAL_DAY_TO_DATE":
        result = await transform_special_day_items(
            raw_items, config, source_operation_id=operation_id
        )
        return {
            "items": result["rows"],
            "transform_applied": True,
            "transform_summary": result["diagnostics"],
            "unmapped_codes": result.get("unmapped_codes", []),
            "warnings": result.get("warnings", []),
            "blocked": result.get("blocked"),
            "block_reason": result.get("block_reason"),
        }
    if ttype == "CALENDAR_DATE_TO_HOUR":
        result = await transform_calendar_date_to_hour_items(
            raw_items, config, source_operation_id=operation_id
        )
        return {
            "items": result["rows"],
            "transform_applied": True,
            "transform_summary": result["diagnostics"],
            "unmapped_codes": result.get("unmapped_codes", []),
            "warnings": result.get("warnings", []),
            "blocked": result.get("blocked"),
            "block_reason": result.get("block_reason"),
        }
    return {
        "items": raw_items,
        "transform_applied": False,
        "transform_summary": None,
        "unmapped_codes": [],
        "warnings": [f"지원하지 않는 변환 유형: {ttype}"],
    }


__all__ = [
    "ALL_TRANSFORM_TYPES",
    "TRANSFORM_ERROR_TYPES",
    "apply_transform_if_configured",
    "get_transform_config",
    "preview_transform",
    "save_transform_config",
    "validate_connector_transform_config",
]
