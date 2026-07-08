"""API Connector 기본 적재 — std_ 물리 테이블 INSERT."""

from __future__ import annotations

import json
from datetime import date, datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entities import DataMapping
from app.services.mapping_service import apply_mapping
from app.services.standard_dataset_service import (
    TargetTableNotAllowedError,
    resolve_physical_table_name,
    validate_target_table_allowed,
)


def _table_parts(physical_table: str) -> tuple[str, str]:
    schema = "public"
    table = physical_table
    if "." in physical_table:
        schema, table = physical_table.split(".", 1)
    return schema, table


async def get_physical_columns(db: AsyncSession, physical_table: str) -> list[str]:
    schema, table = _table_parts(physical_table)
    rows = (
        await db.execute(
            text(
                """
                SELECT column_name FROM information_schema.columns
                WHERE table_schema = :schema AND table_name = :table
                ORDER BY ordinal_position
                """
            ),
            {"schema": schema, "table": table},
        )
    ).all()
    return [r[0] for r in rows]


async def get_physical_column_types(db: AsyncSession, physical_table: str) -> dict[str, str]:
    schema, table = _table_parts(physical_table)
    rows = (
        await db.execute(
            text(
                """
                SELECT column_name, data_type
                FROM information_schema.columns
                WHERE table_schema = :schema AND table_name = :table
                ORDER BY ordinal_position
                """
            ),
            {"schema": schema, "table": table},
        )
    ).all()
    return {r[0]: r[1] for r in rows}


def coerce_value_for_column(value: Any, data_type: str) -> Any:
    if value is None or value == "":
        return value
    dt = (data_type or "").lower()
    if "timestamp" in dt:
        if isinstance(value, datetime):
            return value.replace(tzinfo=None) if value.tzinfo else value
        if isinstance(value, str):
            text_val = value.strip()
            if text_val.endswith("Z"):
                text_val = text_val[:-1] + "+00:00"
            parsed = datetime.fromisoformat(text_val)
            return parsed.replace(tzinfo=None) if parsed.tzinfo else parsed
    if dt == "date":
        if isinstance(value, date) and not isinstance(value, datetime):
            return value
        if isinstance(value, str):
            return date.fromisoformat(value[:10])
    if dt in ("integer", "bigint", "smallint"):
        if isinstance(value, int):
            return value
        if isinstance(value, str) and value.strip().lstrip("-").isdigit():
            return int(value)
    if any(token in dt for token in ("numeric", "decimal", "double precision", "real")):
        if isinstance(value, (int, float)):
            return value
        if isinstance(value, str):
            return float(value.replace(",", ""))
    if "json" in dt and isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return value


def _normalize_row_values(row: dict[str, Any], col_types: dict[str, str]) -> dict[str, Any]:
    normalized: dict[str, Any] = {}
    for col, value in row.items():
        if value == "":
            continue
        if value is None:
            normalized[col] = None
            continue
        normalized[col] = coerce_value_for_column(value, col_types.get(col, ""))
    return normalized


async def preview_load_rows(
    db: AsyncSession,
    *,
    target_table: str,
    items: list[dict[str, Any]],
    mapping: DataMapping | None,
    limit: int = 10,
) -> dict[str, Any]:
    await validate_target_table_allowed(db, target_table)
    str_rows = [{k: "" if v is None else str(v) for k, v in row.items()} for row in items[:limit]]
    if mapping and mapping.columns:
        mapped = apply_mapping(str_rows, mapping)
    else:
        physical = resolve_physical_table_name(target_table)
        cols = await get_physical_columns(db, physical)
        mapped = []
        for raw in str_rows:
            row = {c: raw.get(c) for c in cols if c in raw}
            if row:
                mapped.append(row)
    return {
        "target_table": target_table,
        "preview_rows": mapped[:limit],
        "item_count": len(items),
        "preview_count": len(mapped[:limit]),
        "mapping_applied": bool(mapping and mapping.columns),
    }


async def insert_rows(
    db: AsyncSession,
    *,
    target_table: str,
    items: list[dict[str, Any]],
    mapping: DataMapping | None,
    max_rows: int = 1000,
) -> dict[str, int]:
    await validate_target_table_allowed(db, target_table)
    physical, cols, _, rows = await prepare_rows_for_target(
        db,
        target_table=target_table,
        items=items,
        mapping=mapping,
        max_rows=max_rows,
    )

    inserted = 0
    skipped = 0
    errors = 0
    for row in rows:
        insert_cols = [c for c in cols if c in row]
        if not insert_cols:
            skipped += 1
            continue
        placeholders = ", ".join(f":{c}" for c in insert_cols)
        col_list = ", ".join(f'"{c}"' for c in insert_cols)
        sql = f'INSERT INTO "{physical}" ({col_list}) VALUES ({placeholders})'
        try:
            await db.execute(text(sql), {c: row[c] for c in insert_cols})
            inserted += 1
        except Exception:
            errors += 1
    return {"inserted_count": inserted, "skipped_count": skipped, "error_count": errors}


async def prepare_rows_for_target(
    db: AsyncSession,
    *,
    target_table: str,
    items: list[dict[str, Any]],
    mapping: DataMapping | None,
    max_rows: int = 1000,
) -> tuple[str, list[str], dict[str, str], list[dict[str, Any]]]:
    await validate_target_table_allowed(db, target_table)
    physical = resolve_physical_table_name(target_table)
    cols = await get_physical_columns(db, physical)
    if not cols:
        raise TargetTableNotAllowedError(
            f"적재 대상 테이블 컬럼을 찾을 수 없습니다: {target_table}",
            allowed_tables=[],
        )
    col_types = await get_physical_column_types(db, physical)
    if mapping and mapping.columns:
        mapped_inputs = [{k: (None if v is None else str(v)) for k, v in row.items()} for row in items[:max_rows]]
        rows = apply_mapping(mapped_inputs, mapping)
        rows = [_normalize_row_values(row, col_types) for row in rows]
    else:
        rows = []
        for raw in items[:max_rows]:
            row = {c: raw.get(c) for c in cols if c in raw and raw.get(c) != ""}
            if row:
                rows.append(_normalize_row_values(row, col_types))
    return physical, cols, col_types, rows
