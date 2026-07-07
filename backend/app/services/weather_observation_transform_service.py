"""ASOS 관측 기상 → 표준 기상 행 변환 (R10-S4)."""

from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entities import WeatherObservationStation
from app.services.external_code_mapping_service import resolve_or_log_unmapped

DEFAULT_ASOS_FIELD_MAPPINGS: dict[str, str] = {
    "station_code": "stnId",
    "observed_at": "tm",
    "temperature": "ta",
    "humidity": "hm",
    "wind_speed": "ws",
    "precipitation": "rn",
    "pressure": "pa",
    "sunshine_duration": "ss",
    "solar_radiation": "icsr",
}

CANONICAL_WEATHER_COLUMNS = frozenset(
    {
        "station_code",
        "observed_at",
        "temperature",
        "humidity",
        "wind_speed",
        "precipitation",
        "pressure",
        "sunshine_duration",
        "solar_radiation",
        "weather_condition",
        "source_system",
        "source_operation_id",
        "raw_json",
        "created_at",
    }
)

STATION_UNMAPPED_POLICIES = frozenset({"WARN_ONLY", "LOG_UNMAPPED", "FAIL_LOAD"})
DATE_PARSE_POLICIES = frozenset({"WARN_SKIP", "FAIL_ROW", "FAIL_LOAD"})


class WeatherObservationTransformError(ValueError):
    def __init__(self, message: str, *, error_code: str = "WEATHER_TRANSFORM_ERROR"):
        self.error_code = error_code
        super().__init__(message)


def _item_field(item: dict[str, Any], field: str) -> Any:
    if field in item:
        return item[field]
    return None


def _field_mappings(config: dict[str, Any]) -> dict[str, str]:
    raw = config.get("value_field_mappings_json")
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError:
            raw = None
    if isinstance(raw, dict) and raw:
        merged = {**DEFAULT_ASOS_FIELD_MAPPINGS, **raw}
    else:
        merged = dict(DEFAULT_ASOS_FIELD_MAPPINGS)
    merged["station_code"] = config.get("station_code_field") or merged.get("station_code") or "stnId"
    merged["observed_at"] = config.get("observed_at_field") or merged.get("observed_at") or "tm"
    return merged


def normalize_weather_value(value: Any, *, numeric_parse_policy: str = "ALLOW_COMMA") -> tuple[float | None, str | None]:
    if value is None:
        return None, None
    text = str(value).strip()
    if text == "":
        return None, None
    if numeric_parse_policy == "ALLOW_COMMA":
        text = text.replace(",", "")
    try:
        return float(text), None
    except ValueError:
        return None, "invalid_numeric"


def parse_observed_at(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value.replace(tzinfo=None)
    text = str(value).strip()
    if not text:
        raise WeatherObservationTransformError("관측 시각(observed_at)이 비어 있습니다.")
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    if "T" in text or "+" in text[-6:] or text.count("-") >= 2:
        try:
            return datetime.fromisoformat(text.replace("Z", "+00:00")).replace(tzinfo=None)
        except ValueError:
            pass
    if re.fullmatch(r"\d{12}", text):
        return datetime(int(text[0:4]), int(text[4:6]), int(text[6:8]), int(text[8:10]), int(text[10:12]))
    if re.fullmatch(r"\d{10}", text):
        return datetime(int(text[0:4]), int(text[4:6]), int(text[6:8]), int(text[8:10]), 0)
    if re.fullmatch(r"\d{8}", text):
        return datetime(int(text[0:4]), int(text[4:6]), int(text[6:8]), 0, 0)
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y/%m/%d %H:%M:%S", "%Y/%m/%d %H:%M"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    raise WeatherObservationTransformError(f"관측 시각을 해석할 수 없습니다: {value}")


async def _load_known_station_codes(db: AsyncSession) -> set[str]:
    rows = (
        await db.execute(
            select(WeatherObservationStation.station_code).where(WeatherObservationStation.active_yn.is_(True))
        )
    ).scalars().all()
    return {str(code).strip() for code in rows if code}


def validate_asos_transform_config(config: dict[str, Any]) -> list[str]:
    warnings: list[str] = []
    policy = (config.get("station_unmapped_policy") or "WARN_ONLY").upper()
    if policy not in STATION_UNMAPPED_POLICIES:
        raise WeatherObservationTransformError("미등록 관측소 처리 방식이 올바르지 않습니다.")
    if policy == "LOG_UNMAPPED":
        warnings.append("LOG_UNMAPPED 정책은 미등록 관측소 코드를 미매핑 목록에 기록합니다.")
    warnings.append(
        "ASOS 관측 기상은 과거 학습용 기상 데이터입니다. 예측 시점의 미래 기상은 후속 Forecast on-demand 단계에서 처리합니다."
    )
    return warnings


async def transform_asos_hourly_items(
    db: AsyncSession,
    items: list[dict[str, Any]],
    config: dict[str, Any],
    *,
    source_operation_id: str | None = None,
    for_load: bool = False,
) -> dict[str, Any]:
    mappings = _field_mappings(config)
    numeric_policy = config.get("numeric_parse_policy") or "ALLOW_COMMA"
    station_policy = (config.get("station_unmapped_policy") or "WARN_ONLY").upper()
    date_parse_policy = (config.get("metadata_json") or {}).get("date_parse_policy") or "WARN_SKIP"
    if date_parse_policy not in DATE_PARSE_POLICIES:
        date_parse_policy = "WARN_SKIP"
    source_system = config.get("source_system") or "KMA_ASOS_API"
    store_raw = bool(config.get("store_raw_json", True))

    known_stations = await _load_known_station_codes(db)
    rows: list[dict[str, Any]] = []
    warnings: list[str] = []
    unmapped_codes: list[dict[str, Any]] = []
    skipped = 0
    blocked = False
    block_reason: str | None = None

    numeric_targets = {
        k: v
        for k, v in mappings.items()
        if k
        not in (
            "station_code",
            "observed_at",
            "weather_condition",
        )
    }

    for idx, item in enumerate(items):
        if not isinstance(item, dict):
            skipped += 1
            warnings.append(f"항목 {idx + 1}: 객체가 아닌 응답은 건너뜁니다.")
            continue
        station_raw = _item_field(item, mappings["station_code"])
        if station_raw is None or str(station_raw).strip() == "":
            skipped += 1
            warnings.append(f"항목 {idx + 1}: station_code가 없어 건너뜁니다.")
            continue
        station_code = str(station_raw).strip()

        if known_stations and station_code not in known_stations:
            msg = f"미등록 ASOS 관측소 코드: {station_code}"
            if station_policy == "FAIL_LOAD":
                blocked = True
                block_reason = msg
                if for_load:
                    break
                warnings.append(msg)
            elif station_policy == "LOG_UNMAPPED":
                logged = await resolve_or_log_unmapped(
                    db,
                    source_system=source_system,
                    external_code_group="STATION",
                    external_code=station_code,
                    source_operation_id=source_operation_id,
                    sample_payload_json=item,
                )
                unmapped_codes.append(
                    {
                        "field": mappings["station_code"],
                        "external_code": station_code,
                        "unmapped_id": logged.get("unmapped_id"),
                        "resolved": logged.get("resolved"),
                    }
                )
                warnings.append(msg)
            else:
                warnings.append(msg)

        try:
            observed_at = parse_observed_at(_item_field(item, mappings["observed_at"]))
        except WeatherObservationTransformError as exc:
            if date_parse_policy == "FAIL_LOAD":
                blocked = True
                block_reason = str(exc)
                if for_load:
                    break
            if date_parse_policy in ("FAIL_ROW", "FAIL_LOAD"):
                skipped += 1
                warnings.append(f"항목 {idx + 1}: {exc}")
                continue
            skipped += 1
            warnings.append(f"항목 {idx + 1}: {exc}")
            continue

        row: dict[str, Any] = {
            "station_code": station_code,
            "observed_at": observed_at.isoformat(),
            "source_system": source_system,
            "source_operation_id": source_operation_id,
        }
        if store_raw:
            row["raw_json"] = item

        for canonical, source_field in numeric_targets.items():
            if canonical in ("station_code", "observed_at"):
                continue
            raw_val = _item_field(item, source_field) if source_field else None
            if raw_val is None:
                row[canonical] = None
                continue
            if canonical == "weather_condition":
                row[canonical] = str(raw_val) if raw_val is not None else None
                continue
            num_val, err = normalize_weather_value(raw_val, numeric_parse_policy=numeric_policy)
            if err:
                warnings.append(f"항목 {idx + 1}: {canonical} 숫자 변환 실패 ({raw_val}) → NULL")
            row[canonical] = num_val

        rows.append(row)

    diagnostics = {
        "transform_type": "ASOS_HOURLY_TO_CANONICAL",
        "raw_item_count": len(items),
        "transformed_row_count": len(rows),
        "skipped_row_count": skipped,
        "warning_count": len(warnings),
        "warnings": warnings[:50],
        "sample_rows": rows[:5],
        "source_system": source_system,
    }
    return {
        "rows": rows,
        "warnings": warnings,
        "unmapped_codes": unmapped_codes,
        "diagnostics": diagnostics,
        "blocked": blocked,
        "block_reason": block_reason,
    }


async def preview_asos_hourly_transform(
    db: AsyncSession,
    *,
    operation_id: str,
    raw_items: list[dict[str, Any]],
    config: dict[str, Any],
    target_table: str | None,
) -> dict[str, Any]:
    from app.services.api_connector_loader import get_physical_columns
    from app.services.standard_dataset_service import validate_target_table_allowed

    if target_table:
        await validate_target_table_allowed(db, target_table)
    result = await transform_asos_hourly_items(
        db, raw_items, config, source_operation_id=operation_id, for_load=False
    )
    sample_rows = result["rows"][:10]
    column_info: dict[str, Any] = {}
    if target_table and result["rows"]:
        physical = await get_physical_columns(db, target_table)
        column_info = {
            "target_table": target_table,
            "target_columns": physical,
            "canonical_columns": sorted(CANONICAL_WEATHER_COLUMNS),
        }
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


async def apply_weather_transform_if_configured(
    db: AsyncSession,
    operation_id: str,
    raw_items: list[dict[str, Any]],
    config: dict[str, Any],
    *,
    for_load: bool = False,
) -> dict[str, Any]:
    result = await transform_asos_hourly_items(
        db, raw_items, config, source_operation_id=operation_id, for_load=for_load
    )
    if for_load and result.get("blocked"):
        raise WeatherObservationTransformError(
            result.get("block_reason") or "ASOS 관측 기상 변환 중단",
            error_code="UNMAPPED_STATION_CODE",
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
