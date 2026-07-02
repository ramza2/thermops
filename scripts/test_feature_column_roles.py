#!/usr/bin/env python3
"""Feature Column Role API 테스트 (Phase R1)."""

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
from test_fixtures import heat_pipeline_node_config, resolve_heat_mapping_id

API_BASE = os.environ.get("THERMOOPS_API_BASE", "http://localhost:8000/api/v1")
HEAT_MAPPING_ID = ""


def api(method: str, path: str, body: dict | None = None) -> dict | list:
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
        raise RuntimeError(f"HTTP {exc.code} {method} {path}: {detail}") from exc
    if not payload.get("success"):
        raise RuntimeError(f"API failed {method} {path}: {payload}")
    return payload["data"]


def test_role_codes() -> None:
    data = api("GET", "/feature-column-role-codes")
    items = data.get("items") or []
    codes = {i["code"] for i in items}
    assert "ENTITY_KEY" in codes, codes
    assert "TIME_KEY" in codes, codes
    assert "TARGET" in codes, codes
    print(f"  [ok] role codes ({len(items)}개)")


def test_inference() -> None:
    body = {
        "columns": [
            {"source_column": "site_id", "target_column": "site_id", "data_type": "STRING"},
            {"source_column": "measured_at", "target_column": "measured_at", "data_type": "DATETIME"},
            {"source_column": "heat_demand", "target_column": "heat_demand", "data_type": "NUMERIC"},
            {"source_column": "temperature", "target_column": "temperature", "data_type": "NUMERIC"},
            {"source_column": "is_weekend", "target_column": "is_weekend", "data_type": "STRING"},
        ],
        "target_table": "heat_demand_actual",
    }
    data = api("POST", "/feature-column-roles/infer", body)
    by_src = {i["source_column"]: i for i in data["items"]}
    assert by_src["site_id"]["column_role"] == "ENTITY_KEY", by_src["site_id"]
    assert by_src["measured_at"]["column_role"] in ("TIME_KEY", "DATETIME"), by_src["measured_at"]
    assert by_src["heat_demand"]["column_role"] in ("TARGET", "NUMERIC_INPUT"), by_src["heat_demand"]
    assert by_src["temperature"]["column_role"] in ("NUMERIC_INPUT", "MEASURE"), by_src["temperature"]
    assert by_src["is_weekend"]["column_role"] == "BOOLEAN_INPUT", by_src["is_weekend"]
    print("  [ok] inference rules")


def test_validate_ok() -> None:
    roles = [
        {"source_column": "site_id", "target_column": "site_id", "column_role": "ENTITY_KEY"},
        {"source_column": "measured_at", "target_column": "measured_at", "column_role": "TIME_KEY"},
        {"source_column": "heat_demand", "target_column": "heat_demand", "column_role": "TARGET"},
        {"source_column": "supply_temp", "target_column": "supply_temp", "column_role": "NUMERIC_INPUT"},
    ]
    data = api("POST", "/feature-column-roles/validate", {"roles": roles})
    v = data["validation"]
    assert v["valid"] is True, v
    assert data["summary"]["recipe_readiness"]["time_series"]["ready"] is True
    print("  [ok] validate OK (time_series ready)")


def test_validate_warnings() -> None:
    roles = [
        {"source_column": "site_id", "target_column": "site_id", "column_role": "ENTITY_KEY"},
        {"source_column": "measured_at", "target_column": "measured_at", "column_role": "TIME_KEY"},
    ]
    data = api("POST", "/feature-column-roles/validate", {"roles": roles})
    v = data["validation"]
    assert v["valid"] is True, v
    assert any("TARGET" in w for w in v["warnings"]), v
    print("  [ok] validate warning (no TARGET)")


def test_validate_error_time_keys() -> None:
    roles = [
        {"source_column": "site_id", "target_column": "site_id", "column_role": "ENTITY_KEY"},
        {"source_column": "measured_at", "target_column": "measured_at", "column_role": "TIME_KEY"},
        {"source_column": "created_at", "target_column": "created_at", "column_role": "TIME_KEY"},
    ]
    data = api("POST", "/feature-column-roles/validate", {"roles": roles})
    v = data["validation"]
    assert v["valid"] is False, v
    assert v.get("blocking") is True, v
    assert any("TIME_KEY" in e for e in v["errors"]), v
    print("  [ok] validate error (TIME_KEY 2개)")


def test_validate_invalid_enum() -> None:
    roles = [{"source_column": "x", "column_role": "INVALID_ROLE"}]
    data = api("POST", "/feature-column-roles/validate", {"roles": roles})
    v = data["validation"]
    assert v["valid"] is False, v
    print("  [ok] validate error (invalid enum)")


def test_get_with_inferred() -> None:
    data = api(
        "GET",
        f"/feature-column-roles?{urllib.parse.urlencode({'mapping_id': HEAT_MAPPING_ID, 'include_inferred': 'true'})}",
    )
    items = data.get("items") or []
    assert len(items) >= 3, items
    roles = {i.get("column_role") for i in items if i.get("column_role")}
    assert "ENTITY_KEY" in roles or "TIME_KEY" in roles, roles
    assert "summary" in data and "validation" in data
    readiness = data["summary"]["recipe_readiness"]
    assert "time_series" in readiness
    print(f"  [ok] GET include_inferred ({len(items)} rows)")


def test_bulk_upsert() -> None:
    suffix = uuid.uuid4().hex[:4]
    mapping_id = HEAT_MAPPING_ID
    roles = [
        {
            "source_column": "site_id",
            "target_column": "site_id",
            "data_type": "STRING",
            "column_role": "ENTITY_KEY",
            "description": f"test {suffix}",
        },
        {
            "source_column": "measured_at",
            "target_column": "measured_at",
            "data_type": "DATETIME",
            "column_role": "TIME_KEY",
        },
        {
            "source_column": "heat_demand",
            "target_column": "heat_demand",
            "data_type": "NUMERIC",
            "column_role": "TARGET",
        },
        {
            "source_column": "supply_temp",
            "target_column": "supply_temp",
            "data_type": "NUMERIC",
            "column_role": "NUMERIC_INPUT",
        },
    ]
    saved = api("PUT", "/feature-column-roles", {"mapping_id": mapping_id, "roles": roles})
    assert saved["saved_count"] >= 4, saved
    assert saved["validation"]["valid"] is True, saved["validation"]

    fetched = api(
        "GET",
        f"/feature-column-roles?{urllib.parse.urlencode({'mapping_id': mapping_id})}",
    )
    by_src = {i["source_column"]: i for i in fetched["items"]}
    assert by_src["site_id"]["column_role"] == "ENTITY_KEY"
    assert by_src["heat_demand"]["column_role"] == "TARGET"
    print("  [ok] bulk upsert + GET")


def test_bulk_upsert_blocks_double_time_key() -> None:
    mapping_id = HEAT_MAPPING_ID
    roles = [
        {"source_column": "site_id", "target_column": "site_id", "column_role": "ENTITY_KEY"},
        {"source_column": "measured_at", "target_column": "measured_at", "column_role": "TIME_KEY"},
        {"source_column": "supply_temp", "target_column": "supply_temp", "column_role": "TIME_KEY"},
    ]
    try:
        api("PUT", "/feature-column-roles", {"mapping_id": mapping_id, "roles": roles})
        raise AssertionError("expected HTTP 400 for double TIME_KEY")
    except RuntimeError as exc:
        assert "400" in str(exc) or "TIME_KEY" in str(exc), exc
    print("  [ok] bulk upsert blocks TIME_KEY 2개")


def test_ratio_readiness() -> None:
    roles = [
        {"source_column": "a", "column_role": "NUMERIC_INPUT"},
        {"source_column": "b", "column_role": "NUMERIC_INPUT"},
    ]
    data = api("POST", "/feature-column-roles/validate", {"roles": roles})
    assert data["summary"]["recipe_readiness"]["ratio"]["ready"] is True
    print("  [ok] ratio readiness")


def main() -> int:
    global HEAT_MAPPING_ID
    print("test_feature_column_roles.py")
    HEAT_MAPPING_ID = resolve_heat_mapping_id(api)
    print(f"  [fixture] heat mapping={HEAT_MAPPING_ID}")
    tests = [
        test_role_codes,
        test_inference,
        test_validate_ok,
        test_validate_warnings,
        test_validate_error_time_keys,
        test_validate_invalid_enum,
        test_get_with_inferred,
        test_bulk_upsert,
        test_bulk_upsert_blocks_double_time_key,
        test_ratio_readiness,
    ]
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
    print("PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
