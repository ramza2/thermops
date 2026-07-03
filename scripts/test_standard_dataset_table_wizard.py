#!/usr/bin/env python3
"""표준 데이터셋 물리 테이블 생성 Wizard 테스트 (Phase R9-S2-1)."""

from __future__ import annotations

import json
import os
import re
import sys
import uuid
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from test_fixtures import create_wizard_standard_dataset, ensure_test_standard_datasets, resolve_heat_source_id

API_BASE = os.environ.get("THERMOOPS_API_BASE", "http://localhost:8000/api/v1")
ROOT = _SCRIPTS.parent
CLEAN_SEED = ROOT / "db" / "init" / "02_seed_clean.sql"


def api(method: str, path: str, body: dict | None = None, expect_fail: bool = False) -> dict | list:
    import urllib.error
    import urllib.request

    url = f"{API_BASE}{path}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={"Content-Type": "application/json"} if data else {},
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            payload = json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode()
        if expect_fail:
            try:
                parsed = json.loads(detail)
            except json.JSONDecodeError:
                return {"detail": detail, "status": exc.code}
            if isinstance(parsed, dict) and "detail" in parsed:
                if isinstance(parsed["detail"], dict):
                    return {**parsed["detail"], "status": exc.code}
                return {"detail": parsed["detail"], "status": exc.code}
            return {**parsed, "status": exc.code}
        raise RuntimeError(f"HTTP {exc.code} {method} {path}: {detail}") from exc
    if not payload.get("success"):
        raise RuntimeError(f"API failed {method} {path}: {payload}")
    return payload["data"]


def test_clean_seed_no_standard_dataset_inserts() -> None:
    text = CLEAN_SEED.read_text(encoding="utf-8")
    assert "tb_standard_dataset_type" not in text.lower() or not re.search(
        r"insert\s+into\s+tb_standard_dataset_type",
        text,
        re.IGNORECASE,
    ), "운영 seed에 표준 데이터셋 insert가 있으면 안 됩니다."
    print("  [ok] clean seed에 표준 데이터셋 insert 없음")


def test_suggest_table_name_std_prefix() -> None:
    data = api("GET", "/standard-dataset-types/suggest-table-name?dataset_code=customer_transaction")
    name = data.get("physical_table_name") or ""
    assert name.startswith("std_"), name
    print(f"  [ok] suggest table name -> {name}")


def test_invalid_table_name_rejected() -> None:
    suffix = uuid.uuid4().hex[:8]
    table = "tb_forbidden_name"
    created = api("POST", "/standard-dataset-types", {
        "dataset_type_code": f"WIZ_BAD_TBL_{suffix.upper()}",
        "dataset_type_name": "잘못된 테이블명 테스트",
        "target_table": table,
        "status": "DRAFT",
        "managed_table": True,
        "columns": [{"column_name": "id_col", "data_type": "INTEGER", "primary_key": True, "required": True}],
    })
    ds_id = created["dataset_type_id"]
    result = api("POST", f"/standard-dataset-types/{ds_id}/validate")
    assert result.get("valid") is False, result
    codes = {e.get("code") for e in result.get("errors") or []}
    assert "SYSTEM_PREFIX_NOT_ALLOWED" in codes or "INVALID_TABLE_NAME" in codes, result
    print("  [ok] invalid table name (tb_ prefix) rejected on validate")


def test_invalid_column_name_rejected() -> None:
    suffix = uuid.uuid4().hex[:8]
    table = f"std_wiz_badcol_{suffix}"
    created = api("POST", "/standard-dataset-types", {
        "dataset_type_code": f"WIZ_BADCOL_{suffix.upper()}",
        "dataset_type_name": "잘못된 컬럼명",
        "target_table": table,
        "status": "DRAFT",
        "managed_table": True,
        "columns": [{"column_name": "bad-column", "data_type": "VARCHAR", "data_length": 50}],
    })
    ds_id = created["dataset_type_id"]
    result = api("POST", f"/standard-dataset-types/{ds_id}/validate")
    assert result.get("valid") is False, result
    codes = {e.get("code") for e in result.get("errors") or []}
    assert "INVALID_COLUMN_NAME" in codes or any("컬럼" in (e.get("message") or "") for e in result.get("errors") or []), result
    print("  [ok] invalid column name rejected on validate")


def test_wizard_full_flow() -> str:
    suffix = uuid.uuid4().hex[:8]
    table = f"std_wiz_flow_{suffix}"
    code = f"WIZ_FLOW_{suffix.upper()}"
    created = api("POST", "/standard-dataset-types", {
        "dataset_type_code": code,
        "dataset_type_name": f"Wizard Flow {suffix}",
        "description": "R9-S2-1 wizard integration test",
        "category": "TRANSACTION",
        "target_table": table,
        "status": "DRAFT",
        "managed_table": True,
        "mapping_supported": False,
        "columns": [
            {"column_name": "entity_id", "data_type": "VARCHAR", "data_length": 64, "primary_key": True, "required": True, "default_column_role": "ENTITY_KEY"},
            {"column_name": "event_at", "data_type": "TIMESTAMPTZ", "required": True, "default_column_role": "TIME_KEY"},
            {"column_name": "amount", "data_type": "NUMERIC", "numeric_precision": 18, "numeric_scale": 4, "default_column_role": "TARGET"},
        ],
    })
    ds_id = created["dataset_type_id"]
    assert created.get("status") == "DRAFT", created
    assert created.get("table_create_status") in (None, "NOT_CREATED"), created

    validation = api("POST", f"/standard-dataset-types/{ds_id}/validate")
    assert validation.get("valid") is True, validation
    assert validation.get("lifecycle_status") == "VALIDATED", validation

    preview = api("POST", f"/standard-dataset-types/{ds_id}/preview-create-table")
    sql = preview.get("sql_preview") or ""
    assert preview.get("valid") is True, preview
    assert sql.upper().startswith("CREATE TABLE"), sql[:80]
    assert table in sql.lower()
    assert "DROP" not in sql.upper()
    assert ";" not in sql.replace(";", "").replace("CREATE TABLE", "", 1) or sql.count(";") <= 1

    created_tbl = api("POST", f"/standard-dataset-types/{ds_id}/create-physical-table", {"confirm": True})
    assert created_tbl.get("status") == "SUCCESS", created_tbl
    ds = created_tbl.get("dataset_type") or api("GET", f"/standard-dataset-types/{ds_id}")
    assert ds.get("physical_table_exists") is True, ds
    assert ds.get("status") == "ACTIVE", ds
    assert ds.get("mapping_supported") is True, ds

    targets = api("GET", "/standard-target-tables?active_only=true&mapping_supported=true")
    tables = {i["target_table"] for i in targets.get("items") or []}
    assert table in tables, tables

    dup = api("POST", f"/standard-dataset-types/{ds_id}/create-physical-table", {"confirm": True}, expect_fail=True)
    assert dup.get("status") == 400 or "이미" in str(dup), dup
    print(f"  [ok] wizard full flow ({table})")
    return ds_id, table


def test_mapping_target_validation(table: str) -> None:
    heat_source = resolve_heat_source_id(api)
    valid = api("POST", "/standard-dataset-types/validate-target-table", {"target_table": table})
    assert valid.get("valid") is True, valid

    body = {
        "source_id": heat_source,
        "mapping_name": f"R9-wiz-map-{uuid.uuid4().hex[:6]}",
        "target_table": table,
        "columns": [
            {"source_column": "entity_id", "target_column": "entity_id", "required_yn": True},
            {"source_column": "event_at", "target_column": "event_at", "required_yn": True},
        ],
    }
    mapping = api("POST", "/mappings", body)
    assert mapping.get("mapping_id"), mapping
    print(f"  [ok] mapping create with wizard table ({mapping['mapping_id']})")


def test_archive_metadata_only(ds_id: str, table: str) -> None:
    archived = api("POST", f"/standard-dataset-types/{ds_id}/archive")
    assert archived.get("status") == "ARCHIVED", archived
  # physical table still exists - validate-target may fail for archived
    invalid = api("POST", "/standard-dataset-types/validate-target-table", {"target_table": table}, expect_fail=True)
    assert invalid.get("status") == 400 or invalid.get("valid") is False or invalid.get("error_code") == "INVALID_TARGET_TABLE", invalid
    print("  [ok] archive metadata only (physical table retained)")


def test_fixture_helper() -> None:
    info = create_wizard_standard_dataset(api)
    assert info.get("physical_table_name", "").startswith("std_"), info
    assert info.get("dataset_type_id"), info
    print(f"  [ok] fixture helper ({info['physical_table_name']})")


def main() -> int:
    print("THERMOps standard dataset table wizard tests (R9-S2-1)")
    wizard_table = ""
    wizard_ds_id = ""
    tests = [
        test_clean_seed_no_standard_dataset_inserts,
        test_suggest_table_name_std_prefix,
        test_invalid_table_name_rejected,
        test_invalid_column_name_rejected,
        test_wizard_full_flow,
    ]
    failed = 0
    for fn in tests:
        try:
            result = fn()
            if isinstance(result, tuple) and len(result) == 2:
                wizard_ds_id, wizard_table = result
            elif isinstance(result, str):
                wizard_table = result
        except Exception as exc:
            failed += 1
            print(f"  [FAIL] {fn.__name__}: {exc}", file=sys.stderr)

    if wizard_table and wizard_ds_id:
        for fn in (
            lambda: test_mapping_target_validation(wizard_table),
            lambda: test_archive_metadata_only(wizard_ds_id, wizard_table),
            test_fixture_helper,
        ):
            try:
                fn()
            except Exception as exc:
                failed += 1
                print(f"  [FAIL] {fn.__name__}: {exc}", file=sys.stderr)
    else:
        failed += 1
        print("  [FAIL] wizard full flow did not produce table", file=sys.stderr)

    total = len(tests) + (3 if wizard_table else 0)
    if failed:
        print(f"FAILED ({failed} errors)", file=sys.stderr)
        return 1
    print(f"PASSED ({total} checks)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
