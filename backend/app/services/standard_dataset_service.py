"""표준 학습 데이터셋 유형·대상 테이블 관리 (Phase R7)."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from sqlalchemy import and_, func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.time import utc_now
from app.models.entities import StandardDatasetColumn, StandardDatasetType
from app.services.feature_column_role_service import summarize_role_coverage
from app.services.feature_recipe_template_service import (
    evaluate_template_availability,
    list_template_specs,
)
from app.utils.standard_dataset_metadata import (
    dataset_category_options,
    normalize_business_domain,
    normalize_dataset_category,
    normalize_tags,
    resolve_metadata_fields,
    tags_from_json,
)
from app.services.physical_table_service import (
    PhysicalTableValidationError,
    column_dict_from_row,
    create_managed_physical_table,
    preview_managed_physical_table,
    suggest_physical_table_name,
    validate_managed_dataset_definition,
)


class TargetTableNotAllowedError(ValueError):
    """매핑 대상 테이블 allowlist 위반."""

    def __init__(
        self,
        message: str,
        *,
        allowed_tables: list[str] | None = None,
        warnings: list[str] | None = None,
    ) -> None:
        self.error_code = "INVALID_TARGET_TABLE"
        self.allowed_tables = allowed_tables or []
        self.warnings = warnings or []
        super().__init__(message)


def normalize_target_table_key(target_table: str | None) -> str:
    if not target_table:
        return ""
    return target_table.lower().replace("tb_", "")


def resolve_physical_table_name(target_table: str) -> str:
    lowered = target_table.strip().lower()
    if lowered.startswith("std_") or lowered.startswith("stg_"):
        return lowered
    key = normalize_target_table_key(target_table)
    if key in ("heat_demand_actual", "weather_observation"):
        return f"tb_{key}"
    if lowered.startswith("tb_"):
        return lowered
    return f"tb_{key}"


def _yn(value: str | None) -> bool:
    return (value or "").upper() == "Y"


def _dataset_type_dict(
    row: StandardDatasetType,
    *,
    columns: list[dict[str, Any]] | None = None,
    physical_exists: bool | None = None,
    column_count: int | None = None,
) -> dict[str, Any]:
    exists = physical_exists if physical_exists is not None else _yn(row.physical_table_exists_yn)
    category = getattr(row, "category", None) or "CUSTOM"
    tags = tags_from_json(getattr(row, "tags_json", None))
    item: dict[str, Any] = {
        "dataset_type_id": row.dataset_type_id,
        "dataset_type_code": row.dataset_type_code,
        "dataset_type_name": row.dataset_type_name,
        "description": row.description,
        "dataset_category": category,
        "category": category,
        "business_domain": getattr(row, "business_domain", None),
        "tags": tags,
        "target_table": row.target_table,
        "status": row.status,
        "physical_table_yn": _yn(row.physical_table_yn),
        "physical_table_exists": exists,
        "physical_table_schema": getattr(row, "physical_table_schema", None) or "public",
        "managed_table": _yn(getattr(row, "managed_table_yn", "N")),
        "table_create_status": getattr(row, "table_create_status", None) or "NOT_CREATED",
        "table_create_sql_preview": getattr(row, "table_create_sql_preview", None),
        "table_create_error": getattr(row, "table_create_error", None),
        "physical_table_created_at": (
            row.physical_table_created_at.isoformat()
            if getattr(row, "physical_table_created_at", None) else None
        ),
        "mapping_supported": _yn(row.mapping_supported_yn),
        "recipe_supported": _yn(row.recipe_supported_yn),
        "build_supported": _yn(row.build_supported_yn),
        "active": _yn(row.active_yn),
        "owner": row.owner,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }
    if columns is not None:
        item["columns"] = columns
        item["column_count"] = len(columns)
        item["required_column_count"] = sum(1 for c in columns if c.get("required"))
        item["default_roles"] = _group_default_roles(columns)
    elif column_count is not None:
        item["column_count"] = column_count
    return item


def _column_dict(row: StandardDatasetColumn) -> dict[str, Any]:
    return {
        "column_id": row.column_id,
        "dataset_type_id": row.dataset_type_id,
        "column_name": row.column_name,
        "display_name": row.display_name,
        "data_type": row.data_type,
        "data_length": getattr(row, "data_length", None),
        "numeric_precision": getattr(row, "numeric_precision", None),
        "numeric_scale": getattr(row, "numeric_scale", None),
        "nullable": _yn(row.nullable_yn),
        "required": _yn(row.required_yn),
        "primary_key": _yn(row.primary_key_yn),
        "unique": _yn(getattr(row, "unique_yn", "N")),
        "default_column_role": row.default_column_role,
        "role_required": _yn(row.role_required_yn),
        "description": row.description,
        "example_value": row.example_value,
        "sort_order": row.sort_order,
        "active": _yn(row.active_yn),
    }


def _group_default_roles(columns: list[dict[str, Any]]) -> dict[str, list[str]]:
    grouped: dict[str, list[str]] = {}
    for col in columns:
        role = col.get("default_column_role")
        if not role:
            continue
        grouped.setdefault(role, []).append(col["column_name"])
    return grouped


async def check_physical_table_exists(db: AsyncSession, target_table: str) -> bool:
    physical = resolve_physical_table_name(target_table)
    schema = "public"
    result = await db.execute(
        text(
            "SELECT 1 FROM information_schema.tables "
            "WHERE table_schema = :schema AND table_name = :name LIMIT 1"
        ),
        {"schema": schema, "name": physical},
    )
    return result.scalar() is not None


def _column_payload_to_entity(col: dict[str, Any], dataset_type_id: str, idx: int) -> StandardDatasetColumn:
    col_id = col.get("column_id") or f"SDC-{uuid4().hex[:8].upper()}"
    return StandardDatasetColumn(
        column_id=col_id,
        dataset_type_id=dataset_type_id,
        column_name=str(col["column_name"]).strip().lower(),
        display_name=col.get("display_name"),
        data_type=col.get("data_type") or "STRING",
        data_length=col.get("data_length"),
        numeric_precision=col.get("numeric_precision"),
        numeric_scale=col.get("numeric_scale"),
        nullable_yn="N" if col.get("required") or col.get("primary_key") else "Y",
        required_yn="Y" if col.get("required") else "N",
        primary_key_yn="Y" if col.get("primary_key") else "N",
        unique_yn="Y" if col.get("unique") else "N",
        default_column_role=col.get("default_column_role"),
        role_required_yn="Y" if col.get("role_required") else "N",
        description=col.get("description"),
        example_value=col.get("example_value"),
        sort_order=col.get("sort_order", idx),
        active_yn="Y",
        created_at=utc_now(),
    )


async def _load_columns(db: AsyncSession, dataset_type_id: str) -> list[dict[str, Any]]:
    rows = (
        await db.execute(
            select(StandardDatasetColumn)
            .where(
                StandardDatasetColumn.dataset_type_id == dataset_type_id,
                StandardDatasetColumn.active_yn == "Y",
            )
            .order_by(StandardDatasetColumn.sort_order, StandardDatasetColumn.column_name)
        )
    ).scalars().all()
    return [_column_dict(r) for r in rows]


def _target_table_match_clause(target_table: str):
    key = normalize_target_table_key(target_table)
    variants = {target_table, key, f"tb_{key}"}
    return or_(*[StandardDatasetType.target_table == v for v in variants])


async def get_standard_dataset_by_target_table(
    db: AsyncSession,
    target_table: str,
) -> StandardDatasetType | None:
    return (
        await db.execute(
            select(StandardDatasetType).where(
                _target_table_match_clause(target_table),
                StandardDatasetType.active_yn == "Y",
            )
        )
    ).scalar_one_or_none()


async def _count_columns(db: AsyncSession, dataset_type_id: str) -> int:
    result = await db.execute(
        select(func.count())
        .select_from(StandardDatasetColumn)
        .where(
            StandardDatasetColumn.dataset_type_id == dataset_type_id,
            StandardDatasetColumn.active_yn == "Y",
        )
    )
    return int(result.scalar() or 0)


async def list_standard_dataset_metadata_options(db: AsyncSession) -> dict[str, Any]:
    domain_rows = (
        await db.execute(
            select(StandardDatasetType.business_domain)
            .where(
                StandardDatasetType.active_yn == "Y",
                StandardDatasetType.business_domain.is_not(None),
                StandardDatasetType.business_domain != "",
            )
            .distinct()
            .order_by(StandardDatasetType.business_domain)
        )
    ).scalars().all()

    tag_rows = (
        await db.execute(
            text(
                """
                SELECT DISTINCT tag
                FROM tb_standard_dataset_type,
                     LATERAL jsonb_array_elements_text(tags_json) AS tag
                WHERE active_yn = 'Y'
                  AND tags_json IS NOT NULL
                  AND jsonb_typeof(tags_json) = 'array'
                ORDER BY tag
                """
            )
        )
    ).all()

    return {
        "dataset_categories": dataset_category_options(),
        "business_domains": [d for d in domain_rows if d],
        "tags": [row[0] for row in tag_rows if row and row[0]],
    }


async def list_standard_dataset_types(
    db: AsyncSession,
    *,
    status: str | None = None,
    domain: str | None = None,
    business_domain: str | None = None,
    category: str | None = None,
    dataset_category: str | None = None,
    tag: str | None = None,
    keyword: str | None = None,
    physical_table_exists_yn: str | None = None,
    mapping_supported: bool | None = None,
    recipe_supported: bool | None = None,
    build_supported: bool | None = None,
    include_columns: bool = False,
    include_planned: bool = True,
) -> list[dict[str, Any]]:
    q = select(StandardDatasetType).where(StandardDatasetType.active_yn == "Y")
    if status:
        q = q.where(StandardDatasetType.status == status.upper())
    elif not include_planned:
        q = q.where(StandardDatasetType.status == "ACTIVE")

    resolved_business_domain = business_domain or domain
    if resolved_business_domain:
        q = q.where(StandardDatasetType.business_domain == resolved_business_domain.strip())

    resolved_category = dataset_category or category
    if resolved_category:
        q = q.where(StandardDatasetType.category == normalize_dataset_category(resolved_category))

    if tag:
        q = q.where(StandardDatasetType.tags_json.contains([tag.strip()]))

    if keyword:
        kw = f"%{keyword.strip()}%"
        q = q.where(
            or_(
                StandardDatasetType.dataset_type_name.ilike(kw),
                StandardDatasetType.dataset_type_code.ilike(kw),
                StandardDatasetType.description.ilike(kw),
                StandardDatasetType.business_domain.ilike(kw),
            )
        )

    if mapping_supported is not None:
        q = q.where(StandardDatasetType.mapping_supported_yn == ("Y" if mapping_supported else "N"))
    if recipe_supported is not None:
        q = q.where(StandardDatasetType.recipe_supported_yn == ("Y" if recipe_supported else "N"))
    if build_supported is not None:
        q = q.where(StandardDatasetType.build_supported_yn == ("Y" if build_supported else "N"))

    rows = (await db.execute(q.order_by(StandardDatasetType.dataset_type_name))).scalars().all()
    items: list[dict[str, Any]] = []
    for row in rows:
        cols = await _load_columns(db, row.dataset_type_id) if include_columns else None
        col_count = len(cols) if cols is not None else await _count_columns(db, row.dataset_type_id)
        physical_exists = await check_physical_table_exists(db, row.target_table)
        if physical_table_exists_yn:
            want_exists = physical_table_exists_yn.upper() == "Y"
            if physical_exists != want_exists:
                continue
        items.append(
            _dataset_type_dict(
                row,
                columns=cols,
                physical_exists=physical_exists,
                column_count=col_count,
            )
        )
    return items


async def get_standard_dataset_type(
    db: AsyncSession,
    dataset_type_id: str,
    *,
    include_columns: bool = True,
    include_recipe_availability: bool = False,
) -> dict[str, Any]:
    row = (
        await db.execute(
            select(StandardDatasetType).where(StandardDatasetType.dataset_type_id == dataset_type_id)
        )
    ).scalar_one_or_none()
    if not row:
        raise LookupError("DATASET_TYPE_NOT_FOUND")

    cols = await _load_columns(db, dataset_type_id) if include_columns else None
    physical_exists = await check_physical_table_exists(db, row.target_table)
    item = _dataset_type_dict(row, columns=cols, physical_exists=physical_exists)
    if include_recipe_availability and cols:
        item["recipe_readiness"] = await get_dataset_recipe_readiness(db, dataset_type_id)
    return item


async def list_mapping_target_tables(
    db: AsyncSession,
    *,
    active_only: bool = True,
    mapping_supported: bool = True,
) -> list[dict[str, Any]]:
    q = select(StandardDatasetType).where(StandardDatasetType.active_yn == "Y")
    if active_only:
        q = q.where(StandardDatasetType.status == "ACTIVE")
    if mapping_supported:
        q = q.where(StandardDatasetType.mapping_supported_yn == "Y")

    rows = (await db.execute(q.order_by(StandardDatasetType.dataset_type_name))).scalars().all()
    items: list[dict[str, Any]] = []
    for row in rows:
        physical_exists = await check_physical_table_exists(db, row.target_table)
        if not physical_exists:
            continue
        cols = await _load_columns(db, row.dataset_type_id)
        items.append({
            "dataset_type_id": row.dataset_type_id,
            "dataset_type_code": row.dataset_type_code,
            "dataset_type_name": row.dataset_type_name,
            "target_table": row.target_table,
            "dataset_category": row.category,
            "category": row.category,
            "business_domain": getattr(row, "business_domain", None),
            "tags": tags_from_json(getattr(row, "tags_json", None)),
            "description": row.description,
            "build_supported": _yn(row.build_supported_yn),
            "recipe_supported": _yn(row.recipe_supported_yn),
            "managed_table": _yn(getattr(row, "managed_table_yn", "N")),
            "standard_columns": [c["column_name"] for c in cols],
        })
    return items


async def validate_target_table_allowed(
    db: AsyncSession,
    target_table: str,
) -> dict[str, Any]:
    warnings: list[str] = []
    row = await get_standard_dataset_by_target_table(db, target_table)
    if not row:
        allowed = [r.target_table for r in (await db.execute(
            select(StandardDatasetType).where(
                StandardDatasetType.active_yn == "Y",
                StandardDatasetType.status == "ACTIVE",
                StandardDatasetType.mapping_supported_yn == "Y",
            )
        )).scalars().all()]
        raise TargetTableNotAllowedError(
            "대상 테이블은 표준 대상 테이블 목록에서 선택해야 합니다.",
            allowed_tables=sorted(set(allowed)),
        )

    if row.status != "ACTIVE":
        raise TargetTableNotAllowedError(
            f"대상 테이블 '{target_table}'은 상태가 {row.status}이므로 매핑에 사용할 수 없습니다.",
            allowed_tables=[],
        )
    if not _yn(row.mapping_supported_yn):
        raise TargetTableNotAllowedError(
            f"대상 테이블 '{target_table}'은 매핑 지원 대상이 아닙니다.",
            allowed_tables=[],
        )

    physical_exists = await check_physical_table_exists(db, row.target_table)
    if not physical_exists:
        raise TargetTableNotAllowedError(
            f"대상 테이블 '{target_table}'의 물리 테이블이 존재하지 않습니다.",
            allowed_tables=[],
            warnings=["physical_table_missing"],
        )
    if not _yn(row.physical_table_exists_yn):
        warnings.append("physical_table_exists_yn=N — DB 메타를 갱신하세요.")

    cols = await _load_columns(db, row.dataset_type_id)
    dataset = _dataset_type_dict(row, columns=cols, physical_exists=physical_exists)
    return {
        "valid": True,
        "dataset_type": dataset,
        "warnings": warnings,
    }


async def get_default_column_roles_for_target_table(
    db: AsyncSession,
    target_table: str,
) -> dict[str, str]:
    row = await get_standard_dataset_by_target_table(db, target_table)
    if not row:
        return {}
    cols = await _load_columns(db, row.dataset_type_id)
    return {
        c["column_name"]: c["default_column_role"]
        for c in cols
        if c.get("default_column_role")
    }


async def get_dataset_recipe_readiness(
    db: AsyncSession,
    dataset_type_id: str,
) -> dict[str, Any]:
    cols = await _load_columns(db, dataset_type_id)
    roles = [
        {
            "source_column": c["column_name"],
            "target_column": c["column_name"],
            "column_role": c["default_column_role"] or "NUMERIC_INPUT",
        }
        for c in cols
        if c.get("default_column_role")
    ]
    summary = summarize_role_coverage(roles)
    templates: list[dict[str, Any]] = []
    for spec in list_template_specs():
        avail = evaluate_template_availability(spec, summary)
        templates.append({
            "recipe_type": spec.recipe_type,
            "display_name": spec.display_name,
            "status": spec.status,
            "available": avail["available"],
            "missing_roles": avail.get("missing_roles") or [],
            "warnings": avail.get("warnings") or [],
        })
    return {
        "role_summary": summary,
        "templates": templates,
        "available_count": sum(1 for t in templates if t["available"]),
    }


async def create_standard_dataset_type(
    db: AsyncSession,
    payload: dict[str, Any],
) -> dict[str, Any]:
    target_table = str(payload["target_table"]).strip().lower()
    status = (payload.get("status") or "DRAFT").upper()
    managed = target_table.startswith("std_") or bool(payload.get("managed_table"))
    id_prefix = "SDS" if managed else "DST"
    dataset_type_id = payload.get("dataset_type_id") or f"{id_prefix}-{uuid4().hex[:8].upper()}"
    physical_exists = await check_physical_table_exists(db, target_table) if not managed else False
    if status == "ACTIVE" and not physical_exists:
        raise ValueError("ACTIVE 전환에는 물리 테이블이 존재해야 합니다.")

    try:
        meta = resolve_metadata_fields(payload)
    except ValueError as exc:
        raise ValueError(str(exc)) from exc

    row = StandardDatasetType(
        dataset_type_id=dataset_type_id,
        dataset_type_code=payload["dataset_type_code"].upper(),
        dataset_type_name=payload["dataset_type_name"],
        description=payload.get("description"),
        domain=None,
        category=meta["dataset_category"],
        business_domain=meta["business_domain"],
        tags_json=meta["tags"],
        target_table=target_table,
        physical_table_schema="public",
        physical_table_yn="Y" if payload.get("physical_table_yn", True) else "N",
        physical_table_exists_yn="Y" if physical_exists else "N",
        managed_table_yn="Y" if managed else "N",
        table_create_status="SUCCESS" if physical_exists else "NOT_CREATED",
        build_supported_yn="Y" if payload.get("build_supported") else "N",
        recipe_supported_yn="Y" if payload.get("recipe_supported") else "N",
        mapping_supported_yn="Y" if payload.get("mapping_supported", status == "ACTIVE") else "N",
        status=status,
        owner=payload.get("owner"),
        active_yn="Y",
        created_at=utc_now(),
    )
    db.add(row)
    await db.flush()

    columns = payload.get("columns") or []
    for idx, col in enumerate(columns):
        db.add(_column_payload_to_entity(col, dataset_type_id, idx))
    await db.flush()
    return await get_standard_dataset_type(db, dataset_type_id)


async def update_standard_dataset_type(
    db: AsyncSession,
    dataset_type_id: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    row = (
        await db.execute(
            select(StandardDatasetType).where(StandardDatasetType.dataset_type_id == dataset_type_id)
        )
    ).scalar_one_or_none()
    if not row:
        raise LookupError("DATASET_TYPE_NOT_FOUND")
    if row.status == "ARCHIVED":
        raise ValueError("ARCHIVED 데이터셋 유형은 수정할 수 없습니다.")
    if row.status == "ACTIVE":
        raise ValueError("ACTIVE 데이터셋 유형은 컬럼/테이블 정의를 수정할 수 없습니다. Archive 후 재등록하세요.")

    for field, attr in (
        ("dataset_type_name", "dataset_type_name"),
        ("description", "description"),
        ("owner", "owner"),
    ):
        if field in payload and payload[field] is not None:
            setattr(row, attr, payload[field])

    if "dataset_category" in payload or "category" in payload:
        row.category = normalize_dataset_category(
            payload.get("dataset_category") or payload.get("category") or row.category
        )
    if "business_domain" in payload or "domain" in payload:
        meta = resolve_metadata_fields(payload)
        row.business_domain = meta["business_domain"]
    if "tags" in payload:
        row.tags_json = normalize_tags(payload.get("tags"))
    row.domain = None

    if "target_table" in payload and payload["target_table"]:
        if row.status in ("ACTIVE", "VALIDATED"):
            raise ValueError("VALIDATED/ACTIVE 데이터셋 유형의 target_table은 변경할 수 없습니다.")
        row.target_table = str(payload["target_table"]).strip().lower()
        row.managed_table_yn = "Y" if row.target_table.startswith("std_") else "N"
        exists = await check_physical_table_exists(db, row.target_table)
        row.physical_table_exists_yn = "Y" if exists else "N"
        if not exists:
            row.table_create_status = "NOT_CREATED"

    for flag, attr in (
        ("build_supported", "build_supported_yn"),
        ("recipe_supported", "recipe_supported_yn"),
        ("mapping_supported", "mapping_supported_yn"),
    ):
        if flag in payload and payload[flag] is not None:
            setattr(row, attr, "Y" if payload[flag] else "N")

    if payload.get("columns") is not None:
        existing = (
            await db.execute(
                select(StandardDatasetColumn).where(StandardDatasetColumn.dataset_type_id == dataset_type_id)
            )
        ).scalars().all()
        for col in existing:
            col.active_yn = "N"
            col.updated_at = utc_now()
        for idx, col in enumerate(payload["columns"] or []):
            db.add(_column_payload_to_entity(col, dataset_type_id, idx))
        if row.status == "VALIDATED":
            row.status = "DRAFT"
            row.table_create_status = "NOT_CREATED"
            row.table_create_sql_preview = None

    row.updated_at = utc_now()
    await db.flush()
    return await get_standard_dataset_type(db, dataset_type_id)


async def activate_standard_dataset_type(db: AsyncSession, dataset_type_id: str) -> dict[str, Any]:
    row = (
        await db.execute(
            select(StandardDatasetType).where(StandardDatasetType.dataset_type_id == dataset_type_id)
        )
    ).scalar_one_or_none()
    if not row:
        raise LookupError("DATASET_TYPE_NOT_FOUND")
    if row.status == "ARCHIVED":
        raise ValueError("ARCHIVED 데이터셋 유형은 활성화할 수 없습니다.")

    cols = await _load_columns(db, dataset_type_id)
    if not cols:
        raise ValueError("표준 컬럼 정의가 없어 ACTIVE로 전환할 수 없습니다.")

    physical_exists = await check_physical_table_exists(db, row.target_table)
    if not physical_exists:
        raise ValueError("물리 테이블이 존재하지 않아 ACTIVE로 전환할 수 없습니다.")

    row.physical_table_exists_yn = "Y"
    row.status = "ACTIVE"
    row.mapping_supported_yn = "Y"
    row.updated_at = utc_now()
    await db.flush()
    return await get_standard_dataset_type(db, dataset_type_id, include_recipe_availability=True)


async def archive_standard_dataset_type(db: AsyncSession, dataset_type_id: str) -> dict[str, Any]:
    row = (
        await db.execute(
            select(StandardDatasetType).where(StandardDatasetType.dataset_type_id == dataset_type_id)
        )
    ).scalar_one_or_none()
    if not row:
        raise LookupError("DATASET_TYPE_NOT_FOUND")
    row.status = "ARCHIVED"
    row.mapping_supported_yn = "N"
    row.active_yn = "N"
    row.archived_at = utc_now()
    row.archive_reason = "archived_by_user"
    row.updated_at = utc_now()
    await db.flush()
    return _dataset_type_dict(row)


async def _get_dataset_row(db: AsyncSession, dataset_type_id: str) -> StandardDatasetType:
    row = (
        await db.execute(
            select(StandardDatasetType).where(StandardDatasetType.dataset_type_id == dataset_type_id)
        )
    ).scalar_one_or_none()
    if not row:
        raise LookupError("DATASET_TYPE_NOT_FOUND")
    return row


async def validate_standard_dataset_definition(
    db: AsyncSession,
    dataset_type_id: str,
) -> dict[str, Any]:
    row = await _get_dataset_row(db, dataset_type_id)
    if row.status == "ARCHIVED":
        raise ValueError("ARCHIVED 데이터셋은 검증할 수 없습니다.")
    col_rows = (
        await db.execute(
            select(StandardDatasetColumn).where(
                StandardDatasetColumn.dataset_type_id == dataset_type_id,
                StandardDatasetColumn.active_yn == "Y",
            ).order_by(StandardDatasetColumn.sort_order, StandardDatasetColumn.column_name)
        )
    ).scalars().all()
    col_dicts = [column_dict_from_row(c) for c in col_rows]

    managed = (row.managed_table_yn or "N").upper() == "Y"
    result = await validate_managed_dataset_definition(
        db,
        target_table=row.target_table,
        schema=(row.physical_table_schema or "public"),
        columns=col_dicts,
        managed=managed,
    )
    if result["valid"] and row.status == "DRAFT":
        row.status = "VALIDATED"
        row.updated_at = utc_now()
        await db.flush()
    result["lifecycle_status"] = row.status
    return result


async def preview_standard_dataset_create_table(
    db: AsyncSession,
    dataset_type_id: str,
) -> dict[str, Any]:
    row = await _get_dataset_row(db, dataset_type_id)
    col_rows = (
        await db.execute(
            select(StandardDatasetColumn).where(
                StandardDatasetColumn.dataset_type_id == dataset_type_id,
                StandardDatasetColumn.active_yn == "Y",
            ).order_by(StandardDatasetColumn.sort_order, StandardDatasetColumn.column_name)
        )
    ).scalars().all()
    col_dicts = [column_dict_from_row(c) for c in col_rows]
    result = await preview_managed_physical_table(db, row, col_dicts)
    result["lifecycle_status"] = row.status
    return result


async def create_standard_dataset_physical_table(
    db: AsyncSession,
    dataset_type_id: str,
    *,
    requested_by: str | None = None,
) -> dict[str, Any]:
    row = await _get_dataset_row(db, dataset_type_id)
    col_rows = (
        await db.execute(
            select(StandardDatasetColumn).where(
                StandardDatasetColumn.dataset_type_id == dataset_type_id,
                StandardDatasetColumn.active_yn == "Y",
            ).order_by(StandardDatasetColumn.sort_order, StandardDatasetColumn.column_name)
        )
    ).scalars().all()
    col_dicts = [column_dict_from_row(c) for c in col_rows]
    try:
        result = await create_managed_physical_table(db, row, col_dicts, requested_by=requested_by)
    except PhysicalTableValidationError as exc:
        raise ValueError(exc.errors[0]["message"] if exc.errors else str(exc)) from exc
    dataset = await get_standard_dataset_type(db, dataset_type_id, include_recipe_availability=True)
    return {**result, "dataset_type": dataset}


def suggest_table_name_from_code(dataset_code: str) -> str:
    return suggest_physical_table_name(dataset_code)
