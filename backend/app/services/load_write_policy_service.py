from __future__ import annotations

from collections import defaultdict
from typing import Any
from uuid import uuid4

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.time import utc_now
from app.models.entities import (
    ApiConnectorLoadDedupSummary,
    ApiConnectorOperation,
    ApiConnectorWritePolicy,
)
from app.services.api_connector_loader import get_physical_columns, prepare_rows_for_target
from app.services.standard_dataset_service import resolve_physical_table_name, validate_target_table_allowed
from app.utils.sql_identifier import quote_ident

WRITE_MODES = {"INSERT_ONLY", "UPSERT", "DEDUPLICATE"}
BATCH_POLICIES = {"KEEP_FIRST", "KEEP_LAST", "ERROR"}
NULL_POLICIES = {"KEEP_EXISTING", "OVERWRITE_WITH_NULL"}
NO_KEY_POLICIES = {"WARN_INSERT_ONLY", "BLOCK_RUN"}
RESERVED_UPDATE_COLUMNS = {"created_at"}


class WritePolicyError(ValueError):
    pass


def _new_id(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex[:8].upper()}"


def _normalize_str_list(value: Any) -> list[str]:
    if not value:
        return []
    out: list[str] = []
    for item in value:
        if not item:
            continue
        out.append(str(item).strip())
    return out


def _policy_dict(row: ApiConnectorWritePolicy | None, operation_id: str, target_table: str | None) -> dict[str, Any]:
    if not row:
        return {
            "operation_id": operation_id,
            "target_table": target_table,
            "write_mode": "INSERT_ONLY",
            "conflict_key_columns_json": [],
            "update_columns_json": [],
            "exclude_update_columns_json": [],
            "compare_columns_json": [],
            "null_update_policy": "KEEP_EXISTING",
            "duplicate_within_batch_policy": "KEEP_LAST",
            "no_conflict_key_policy": "WARN_INSERT_ONLY",
            "active_yn": True,
            "warnings": [],
        }
    return {
        "write_policy_id": row.write_policy_id,
        "operation_id": row.operation_id,
        "target_table": row.target_table,
        "write_mode": row.write_mode,
        "conflict_key_columns_json": row.conflict_key_columns_json or [],
        "update_columns_json": row.update_columns_json or [],
        "exclude_update_columns_json": row.exclude_update_columns_json or [],
        "compare_columns_json": row.compare_columns_json or [],
        "null_update_policy": row.null_update_policy,
        "duplicate_within_batch_policy": row.duplicate_within_batch_policy,
        "no_conflict_key_policy": row.no_conflict_key_policy,
        "active_yn": bool(row.active_yn),
        "metadata_json": row.metadata_json,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


async def _get_operation(db: AsyncSession, operation_id: str) -> ApiConnectorOperation:
    op = (
        await db.execute(select(ApiConnectorOperation).where(ApiConnectorOperation.operation_id == operation_id))
    ).scalar_one_or_none()
    if not op:
        raise WritePolicyError("API 작업을 찾을 수 없습니다.")
    return op


async def _get_active_policy(db: AsyncSession, operation_id: str, target_table: str) -> ApiConnectorWritePolicy | None:
    return (
        await db.execute(
            select(ApiConnectorWritePolicy).where(
                ApiConnectorWritePolicy.operation_id == operation_id,
                ApiConnectorWritePolicy.target_table == target_table,
                ApiConnectorWritePolicy.active_yn.is_(True),
            )
        )
    ).scalar_one_or_none()


async def get_write_policy(db: AsyncSession, operation_id: str) -> dict[str, Any]:
    op = await _get_operation(db, operation_id)
    if not op.target_table:
        return _policy_dict(None, operation_id, None)
    policy = await _get_active_policy(db, operation_id, op.target_table)
    return _policy_dict(policy, operation_id, op.target_table)


async def list_write_policies(db: AsyncSession) -> list[dict[str, Any]]:
    rows = (
        await db.execute(
            select(ApiConnectorWritePolicy)
            .where(ApiConnectorWritePolicy.active_yn.is_(True))
            .order_by(ApiConnectorWritePolicy.updated_at.desc().nullslast())
        )
    ).scalars().all()
    return [_policy_dict(r, r.operation_id, r.target_table) for r in rows]


async def get_target_table_columns(db: AsyncSession, target_table: str) -> dict[str, Any]:
    await validate_target_table_allowed(db, target_table)
    physical = resolve_physical_table_name(target_table)
    cols = await get_physical_columns(db, physical)
    return {"target_table": target_table, "physical_table": physical, "columns": cols}


async def validate_write_policy_payload(
    db: AsyncSession,
    operation_id: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    op = await _get_operation(db, operation_id)
    if not op.target_table:
        raise WritePolicyError("적재 대상 테이블이 설정되지 않았습니다.")
    await validate_target_table_allowed(db, op.target_table)
    valid_cols = set((await get_target_table_columns(db, op.target_table))["columns"])

    write_mode = str(payload.get("write_mode") or "INSERT_ONLY").upper()
    if write_mode not in WRITE_MODES:
        raise WritePolicyError("지원하지 않는 적재 방식입니다.")
    conflict_keys = _normalize_str_list(payload.get("conflict_key_columns_json"))
    update_cols = _normalize_str_list(payload.get("update_columns_json"))
    exclude_update_cols = _normalize_str_list(payload.get("exclude_update_columns_json"))
    null_update_policy = str(payload.get("null_update_policy") or "KEEP_EXISTING").upper()
    duplicate_within_batch_policy = str(payload.get("duplicate_within_batch_policy") or "KEEP_LAST").upper()
    no_conflict_key_policy = str(payload.get("no_conflict_key_policy") or "WARN_INSERT_ONLY").upper()

    if null_update_policy not in NULL_POLICIES:
        raise WritePolicyError("null 값 처리 정책이 올바르지 않습니다.")
    if duplicate_within_batch_policy not in BATCH_POLICIES:
        raise WritePolicyError("batch 중복 처리 정책이 올바르지 않습니다.")
    if no_conflict_key_policy not in NO_KEY_POLICIES:
        raise WritePolicyError("conflict key 미설정 정책이 올바르지 않습니다.")
    for col in conflict_keys + update_cols + exclude_update_cols:
        if col not in valid_cols:
            raise WritePolicyError(f"대상 테이블에 없는 컬럼입니다: {col}")
    for col in exclude_update_cols:
        if col in RESERVED_UPDATE_COLUMNS:
            continue
    if write_mode in {"UPSERT", "DEDUPLICATE"} and not conflict_keys:
        if no_conflict_key_policy == "BLOCK_RUN":
            raise WritePolicyError("중복 판단 키가 없어 실행할 수 없습니다.")
    warnings: list[str] = []
    if write_mode in {"UPSERT", "DEDUPLICATE"} and not conflict_keys:
        warnings.append("중복 판단 키가 없어 INSERT_ONLY로 처리됩니다.")

    return {
        "operation_id": operation_id,
        "target_table": op.target_table,
        "write_mode": write_mode,
        "conflict_key_columns_json": conflict_keys,
        "update_columns_json": update_cols,
        "exclude_update_columns_json": exclude_update_cols,
        "compare_columns_json": _normalize_str_list(payload.get("compare_columns_json")),
        "null_update_policy": null_update_policy,
        "duplicate_within_batch_policy": duplicate_within_batch_policy,
        "no_conflict_key_policy": no_conflict_key_policy,
        "active_yn": bool(payload.get("active_yn", True)),
        "metadata_json": payload.get("metadata_json"),
        "warnings": warnings,
    }


async def upsert_write_policy(db: AsyncSession, operation_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    normalized = await validate_write_policy_payload(db, operation_id, payload)
    existing = await _get_active_policy(db, operation_id, normalized["target_table"])
    now = utc_now()
    if existing:
        existing.write_mode = normalized["write_mode"]
        existing.conflict_key_columns_json = normalized["conflict_key_columns_json"]
        existing.update_columns_json = normalized["update_columns_json"]
        existing.exclude_update_columns_json = normalized["exclude_update_columns_json"]
        existing.compare_columns_json = normalized["compare_columns_json"]
        existing.null_update_policy = normalized["null_update_policy"]
        existing.duplicate_within_batch_policy = normalized["duplicate_within_batch_policy"]
        existing.no_conflict_key_policy = normalized["no_conflict_key_policy"]
        existing.active_yn = normalized["active_yn"]
        existing.metadata_json = normalized["metadata_json"]
        existing.updated_at = now
        row = existing
    else:
        row = ApiConnectorWritePolicy(
            write_policy_id=_new_id("ACWP"),
            operation_id=operation_id,
            target_table=normalized["target_table"],
            write_mode=normalized["write_mode"],
            conflict_key_columns_json=normalized["conflict_key_columns_json"],
            update_columns_json=normalized["update_columns_json"],
            exclude_update_columns_json=normalized["exclude_update_columns_json"],
            compare_columns_json=normalized["compare_columns_json"],
            null_update_policy=normalized["null_update_policy"],
            duplicate_within_batch_policy=normalized["duplicate_within_batch_policy"],
            no_conflict_key_policy=normalized["no_conflict_key_policy"],
            active_yn=normalized["active_yn"],
            created_at=now,
            updated_at=now,
            metadata_json=normalized["metadata_json"],
        )
        db.add(row)
    await db.flush()
    out = _policy_dict(row, operation_id, normalized["target_table"])
    out["warnings"] = normalized.get("warnings", [])
    return out


def _make_key(row: dict[str, Any], keys: list[str]) -> tuple[Any, ...]:
    return tuple(row.get(k) for k in keys)


async def apply_write_policy(
    db: AsyncSession,
    *,
    operation_id: str,
    target_table: str,
    items: list[dict[str, Any]],
    mapping: Any,
    dry_run: bool,
    load_run_id: str | None = None,
    schedule_run_id: str | None = None,
    max_rows: int = 1000,
) -> dict[str, Any]:
    policy = await _get_active_policy(db, operation_id, target_table)
    p = _policy_dict(policy, operation_id, target_table)
    write_mode = str(p["write_mode"] or "INSERT_ONLY").upper()
    conflict_keys = _normalize_str_list(p.get("conflict_key_columns_json"))
    if write_mode in {"UPSERT", "DEDUPLICATE"} and not conflict_keys:
        if p.get("no_conflict_key_policy") == "BLOCK_RUN":
            raise WritePolicyError("중복 판단 키가 없어 실행할 수 없습니다.")
        write_mode = "INSERT_ONLY"

    physical, cols, _, prepared_rows = await prepare_rows_for_target(
        db,
        target_table=target_table,
        items=items,
        mapping=mapping,
        max_rows=max_rows,
    )
    input_count = len(prepared_rows)
    unique_rows: list[dict[str, Any]] = []
    warnings = list(p.get("warnings", []))
    sample_conflicts: list[dict[str, Any]] = []
    duplicate_within_batch_count = 0
    if write_mode in {"UPSERT", "DEDUPLICATE"} and conflict_keys:
        by_key: dict[tuple[Any, ...], dict[str, Any]] = {}
        seen: dict[tuple[Any, ...], int] = defaultdict(int)
        for row in prepared_rows:
            key = _make_key(row, conflict_keys)
            seen[key] += 1
            if seen[key] > 1:
                duplicate_within_batch_count += 1
                if len(sample_conflicts) < 5:
                    sample_conflicts.append({"key": list(key), "type": "batch_duplicate"})
                pol = str(p.get("duplicate_within_batch_policy") or "KEEP_LAST").upper()
                if pol == "ERROR":
                    raise WritePolicyError("batch 내부 중복 데이터가 있어 실행할 수 없습니다.")
                if pol == "KEEP_FIRST":
                    continue
            by_key[key] = row
        unique_rows = list(by_key.values())
    else:
        unique_rows = prepared_rows

    inserted = 0
    updated = 0
    skipped = 0
    unchanged = 0
    errors = 0
    existing_match_count = 0
    update_cols = _normalize_str_list(p.get("update_columns_json"))
    exclude_update_cols = set(_normalize_str_list(p.get("exclude_update_columns_json")))

    for row in unique_rows:
        try:
            if write_mode == "INSERT_ONLY" or not conflict_keys:
                insert_cols = [c for c in cols if c in row]
                if not insert_cols:
                    skipped += 1
                    continue
                if not dry_run:
                    params = {c: row.get(c) for c in insert_cols}
                    placeholders = ", ".join(f":{c}" for c in insert_cols)
                    col_list = ", ".join(quote_ident(c) for c in insert_cols)
                    sql = f'INSERT INTO {quote_ident(physical)} ({col_list}) VALUES ({placeholders})'
                    await db.execute(text(sql), params)
                inserted += 1
                continue

            where_clause = " AND ".join(f"{quote_ident(k)} = :w_{k}" for k in conflict_keys)
            where_params = {f"w_{k}": row.get(k) for k in conflict_keys}
            sel = await db.execute(
                text(f'SELECT * FROM {quote_ident(physical)} WHERE {where_clause} LIMIT 1'),
                where_params,
            )
            existing = sel.mappings().first()
            if existing is None:
                insert_cols = [c for c in cols if c in row]
                if insert_cols:
                    if not dry_run:
                        params = {c: row.get(c) for c in insert_cols}
                        placeholders = ", ".join(f":{c}" for c in insert_cols)
                        col_list = ", ".join(quote_ident(c) for c in insert_cols)
                        sql = f'INSERT INTO {quote_ident(physical)} ({col_list}) VALUES ({placeholders})'
                        await db.execute(text(sql), params)
                    inserted += 1
                else:
                    skipped += 1
                continue

            existing_match_count += 1
            if write_mode == "DEDUPLICATE":
                skipped += 1
                continue

            candidate_cols = update_cols or [c for c in cols if c in row and c not in conflict_keys]
            candidate_cols = [
                c for c in candidate_cols if c in cols and c not in exclude_update_cols and c not in RESERVED_UPDATE_COLUMNS
            ]
            set_cols: list[str] = []
            set_params: dict[str, Any] = {}
            for c in candidate_cols:
                incoming = row.get(c)
                if incoming is None and p.get("null_update_policy") == "KEEP_EXISTING":
                    continue
                if existing.get(c) == incoming:
                    continue
                set_cols.append(c)
                set_params[f"u_{c}"] = incoming
            if not set_cols:
                unchanged += 1
                continue
            if not dry_run:
                set_clause = ", ".join(f"{quote_ident(c)} = :u_{c}" for c in set_cols)
                sql = f'UPDATE {quote_ident(physical)} SET {set_clause} WHERE {where_clause}'
                await db.execute(text(sql), {**set_params, **where_params})
            updated += 1
        except Exception:
            errors += 1

    now = utc_now()
    summary = ApiConnectorLoadDedupSummary(
        summary_id=_new_id("ACDS"),
        load_run_id=load_run_id,
        schedule_run_id=schedule_run_id,
        operation_id=operation_id,
        target_table=target_table,
        write_mode=write_mode,
        input_row_count=input_count,
        unique_input_row_count=len(unique_rows),
        duplicate_within_batch_count=duplicate_within_batch_count,
        existing_match_count=existing_match_count,
        inserted_count=inserted,
        updated_count=updated,
        skipped_duplicate_count=skipped,
        unchanged_count=unchanged,
        error_count=errors,
        conflict_key_columns_json=conflict_keys,
        sample_conflicts_json=sample_conflicts,
        warnings_json=warnings,
        created_at=now,
        metadata_json={"dry_run": dry_run},
    )
    db.add(summary)
    await db.flush()
    return {
        "dedup_summary_id": summary.summary_id,
        "write_mode": write_mode,
        "write_policy_summary": _policy_dict(policy, operation_id, target_table),
        "input_row_count": input_count,
        "unique_input_row_count": len(unique_rows),
        "duplicate_within_batch_count": duplicate_within_batch_count,
        "existing_match_count": existing_match_count,
        "inserted_count": inserted,
        "updated_count": updated,
        "skipped_count": skipped,
        "skipped_duplicate_count": skipped,
        "unchanged_count": unchanged,
        "error_count": errors,
        "estimated_insert_count": inserted,
        "estimated_update_count": updated,
        "estimated_skip_count": skipped,
        "warnings": warnings,
        "sample_conflicts": sample_conflicts,
    }


async def list_dedup_summaries(db: AsyncSession, operation_id: str | None = None) -> list[dict[str, Any]]:
    q = select(ApiConnectorLoadDedupSummary).order_by(ApiConnectorLoadDedupSummary.created_at.desc())
    if operation_id:
        q = q.where(ApiConnectorLoadDedupSummary.operation_id == operation_id)
    rows = (await db.execute(q.limit(200))).scalars().all()
    return [
        {
            "summary_id": r.summary_id,
            "load_run_id": r.load_run_id,
            "schedule_run_id": r.schedule_run_id,
            "operation_id": r.operation_id,
            "target_table": r.target_table,
            "write_mode": r.write_mode,
            "input_row_count": r.input_row_count,
            "unique_input_row_count": r.unique_input_row_count,
            "duplicate_within_batch_count": r.duplicate_within_batch_count,
            "existing_match_count": r.existing_match_count,
            "inserted_count": r.inserted_count,
            "updated_count": r.updated_count,
            "skipped_duplicate_count": r.skipped_duplicate_count,
            "unchanged_count": r.unchanged_count,
            "error_count": r.error_count,
            "conflict_key_columns_json": r.conflict_key_columns_json,
            "sample_conflicts_json": r.sample_conflicts_json,
            "warnings_json": r.warnings_json,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "metadata_json": r.metadata_json,
        }
        for r in rows
    ]


async def get_dedup_summary(db: AsyncSession, summary_id: str) -> dict[str, Any] | None:
    row = (
        await db.execute(
            select(ApiConnectorLoadDedupSummary).where(ApiConnectorLoadDedupSummary.summary_id == summary_id)
        )
    ).scalar_one_or_none()
    if not row:
        return None
    return {
        "summary_id": row.summary_id,
        "load_run_id": row.load_run_id,
        "schedule_run_id": row.schedule_run_id,
        "operation_id": row.operation_id,
        "target_table": row.target_table,
        "write_mode": row.write_mode,
        "input_row_count": row.input_row_count,
        "unique_input_row_count": row.unique_input_row_count,
        "duplicate_within_batch_count": row.duplicate_within_batch_count,
        "existing_match_count": row.existing_match_count,
        "inserted_count": row.inserted_count,
        "updated_count": row.updated_count,
        "skipped_duplicate_count": row.skipped_duplicate_count,
        "unchanged_count": row.unchanged_count,
        "error_count": row.error_count,
        "conflict_key_columns_json": row.conflict_key_columns_json,
        "sample_conflicts_json": row.sample_conflicts_json,
        "warnings_json": row.warnings_json,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "metadata_json": row.metadata_json,
    }
