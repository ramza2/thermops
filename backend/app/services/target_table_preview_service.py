"""Read-only target table sample rows preview (R11-S8-9-14 / B18).

SELECT-only. No DDL/DML. Table names must pass identifier checks and
be registered on a non-archived StandardDatasetType.
"""

from __future__ import annotations

from datetime import date, datetime, time
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.time import utc_now
from app.models.entities import StandardDatasetType
from app.services.standard_dataset_service import (
    check_physical_table_exists,
    resolve_physical_table_name,
    _target_table_match_clause,
)
from app.utils.sql_identifier import (
    ALLOWED_SCHEMA,
    TABLE_NAME_RE,
    normalize_physical_table_name,
    quote_ident,
)

DEFAULT_PREVIEW_LIMIT = 20
MAX_PREVIEW_LIMIT = 100


class TargetTablePreviewError(Exception):
    def __init__(self, status_code: int, message: str, *, code: str = "PREVIEW_ERROR") -> None:
        self.status_code = status_code
        self.message = message
        self.code = code
        super().__init__(message)


def _clamp_limit(limit: int | None) -> int:
    if limit is None:
        return DEFAULT_PREVIEW_LIMIT
    try:
        value = int(limit)
    except (TypeError, ValueError) as exc:
        raise TargetTablePreviewError(400, "limit은 정수여야 합니다.", code="INVALID_LIMIT") from exc
    if value < 1:
        raise TargetTablePreviewError(400, "limit은 1 이상이어야 합니다.", code="INVALID_LIMIT")
    return min(value, MAX_PREVIEW_LIMIT)


def _validate_table_name(raw: str | None) -> str:
    name = normalize_physical_table_name(raw or "")
    if not name:
        raise TargetTablePreviewError(400, "target_table을 입력하세요.", code="TARGET_TABLE_MISSING")
    if not TABLE_NAME_RE.match(name):
        raise TargetTablePreviewError(
            400,
            "테이블명은 소문자 영문으로 시작하고 3~63자의 영문/숫자/underscore만 허용됩니다.",
            code="INVALID_TABLE_NAME",
        )
    if ";" in name or " " in name or "--" in name or "/*" in name:
        raise TargetTablePreviewError(400, "허용되지 않는 테이블명입니다.", code="INVALID_TABLE_NAME")
    return name


async def _lookup_registered_dataset(
    db: AsyncSession,
    target_table: str,
) -> StandardDatasetType:
    row = (
        await db.execute(
            select(StandardDatasetType).where(
                _target_table_match_clause(target_table),
                StandardDatasetType.status != "ARCHIVED",
            )
        )
    ).scalar_one_or_none()
    if not row:
        raise TargetTablePreviewError(
            403,
            "등록된 표준 데이터셋 target_table이 아니거나 보관(ARCHIVED) 상태입니다.",
            code="TARGET_TABLE_NOT_ALLOWED",
        )
    return row


def _serialize_cell(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, time):
        return value.isoformat()
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, (bytes, memoryview)):
        return "<binary>"
    if isinstance(value, (list, dict)):
        return value
    return str(value)


async def preview_target_table_sample(
    db: AsyncSession,
    *,
    target_table: str | None,
    limit: int | None = None,
) -> dict[str, Any]:
    """Return row_count + LIMIT N sample rows for a registered target table."""
    name = _validate_table_name(target_table)
    dataset = await _lookup_registered_dataset(db, name)
    physical = resolve_physical_table_name(dataset.target_table or name)
    sample_limit = _clamp_limit(limit)

    exists = await check_physical_table_exists(db, dataset.target_table or name)
    if not exists:
        status = str(dataset.status or "").upper()
        hint = (
            "표준 데이터셋이 DRAFT이거나 물리 테이블이 아직 생성되지 않았을 수 있습니다."
            if status in {"DRAFT", "PLANNED", ""}
            else "물리 테이블이 존재하지 않습니다. 표준 데이터셋 Wizard에서 내부 테이블 생성을 확인하세요."
        )
        raise TargetTablePreviewError(
            404,
            f"대상 테이블을 찾을 수 없습니다. {hint}",
            code="PHYSICAL_TABLE_NOT_FOUND",
        )

    schema_q = quote_ident(ALLOWED_SCHEMA)
    table_q = quote_ident(physical)
    # Identifiers are quote_ident'd after whitelist + TABLE_NAME_RE checks.
    # LIMIT uses a bound parameter.
    try:
        count_result = await db.execute(text(f"SELECT COUNT(*) FROM {schema_q}.{table_q}"))
        row_count = int(count_result.scalar() or 0)

        col_result = await db.execute(
            text(
                """
                SELECT column_name, data_type
                FROM information_schema.columns
                WHERE table_schema = :schema AND table_name = :table
                ORDER BY ordinal_position
                """
            ),
            {"schema": ALLOWED_SCHEMA, "table": physical},
        )
        columns = [{"name": r[0], "data_type": r[1]} for r in col_result.all()]

        rows_result = await db.execute(
            text(f"SELECT * FROM {schema_q}.{table_q} LIMIT :limit"),
            {"limit": sample_limit},
        )
        mappings = rows_result.mappings().all()
        rows = [{k: _serialize_cell(v) for k, v in dict(m).items()} for m in mappings]
    except TargetTablePreviewError:
        raise
    except Exception as exc:  # noqa: BLE001 — surface as preview failure
        raise TargetTablePreviewError(
            500,
            "샘플 조회에 실패했습니다. 실행 상태와 target table 권한을 확인해 주세요.",
            code="PREVIEW_QUERY_FAILED",
        ) from exc

    return {
        "table_name": physical,
        "dataset_type_id": dataset.dataset_type_id,
        "dataset_status": dataset.status,
        "physical_table_exists": True,
        "row_count": row_count,
        "limit": sample_limit,
        "columns": columns,
        "rows": rows,
        "sampled_at": utc_now().isoformat(),
    }
