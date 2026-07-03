"""Managed physical table DDL generation and execution (R9-S2-1)."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.time import utc_now
from app.models.entities import StandardDatasetColumn, StandardDatasetTableCreateLog, StandardDatasetType
from app.utils.sql_identifier import (
    ALLOWED_SCHEMA,
    quote_ident,
    render_postgres_type,
    suggest_physical_table_name,
    validate_column_definition,
    validate_column_identifier,
    validate_schema_name,
    validate_table_identifier,
)


class PhysicalTableValidationError(ValueError):
    def __init__(self, errors: list[dict[str, str]], warnings: list[dict[str, str]] | None = None) -> None:
        self.errors = errors
        self.warnings = warnings or []
        super().__init__(errors[0]["message"] if errors else "validation failed")


def _warning(code: str, message: str) -> dict[str, str]:
    return {"code": code, "message": message}


def column_dict_from_row(row: StandardDatasetColumn) -> dict[str, Any]:
    return {
        "column_id": row.column_id,
        "column_name": row.column_name,
        "display_name": row.display_name,
        "data_type": row.data_type,
        "data_length": row.data_length,
        "numeric_precision": row.numeric_precision,
        "numeric_scale": row.numeric_scale,
        "nullable": (row.nullable_yn or "Y").upper() == "Y",
        "required": (row.required_yn or "N").upper() == "Y",
        "primary_key": (row.primary_key_yn or "N").upper() == "Y",
        "unique": (getattr(row, "unique_yn", "N") or "N").upper() == "Y",
        "default_column_role": row.default_column_role,
        "sort_order": row.sort_order,
        "description": row.description,
    }


async def table_exists(db: AsyncSession, schema: str, table_name: str) -> bool:
    result = await db.execute(
        text(
            "SELECT 1 FROM information_schema.tables "
            "WHERE table_schema = :schema AND table_name = :name LIMIT 1"
        ),
        {"schema": schema, "name": table_name},
    )
    return result.scalar() is not None


def validate_dataset_columns(columns: list[dict[str, Any]]) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    errors: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []
    if not columns:
        errors.append({"code": "NO_COLUMNS", "message": "최소 1개 이상의 컬럼 정의가 필요합니다."})
        return errors, warnings

    seen: set[str] = set()
    pk_cols: list[str] = []
    for col in columns:
        name = str(col.get("column_name") or "").strip().lower()
        if name in seen:
            errors.append({"code": "DUPLICATE_COLUMN_NAME", "message": f"중복 컬럼명: {name}"})
        seen.add(name)
        errors.extend(validate_column_definition(col))
        if col.get("primary_key"):
            pk_cols.append(name)

    if not pk_cols:
        warnings.append(_warning("NO_PRIMARY_KEY", "Primary Key가 없어도 생성은 가능하지만 증분 적재/UPSERT에는 제약이 있습니다."))
    return errors, warnings


async def validate_managed_dataset_definition(
    db: AsyncSession,
    *,
    target_table: str,
    schema: str = ALLOWED_SCHEMA,
    columns: list[dict[str, Any]],
    managed: bool = True,
) -> dict[str, Any]:
    errors: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []

    errors.extend(validate_schema_name(schema))
    errors.extend(validate_table_identifier(target_table, require_managed_prefix=managed))
    col_errors, col_warnings = validate_dataset_columns(columns)
    errors.extend(col_errors)
    warnings.extend(col_warnings)

    physical_name = target_table.strip().lower()
    if not errors and await table_exists(db, schema, physical_name):
        errors.append({
            "code": "TABLE_ALREADY_EXISTS",
            "message": f"물리 테이블 '{schema}.{physical_name}'이(가) 이미 존재합니다.",
        })

    return {
        "valid": not errors,
        "errors": errors,
        "warnings": warnings,
        "physical_table_name": physical_name,
        "physical_table_schema": schema,
    }


def generate_create_table_sql(
    *,
    schema: str,
    table_name: str,
    columns: list[dict[str, Any]],
) -> str:
    schema_q = quote_ident(schema)
    table_q = quote_ident(table_name)
    lines: list[str] = []
    pk_cols: list[str] = []
    unique_cols: list[str] = []

    for col in sorted(columns, key=lambda c: (c.get("sort_order") or 0, c.get("column_name") or "")):
        col_name = str(col["column_name"]).strip().lower()
        for err in validate_column_identifier(col_name):
            raise PhysicalTableValidationError([err])
        pg_type = render_postgres_type(col)
        nullable = col.get("nullable", True)
        if col.get("required") or col.get("primary_key"):
            nullable = False
        null_sql = "" if nullable else " NOT NULL"
        lines.append(f"  {quote_ident(col_name)} {pg_type}{null_sql}")
        if col.get("primary_key"):
            pk_cols.append(col_name)
        if col.get("unique") and not col.get("primary_key"):
            unique_cols.append(col_name)

    constraint_lines: list[str] = []
    if pk_cols:
        pk_list = ", ".join(quote_ident(c) for c in pk_cols)
        constraint_lines.append(f"  PRIMARY KEY ({pk_list})")
    for ucol in unique_cols:
        constraint_lines.append(f"  UNIQUE ({quote_ident(ucol)})")

    body = ",\n".join(lines + constraint_lines)
    return f"CREATE TABLE {schema_q}.{table_q} (\n{body}\n);"


async def append_create_log(
    db: AsyncSession,
    *,
    dataset_type_id: str,
    action_type: str,
    status: str,
    sql_preview: str | None = None,
    error_message: str | None = None,
    created_by: str | None = None,
) -> None:
    db.add(StandardDatasetTableCreateLog(
        log_id=f"SDTLOG-{uuid4().hex[:8].upper()}",
        dataset_type_id=dataset_type_id,
        action_type=action_type,
        status=status,
        sql_preview=sql_preview,
        error_message=error_message,
        created_by=created_by,
        created_at=utc_now(),
    ))


async def preview_managed_physical_table(
    db: AsyncSession,
    row: StandardDatasetType,
    columns: list[dict[str, Any]],
) -> dict[str, Any]:
    if row.status == "ARCHIVED":
        raise ValueError("ARCHIVED 데이터셋은 물리 테이블을 생성할 수 없습니다.")
    if (row.physical_table_exists_yn or "N").upper() == "Y" and (row.table_create_status or "") == "SUCCESS":
        raise ValueError("이미 물리 테이블이 생성된 데이터셋입니다.")

    managed = (row.managed_table_yn or "N").upper() == "Y"
    schema = (row.physical_table_schema or ALLOWED_SCHEMA).lower()
    validation = await validate_managed_dataset_definition(
        db,
        target_table=row.target_table,
        schema=schema,
        columns=columns,
        managed=managed,
    )
    if not validation["valid"]:
        return {
            **validation,
            "sql_preview": None,
        }

    sql_preview = generate_create_table_sql(
        schema=schema,
        table_name=validation["physical_table_name"],
        columns=columns,
    )
    row.table_create_status = "PREVIEWED"
    row.table_create_sql_preview = sql_preview
    row.table_create_error = None
    row.updated_at = utc_now()
    await append_create_log(
        db,
        dataset_type_id=row.dataset_type_id,
        action_type="PREVIEW",
        status="SUCCESS",
        sql_preview=sql_preview,
    )
    await db.flush()
    return {
        **validation,
        "sql_preview": sql_preview,
    }


async def create_managed_physical_table(
    db: AsyncSession,
    row: StandardDatasetType,
    columns: list[dict[str, Any]],
    *,
    requested_by: str | None = None,
) -> dict[str, Any]:
    if row.status == "ARCHIVED":
        raise ValueError("ARCHIVED 데이터셋은 물리 테이블을 생성할 수 없습니다.")
    if (row.table_create_status or "") == "SUCCESS" and (row.physical_table_exists_yn or "N").upper() == "Y":
        raise ValueError("이미 물리 테이블이 생성된 데이터셋입니다.")

    managed = (row.managed_table_yn or "N").upper() == "Y"
    schema = (row.physical_table_schema or ALLOWED_SCHEMA).lower()
    validation = await validate_managed_dataset_definition(
        db,
        target_table=row.target_table,
        schema=schema,
        columns=columns,
        managed=managed,
    )
    if not validation["valid"]:
        raise PhysicalTableValidationError(validation["errors"], validation.get("warnings") or [])

    sql_preview = generate_create_table_sql(
        schema=schema,
        table_name=validation["physical_table_name"],
        columns=columns,
    )

    try:
        await db.execute(text(sql_preview))
    except Exception as exc:
        row.table_create_status = "FAILED"
        row.table_create_error = str(exc)
        row.updated_at = utc_now()
        await append_create_log(
            db,
            dataset_type_id=row.dataset_type_id,
            action_type="CREATE_TABLE",
            status="FAILED",
            sql_preview=sql_preview,
            error_message=str(exc),
            created_by=requested_by,
        )
        await db.flush()
        raise ValueError(f"CREATE TABLE 실패: {exc}") from exc

    row.physical_table_exists_yn = "Y"
    row.table_create_status = "SUCCESS"
    row.table_create_sql_preview = sql_preview
    row.table_create_error = None
    row.physical_table_created_at = utc_now()
    row.physical_table_created_by = requested_by
    row.status = "ACTIVE"
    row.mapping_supported_yn = "Y"
    row.updated_at = utc_now()

    await append_create_log(
        db,
        dataset_type_id=row.dataset_type_id,
        action_type="CREATE_TABLE",
        status="SUCCESS",
        sql_preview=sql_preview,
        created_by=requested_by,
    )
    await db.flush()

    return {
        "status": "SUCCESS",
        "physical_table_name": validation["physical_table_name"],
        "physical_table_schema": schema,
        "physical_table_exists_yn": "Y",
        "lifecycle_status": "ACTIVE",
        "sql_preview": sql_preview,
        "warnings": validation.get("warnings") or [],
    }


__all__ = [
    "PhysicalTableValidationError",
    "column_dict_from_row",
    "create_managed_physical_table",
    "generate_create_table_sql",
    "preview_managed_physical_table",
    "suggest_physical_table_name",
    "table_exists",
    "validate_managed_dataset_definition",
]
