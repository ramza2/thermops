"""Data mapping transform and validation."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from app.models.entities import DataMapping, DataSource

HEAT_TARGET = "heat_demand_actual"
WEATHER_TARGET = "weather_observation"

HEAT_REQUIRED = {"site_id", "measured_at", "heat_demand"}
WEATHER_REQUIRED = {"weather_area_id", "measured_at"}
WEATHER_NUMERIC = {"temperature", "humidity", "rainfall", "wind_speed", "apparent_temp"}

DATETIME_FORMATS = (
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%dT%H:%M:%S%z",
    "%Y-%m-%d %H:%M",
    "%Y/%m/%d %H:%M:%S",
)


def _target_columns(mapping: DataMapping) -> list[dict[str, Any]]:
    return mapping.columns or []


def _target_table_key(mapping: DataMapping) -> str:
    table = (mapping.target_table or "").lower().replace("tb_", "")
    return table


def apply_mapping(raw_rows: list[dict[str, str]], mapping: DataMapping) -> list[dict[str, Any]]:
    rules = _target_columns(mapping)
    if not rules:
        raise ValueError("매핑 컬럼 정의가 없습니다.")

    mapped: list[dict[str, Any]] = []
    for raw in raw_rows:
        row: dict[str, Any] = {}
        for rule in rules:
            src = rule.get("source_column")
            tgt = rule.get("target_column")
            if not src or not tgt:
                continue
            row[tgt] = raw.get(src)
            if row[tgt] is not None and isinstance(row[tgt], str):
                row[tgt] = row[tgt].strip()
        mapped.append(row)
    return mapped


def _parse_datetime(value: Any) -> datetime | None:
    if value is None or value == "":
        return None
    text = str(value).strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        pass
    for fmt in DATETIME_FORMATS:
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


def _parse_decimal(value: Any) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        return Decimal(str(value).strip().replace(",", ""))
    except (InvalidOperation, ValueError):
        return None


def validate_mapping_rules(mapping: DataMapping, source: DataSource | None = None) -> dict[str, Any]:
    rules = _target_columns(mapping)
    errors: list[str] = []
    warnings: list[str] = []

    target_cols = [r.get("target_column") for r in rules if r.get("target_column")]
    if len(target_cols) != len(set(target_cols)):
        errors.append("중복된 표준 컬럼(target_column) 매핑이 있습니다.")

    table = _target_table_key(mapping)
    required = HEAT_REQUIRED if table == HEAT_TARGET else WEATHER_REQUIRED if table == WEATHER_TARGET else set()
    mapped_targets = set(target_cols)
    for col in required:
        if col not in mapped_targets:
            errors.append(f"필수 표준 컬럼 '{col}' 매핑이 없습니다.")

    for rule in rules:
        if rule.get("required_yn") and not rule.get("source_column"):
            errors.append(f"필수 컬럼 {rule.get('target_column')}의 source_column이 비어 있습니다.")

    if source:
        try:
            from app.services.connectors.registry import get_connector

            connector = get_connector(source)
            raw_rows, _ = connector.fetch_rows(source, mapping=mapping, limit=20)
            if not raw_rows:
                warnings.append("소스에서 데이터 행이 없습니다.")
            else:
                preview = raw_rows[:20]
                date_col = "measured_at"
                for i, row in enumerate(preview[:5], start=1):
                    if date_col in row and _parse_datetime(row[date_col]) is None:
                        errors.append(f"{i}행 measured_at 날짜 파싱 불가: {row.get(date_col)}")
                numeric_cols = {"heat_demand"} if table == HEAT_TARGET else WEATHER_NUMERIC
                for col in numeric_cols:
                    if col in mapped_targets:
                        for i, row in enumerate(preview[:5], start=1):
                            val = row.get(col)
                            if val not in (None, "") and _parse_decimal(val) is None:
                                errors.append(f"{i}행 {col} 숫자 변환 불가: {val}")
        except Exception as exc:
            errors.append(f"소스 읽기 실패: {exc}")

    if table == HEAT_TARGET and "supply_temp" not in mapped_targets:
        warnings.append("선택 컬럼 supply_temp가 매핑되지 않았습니다.")
    if table == WEATHER_TARGET and "data_type" not in mapped_targets:
        warnings.append("data_type 미매핑 — 적재 시 'OBSERVATION' 기본값을 사용합니다.")

    return {
        "mapping_id": mapping.mapping_id,
        "valid": len(errors) == 0,
        "warnings": warnings,
        "errors": errors,
    }


def preview_mapping_data(
    source: DataSource,
    mapping: DataMapping,
    limit: int = 10,
    start_at: datetime | None = None,
    end_at: datetime | None = None,
) -> list[dict[str, Any]]:
    from app.services.connectors.registry import get_connector

    connector = get_connector(source)
    result = connector.preview(
        source,
        mapping=mapping,
        limit=limit,
        start_at=start_at,
        end_at=end_at,
    )
    rows = result.get("rows") or []
    table = _target_table_key(mapping)
    output: list[dict[str, Any]] = []
    for row in rows:
        out: dict[str, Any] = {}
        for k, v in row.items():
            if k == "measured_at":
                dt = _parse_datetime(v)
                out[k] = dt.isoformat() if dt else v
            elif k in {"heat_demand", "supply_temp", "return_temp", "flow_rate", *WEATHER_NUMERIC}:
                num = _parse_decimal(v)
                out[k] = float(num) if num is not None else v
            else:
                out[k] = v
        if table == WEATHER_TARGET and not out.get("data_type"):
            out["data_type"] = "OBSERVATION"
        output.append(out)
    return output


def normalize_row_for_insert(row: dict[str, Any], mapping: DataMapping) -> dict[str, Any] | None:
    table = _target_table_key(mapping)
    measured = _parse_datetime(row.get("measured_at"))
    if measured is None:
        return None

    if table == HEAT_TARGET:
        heat = _parse_decimal(row.get("heat_demand"))
        if heat is None or not row.get("site_id"):
            return None
        out: dict[str, Any] = {
            "site_id": str(row["site_id"]).strip(),
            "measured_at": measured,
            "heat_demand": float(heat),
        }
        for opt in ("supply_temp", "return_temp", "flow_rate"):
            if row.get(opt) not in (None, ""):
                num = _parse_decimal(row[opt])
                if num is not None:
                    out[opt] = float(num)
        return out

    if table == WEATHER_TARGET:
        if not row.get("weather_area_id"):
            return None
        out = {
            "weather_area_id": str(row["weather_area_id"]).strip(),
            "measured_at": measured,
            "data_type": str(row.get("data_type") or "OBSERVATION").strip(),
        }
        for col in WEATHER_NUMERIC:
            if row.get(col) not in (None, ""):
                num = _parse_decimal(row[col])
                if num is not None:
                    out[col] = float(num)
        return out

    raise ValueError(f"지원하지 않는 target_table: {mapping.target_table}")
