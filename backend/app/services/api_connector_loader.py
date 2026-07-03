"""API Connector 기본 적재 — std_ 물리 테이블 INSERT."""

from __future__ import annotations

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


async def get_physical_columns(db: AsyncSession, physical_table: str) -> list[str]:
    schema = "public"
    table = physical_table
    if "." in physical_table:
        schema, table = physical_table.split(".", 1)
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
    physical = resolve_physical_table_name(target_table)
    cols = await get_physical_columns(db, physical)
    if not cols:
        raise TargetTableNotAllowedError(
            f"적재 대상 테이블 컬럼을 찾을 수 없습니다: {target_table}",
            allowed_tables=[],
        )

    str_rows = [{k: "" if v is None else str(v) for k, v in row.items()} for row in items[:max_rows]]
    if mapping and mapping.columns:
        rows = apply_mapping(str_rows, mapping)
    else:
        rows = []
        for raw in str_rows:
            row = {c: raw.get(c) for c in cols if c in raw and raw.get(c) not in (None, "")}
            if row:
                rows.append(row)

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
