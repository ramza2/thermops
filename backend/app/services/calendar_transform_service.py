"""Calendar / 특일 → 날짜·시간 달력 행 변환 (R10-S4)."""

from __future__ import annotations

import calendar
import json
from datetime import date, datetime, time, timedelta
from typing import Any

from app.services.wide_hour_transform_service import parse_date_value, WideHourTransformError

CALENDAR_MODES = frozenset({"SPECIAL_DAYS_ONLY", "FULL_CALENDAR_WITH_OVERLAY"})
SPECIAL_DAY_TYPES = frozenset(
    {
        "PUBLIC_HOLIDAY",
        "NATIONAL_HOLIDAY",
        "ANNIVERSARY",
        "SOLAR_TERM",
        "MISC_SPECIAL_DAY",
        "CUSTOM",
    }
)
KOREAN_DAY_NAMES = ("월", "화", "수", "목", "금", "토", "일")
SEASONS = ("WINTER", "SPRING", "SUMMER", "AUTUMN")


class CalendarTransformError(ValueError):
    def __init__(self, message: str, *, error_code: str = "CALENDAR_TRANSFORM_ERROR"):
        self.error_code = error_code
        super().__init__(message)


def _item_field(item: dict[str, Any], field: str) -> Any:
    if field in item:
        return item[field]
    return None


def _is_truthy_holiday(value: Any) -> bool:
    if value is None:
        return False
    text = str(value).strip().upper()
    return text in {"Y", "YES", "TRUE", "1", "T"}


def _season_for_month(month: int) -> str:
    if month in (12, 1, 2):
        return "WINTER"
    if month in (3, 4, 5):
        return "SPRING"
    if month in (6, 7, 8):
        return "SUMMER"
    return "AUTUMN"


def _day_name_korean(d: date) -> str:
    return KOREAN_DAY_NAMES[d.weekday()]


def _parse_special_day_date(value: Any, date_format: str) -> date:
    try:
        return parse_date_value(value, date_format)
    except WideHourTransformError as exc:
        raise CalendarTransformError(str(exc)) from exc


def _infer_special_day_type(item: dict[str, Any], config: dict[str, Any]) -> str:
    type_field = config.get("special_day_type_field")
    raw = _item_field(item, type_field) if type_field else None
    if not raw and "special_day_type" in item:
        raw = item.get("special_day_type")
    if raw:
        candidate = str(raw).strip().upper()
        if candidate in SPECIAL_DAY_TYPES:
            return candidate
    default_type = (config.get("default_special_day_type") or "PUBLIC_HOLIDAY").upper()
    if default_type not in SPECIAL_DAY_TYPES:
        return "PUBLIC_HOLIDAY"
    return default_type


def _special_day_from_item(item: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    date_field = config.get("date_field") or "locdate"
    date_format = config.get("date_format") or "YYYYMMDD"
    name_field = config.get("special_day_name_field") or "dateName"
    holiday_field = config.get("public_holiday_field") or "isHoliday"

    calendar_date = _parse_special_day_date(_item_field(item, date_field), date_format)
    name = _item_field(item, name_field)
    name_text = str(name).strip() if name is not None else None
    day_type = _infer_special_day_type(item, config)
    is_public = _is_truthy_holiday(_item_field(item, holiday_field))
    if day_type in ("PUBLIC_HOLIDAY", "NATIONAL_HOLIDAY"):
        is_public = True
    is_holiday = is_public or day_type in ("PUBLIC_HOLIDAY", "NATIONAL_HOLIDAY", "MISC_SPECIAL_DAY")
    if day_type == "SOLAR_TERM":
        is_holiday = is_public

    return {
        "calendar_date": calendar_date,
        "holiday_name": name_text if is_public else None,
        "special_day_type": day_type,
        "special_day_name": name_text,
        "is_public_holiday": is_public,
        "is_holiday": is_holiday,
        "raw_json": item,
    }


def _build_date_row(
    calendar_date: date,
    *,
    source_system: str,
    source_operation_id: str | None,
    overlay: dict[str, Any] | None,
    store_raw: bool,
) -> dict[str, Any]:
    dow = calendar_date.weekday()
    is_weekend = dow >= 5
    is_holiday = False
    is_public_holiday = False
    holiday_name = None
    special_day_type = None
    special_day_name = None
    solar_term_name = None
    raw_json = None
    extra_special_days: list[dict[str, Any]] = []

    if overlay:
        is_holiday = bool(overlay.get("is_holiday"))
        is_public_holiday = bool(overlay.get("is_public_holiday"))
        holiday_name = overlay.get("holiday_name")
        special_day_type = overlay.get("special_day_type")
        special_day_name = overlay.get("special_day_name")
        if special_day_type == "SOLAR_TERM":
            solar_term_name = special_day_name
        raw_json = overlay.get("raw_json")
        extra_special_days = overlay.get("extra_special_days") or []

    is_workday = not is_weekend and not is_holiday
    row = {
        "calendar_date": calendar_date.isoformat(),
        "year": calendar_date.year,
        "month": calendar_date.month,
        "day": calendar_date.day,
        "day_of_week": dow + 1,
        "day_name": _day_name_korean(calendar_date),
        "is_weekend": is_weekend,
        "is_holiday": is_holiday,
        "is_public_holiday": is_public_holiday,
        "holiday_name": holiday_name,
        "special_day_type": special_day_type,
        "special_day_name": special_day_name,
        "solar_term_name": solar_term_name,
        "is_workday": is_workday,
        "source_system": source_system,
        "source_operation_id": source_operation_id,
    }
    if store_raw and raw_json is not None:
        payload = raw_json if isinstance(raw_json, dict) else {"value": raw_json}
        if extra_special_days:
            payload = {**payload, "_extra_special_days": extra_special_days}
        row["raw_json"] = payload
    return row


def generate_calendar_date_rows(
    year: int,
    month: int | None,
    special_days: list[dict[str, Any]],
    *,
    calendar_mode: str,
    source_system: str,
    source_operation_id: str | None = None,
    store_raw: bool = True,
) -> tuple[list[dict[str, Any]], list[str]]:
    warnings: list[str] = []
    overlay_map: dict[date, dict[str, Any]] = {}
    for sd in special_days:
        d = sd["calendar_date"]
        if d in overlay_map:
            warnings.append(f"중복 특일 날짜 {d.isoformat()}: 첫 번째 항목을 우선 적용합니다.")
            existing = overlay_map[d]
            extra = existing.setdefault("extra_special_days", [])
            extra.append(
                {
                    "special_day_type": sd.get("special_day_type"),
                    "special_day_name": sd.get("special_day_name"),
                    "is_public_holiday": sd.get("is_public_holiday"),
                }
            )
            continue
        overlay_map[d] = sd

    rows: list[dict[str, Any]] = []
    if calendar_mode == "SPECIAL_DAYS_ONLY":
        for d in sorted(overlay_map.keys()):
            rows.append(
                _build_date_row(
                    d,
                    source_system=source_system,
                    source_operation_id=source_operation_id,
                    overlay=overlay_map[d],
                    store_raw=store_raw,
                )
            )
        return rows, warnings

    if month is not None:
        _, last_day = calendar.monthrange(year, month)
        start = date(year, month, 1)
        end = date(year, month, last_day)
    else:
        start = date(year, 1, 1)
        end = date(year, 12, 31)

    current = start
    while current <= end:
        rows.append(
            _build_date_row(
                current,
                source_system=source_system,
                source_operation_id=source_operation_id,
                overlay=overlay_map.get(current),
                store_raw=store_raw,
            )
        )
        current += timedelta(days=1)
    return rows, warnings


def generate_calendar_hour_rows(
    date_rows: list[dict[str, Any]],
    *,
    hour_start: int = 0,
    hour_end: int = 23,
) -> list[dict[str, Any]]:
    hour_rows: list[dict[str, Any]] = []
    for dr in date_rows:
        cal_text = dr.get("calendar_date")
        if not cal_text:
            continue
        cal_date = date.fromisoformat(str(cal_text)[:10])
        for hour in range(int(hour_start), int(hour_end) + 1):
            measured_at = datetime.combine(cal_date, time(hour, 0))
            hour_rows.append(
                {
                    "measured_at": measured_at.isoformat(),
                    "calendar_date": cal_date.isoformat(),
                    "hour": hour,
                    "year": dr.get("year", cal_date.year),
                    "month": dr.get("month", cal_date.month),
                    "day": dr.get("day", cal_date.day),
                    "day_of_week": dr.get("day_of_week", cal_date.weekday() + 1),
                    "is_weekend": dr.get("is_weekend", cal_date.weekday() >= 5),
                    "is_holiday": dr.get("is_holiday", False),
                    "is_public_holiday": dr.get("is_public_holiday", False),
                    "is_workday": dr.get("is_workday", True),
                    "season": _season_for_month(cal_date.month),
                    "holiday_name": dr.get("holiday_name"),
                    "special_day_type": dr.get("special_day_type"),
                    "special_day_name": dr.get("special_day_name"),
                }
            )
    return hour_rows


def validate_calendar_transform_config(config: dict[str, Any], *, hour_mode: bool = False) -> list[str]:
    warnings: list[str] = []
    mode = (config.get("calendar_mode") or "FULL_CALENDAR_WITH_OVERLAY").upper()
    if mode not in CALENDAR_MODES:
        raise CalendarTransformError("달력 변환 모드(calendar_mode)가 올바르지 않습니다.")
    if not hour_mode:
        year = config.get("calendar_year")
        if mode == "FULL_CALENDAR_WITH_OVERLAY" and year is None:
            raise CalendarTransformError("FULL_CALENDAR_WITH_OVERLAY 모드에는 calendar_year가 필요합니다.")
        month = config.get("calendar_month")
        if month is not None and (int(month) < 1 or int(month) > 12):
            raise CalendarTransformError("calendar_month는 1~12 사이여야 합니다.")
    else:
        hour_start = int(config.get("hour_start") or 0)
        hour_end = int(config.get("hour_end") or 23)
        if hour_start < 0 or hour_end > 23 or hour_start > hour_end:
            raise CalendarTransformError("시간 범위(hour_start~hour_end)는 0~23이어야 합니다.")
    warnings.append("Calendar 변환은 공휴일/특일 응답을 날짜 기준정보로 정규화합니다.")
    warnings.append("요일명(day_name)은 한국어(월~일), day_of_week는 1(월)~7(일) 기준입니다.")
    return warnings


async def transform_special_day_items(
    items: list[dict[str, Any]],
    config: dict[str, Any],
    *,
    source_operation_id: str | None = None,
) -> dict[str, Any]:
    source_system = config.get("source_system") or "KASI_SPECIAL_DAY_API"
    calendar_mode = (config.get("calendar_mode") or "FULL_CALENDAR_WITH_OVERLAY").upper()
    store_raw = bool(config.get("store_raw_json", True))
    year = config.get("calendar_year")
    month = config.get("calendar_month")
    warnings: list[str] = []
    skipped = 0
    parsed_special: list[dict[str, Any]] = []

    for idx, item in enumerate(items):
        if not isinstance(item, dict):
            skipped += 1
            warnings.append(f"항목 {idx + 1}: 객체가 아닌 응답은 건너뜁니다.")
            continue
        try:
            parsed_special.append(_special_day_from_item(item, config))
        except CalendarTransformError as exc:
            skipped += 1
            warnings.append(f"항목 {idx + 1}: {exc}")
            continue

    if year is None and parsed_special:
        year = parsed_special[0]["calendar_date"].year
    if year is None:
        raise CalendarTransformError("calendar_year가 없고 특일에서 연도를 추론할 수 없습니다.")

    month_val = int(month) if month is not None else None
    date_rows, merge_warnings = generate_calendar_date_rows(
        int(year),
        month_val,
        parsed_special,
        calendar_mode=calendar_mode,
        source_system=source_system,
        source_operation_id=source_operation_id,
        store_raw=store_raw,
    )
    warnings.extend(merge_warnings)

    diagnostics = {
        "transform_type": "CALENDAR_SPECIAL_DAY_TO_DATE",
        "calendar_mode": calendar_mode,
        "raw_item_count": len(items),
        "transformed_row_count": len(date_rows),
        "date_row_count": len(date_rows),
        "hour_row_count": 0,
        "special_day_count": len(parsed_special),
        "skipped_row_count": skipped,
        "warning_count": len(warnings),
        "warnings": warnings[:50],
        "sample_rows": date_rows[:5],
        "source_system": source_system,
    }
    return {
        "rows": date_rows,
        "warnings": warnings,
        "unmapped_codes": [],
        "diagnostics": diagnostics,
        "blocked": False,
        "block_reason": None,
    }


async def transform_calendar_date_to_hour_items(
    items: list[dict[str, Any]],
    config: dict[str, Any],
    *,
    source_operation_id: str | None = None,
) -> dict[str, Any]:
    source_system = config.get("source_system") or "KASI_SPECIAL_DAY_API"
    store_raw = bool(config.get("store_raw_json", True))
    hour_start = int(config.get("hour_start") or 0)
    hour_end = int(config.get("hour_end") or 23)
    calendar_mode = (config.get("calendar_mode") or "FULL_CALENDAR_WITH_OVERLAY").upper()
    warnings: list[str] = []
    parsed_special: list[dict[str, Any]] = []
    date_rows: list[dict[str, Any]] = []

    for idx, item in enumerate(items):
        if not isinstance(item, dict):
            warnings.append(f"항목 {idx + 1}: 객체가 아닌 응답은 건너뜁니다.")
            continue
        if item.get("calendar_date"):
            date_rows.append(item)
            continue
        try:
            parsed_special.append(_special_day_from_item(item, config))
        except CalendarTransformError as exc:
            warnings.append(f"항목 {idx + 1}: {exc}")

    year = config.get("calendar_year")
    if year is None and parsed_special:
        year = parsed_special[0]["calendar_date"].year
    month_val = int(config["calendar_month"]) if config.get("calendar_month") else None

    if year is not None and (parsed_special or calendar_mode == "FULL_CALENDAR_WITH_OVERLAY"):
        generated, merge_warnings = generate_calendar_date_rows(
            int(year),
            month_val,
            parsed_special,
            calendar_mode=calendar_mode,
            source_system=source_system,
            source_operation_id=source_operation_id,
            store_raw=store_raw,
        )
        warnings.extend(merge_warnings)
        date_rows = generated
    elif parsed_special and not date_rows:
        generated, merge_warnings = generate_calendar_date_rows(
            int(parsed_special[0]["calendar_date"].year),
            month_val,
            parsed_special,
            calendar_mode="SPECIAL_DAYS_ONLY",
            source_system=source_system,
            source_operation_id=source_operation_id,
            store_raw=store_raw,
        )
        warnings.extend(merge_warnings)
        date_rows = generated

    hour_rows = generate_calendar_hour_rows(date_rows, hour_start=hour_start, hour_end=hour_end)
    diagnostics = {
        "transform_type": "CALENDAR_DATE_TO_HOUR",
        "calendar_mode": config.get("calendar_mode") or "FULL_CALENDAR_WITH_OVERLAY",
        "raw_item_count": len(items),
        "transformed_row_count": len(hour_rows),
        "date_row_count": len(date_rows),
        "hour_row_count": len(hour_rows),
        "special_day_count": sum(1 for r in date_rows if r.get("special_day_name")),
        "skipped_row_count": max(0, len(items) - len(date_rows)),
        "warning_count": len(warnings),
        "warnings": warnings[:50],
        "sample_rows": hour_rows[:5],
        "source_system": source_system,
    }
    return {
        "rows": hour_rows,
        "warnings": warnings,
        "unmapped_codes": [],
        "diagnostics": diagnostics,
        "blocked": False,
        "block_reason": None,
    }


async def preview_special_day_transform(
    db,
    *,
    operation_id: str,
    raw_items: list[dict[str, Any]],
    config: dict[str, Any],
    target_table: str | None,
) -> dict[str, Any]:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.services.api_connector_loader import get_physical_columns
    from app.services.standard_dataset_service import validate_target_table_allowed

    if target_table:
        await validate_target_table_allowed(db, target_table)
    result = await transform_special_day_items(raw_items, config, source_operation_id=operation_id)
    column_info: dict[str, Any] = {}
    if target_table and result["rows"]:
        physical = await get_physical_columns(db, target_table)
        column_info = {"target_table": target_table, "target_columns": physical}
    return {
        "operation_id": operation_id,
        "target_table": target_table,
        "raw_item_count": len(raw_items),
        "transformed_row_count": len(result["rows"]),
        "sample_rows": result["rows"][:10],
        "unmapped_codes": [],
        "warnings": result["warnings"],
        "transform_summary": result["diagnostics"],
        "blocked": False,
        "block_reason": None,
        **column_info,
    }


async def preview_calendar_hour_transform(
    db: AsyncSession,
    *,
    operation_id: str,
    raw_items: list[dict[str, Any]],
    config: dict[str, Any],
    target_table: str | None,
) -> dict[str, Any]:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.services.api_connector_loader import get_physical_columns
    from app.services.standard_dataset_service import validate_target_table_allowed

    if target_table:
        await validate_target_table_allowed(db, target_table)
    result = await transform_calendar_date_to_hour_items(
        raw_items, config, source_operation_id=operation_id
    )
    column_info: dict[str, Any] = {}
    if target_table and result["rows"]:
        physical = await get_physical_columns(db, target_table)
        column_info = {"target_table": target_table, "target_columns": physical}
    return {
        "operation_id": operation_id,
        "target_table": target_table,
        "raw_item_count": len(raw_items),
        "transformed_row_count": len(result["rows"]),
        "sample_rows": result["rows"][:10],
        "unmapped_codes": [],
        "warnings": result["warnings"],
        "transform_summary": result["diagnostics"],
        "blocked": False,
        "block_reason": None,
        **column_info,
    }
