#!/usr/bin/env python3
"""표준 데이터셋 유형 / 대상 테이블 allowlist 테스트 (Phase R7)."""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))
from test_fixtures import resolve_heat_source_id

API_BASE = os.environ.get("THERMOOPS_API_BASE", "http://localhost:8000/api/v1")
HEAT_SOURCE_ID = ""


def api(method: str, path: str, body: dict | None = None, expect_fail: bool = False) -> dict | list:
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
                return json.loads(detail)
            except json.JSONDecodeError:
                return {"detail": detail, "status": exc.code}
        raise RuntimeError(f"HTTP {exc.code} {method} {path}: {detail}") from exc
    if not payload.get("success"):
        raise RuntimeError(f"API failed {method} {path}: {payload}")
    return payload["data"]


def test_list_dataset_types() -> None:
    data = api("GET", "/standard-dataset-types?include_columns=false")
    items = data.get("items") or []
    assert len(items) >= 5, len(items)
    codes = {i["dataset_type_code"] for i in items}
    assert "HEAT_DEMAND_ACTUAL" in codes, codes
    print(f"  [ok] standard dataset list ({len(items)}건)")


def test_target_tables_active_only() -> None:
    data = api("GET", "/standard-target-tables?active_only=true&mapping_supported=true")
    items = data.get("items") or []
    assert items, items
    tables = {i["target_table"] for i in items}
    assert "heat_demand_actual" in tables or "tb_heat_demand_actual" in tables, tables
    for item in items:
        assert item.get("standard_columns"), item
    planned = api("GET", "/standard-dataset-types?status=PLANNED")
    planned_tables = {i["target_table"] for i in planned.get("items") or []}
    assert not tables.intersection(planned_tables), (tables, planned_tables)
    print(f"  [ok] mapping target tables ({len(items)}건, PLANNED 제외)")


def test_heat_columns_and_validate() -> None:
    detail = api("GET", "/standard-dataset-types/DST-HEAT-DEMAND-ACTUAL?include_columns=true")
    cols = {c["column_name"] for c in detail.get("columns") or []}
    assert {"site_id", "measured_at", "heat_demand"}.issubset(cols), cols
    valid = api("POST", "/standard-dataset-types/validate-target-table", {"target_table": "heat_demand_actual"})
    assert valid.get("valid") is True, valid
    print("  [ok] HEAT columns + validate-target-table success")


def test_validate_invalid() -> None:
    resp = api(
        "POST",
        "/standard-dataset-types/validate-target-table",
        {"target_table": "tb_custom_random_table"},
        expect_fail=True,
    )
    detail = resp.get("detail") if isinstance(resp.get("detail"), dict) else resp
    if isinstance(detail, dict):
        assert detail.get("error_code") == "INVALID_TARGET_TABLE" or detail.get("valid") is False, detail
    else:
        assert "INVALID_TARGET_TABLE" in str(resp) or resp.get("status") == 400, resp
    print("  [ok] validate-target-table invalid")


def test_mapping_create_invalid_blocked() -> None:
    body = {
        "source_id": HEAT_SOURCE_ID,
        "mapping_name": f"R7-invalid-{uuid.uuid4().hex[:6]}",
        "target_table": "tb_not_allowed_table_xyz",
        "columns": [{"source_column": "a", "target_column": "b", "required_yn": False}],
    }
    resp = api("POST", "/mappings", body, expect_fail=True)
    detail = resp.get("detail") if isinstance(resp.get("detail"), dict) else resp
    assert resp.get("status") == 400 or detail.get("error_code") == "INVALID_TARGET_TABLE", resp
    print("  [ok] mapping create invalid target_table blocked")


def test_mapping_create_valid() -> None:
    body = {
        "source_id": HEAT_SOURCE_ID,
        "mapping_name": f"R7-valid-{uuid.uuid4().hex[:6]}",
        "target_table": "heat_demand_actual",
        "columns": [
            {"source_column": "site_id", "target_column": "site_id", "required_yn": True},
            {"source_column": "measured_at", "target_column": "measured_at", "required_yn": True},
            {"source_column": "heat_demand", "target_column": "heat_demand", "required_yn": True},
        ],
    }
    data = api("POST", "/mappings", body)
    assert data.get("mapping_id"), data
    print(f"  [ok] mapping create valid ({data['mapping_id']})")


def test_infer_standard_roles() -> None:
    body = {
        "target_table": "heat_demand_actual",
        "columns": [
            {"source_column": "site_id", "target_column": "site_id", "data_type": "STRING"},
            {"source_column": "measured_at", "target_column": "measured_at", "data_type": "DATETIME"},
            {"source_column": "heat_demand", "target_column": "heat_demand", "data_type": "NUMERIC"},
        ],
    }
    data = api("POST", "/feature-column-roles/infer", body)
    by_src = {i["source_column"]: i for i in data["items"]}
    assert by_src["site_id"]["column_role"] == "ENTITY_KEY", by_src["site_id"]
    assert by_src["measured_at"]["column_role"] == "TIME_KEY", by_src["measured_at"]
    assert by_src["heat_demand"]["column_role"] == "TARGET", by_src["heat_demand"]
    print("  [ok] infer uses standard column default roles")


def test_recipe_availability_on_detail() -> None:
    detail = api(
        "GET",
        "/standard-dataset-types/DST-HEAT-DEMAND-ACTUAL?include_recipe_availability=true",
    )
    readiness = detail.get("recipe_readiness")
    assert readiness and readiness.get("templates"), readiness
    print(f"  [ok] recipe availability ({readiness.get('available_count')} templates)")


def test_activate_missing_physical_fails() -> None:
    types = api("GET", "/standard-dataset-types?status=PLANNED")
    facility = next((i for i in types.get("items") or [] if i["dataset_type_code"] == "FACILITY_MASTER"), None)
    if not facility:
        print("  [skip] FACILITY_MASTER seed 없음")
        return
    resp = api(
        "POST",
        f"/standard-dataset-types/{facility['dataset_type_id']}/activate",
        expect_fail=True,
    )
    assert resp.get("status") == 400 or "물리 테이블" in str(resp), resp
    print("  [ok] activate without physical table fails")


def main() -> int:
    global HEAT_SOURCE_ID
    HEAT_SOURCE_ID = resolve_heat_source_id(api)
    print(f"  [fixture] heat source={HEAT_SOURCE_ID}")
    tests = [
        test_list_dataset_types,
        test_target_tables_active_only,
        test_heat_columns_and_validate,
        test_validate_invalid,
        test_mapping_create_invalid_blocked,
        test_mapping_create_valid,
        test_infer_standard_roles,
        test_recipe_availability_on_detail,
        test_activate_missing_physical_fails,
    ]
    print("THERMOps standard datasets tests (R7)")
    failed = 0
    for fn in tests:
        try:
            fn()
        except Exception as exc:
            failed += 1
            print(f"  [FAIL] {fn.__name__}: {exc}", file=sys.stderr)
    if failed:
        print(f"FAILED ({failed}/{len(tests)})", file=sys.stderr)
        return 1
    print(f"PASSED ({len(tests)}/{len(tests)})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
