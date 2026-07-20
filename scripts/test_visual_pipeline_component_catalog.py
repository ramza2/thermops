#!/usr/bin/env python3
"""R11-S1 Visual Pipeline component catalog / contract API tests.

Primary: service direct (no DB).
Optional: HTTP smoke when backend is reachable at BASE_URL.
"""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent
_BACKEND = _SCRIPTS.parent / "backend"
for p in (str(_SCRIPTS), str(_BACKEND)):
    if p not in sys.path:
        sys.path.insert(0, p)

from app.services.visual_pipeline.component_catalog_service import (  # noqa: E402
    ACTIVE_COMPONENT_TYPES,
    COMPONENT_CONTRACT_VERSION,
    DISABLED_COMPONENT_TYPES,
    get_component,
    list_components,
    list_connection_rules,
)

BASE_URL = "http://localhost:8000"
API = f"{BASE_URL}/api/v1"

ACTIVE_EXPECTED = {
    "VP_REST_API_SOURCE",
    "VP_TRANSFORM",
    "VP_UPSERT_LOAD",
    "VP_CRON_SCHEDULE",
}
DISABLED_EXPECTED = {
    "VP_NOTIFICATION",
    "VP_DATA_QUALITY",
    "VP_FEATURE_BUILD",
    "VP_MODEL_TRAINING",
    "VP_BATCH_PREDICTION",
    "VP_FORECAST_PROVIDER",
    "VP_DB_SOURCE",
    "VP_CSV_SOURCE",
}
TRANSFORM_TYPES = {
    "NONE",
    "WIDE_HOUR_TO_LONG",
    "ASOS_HOURLY_TO_CANONICAL",
    "CALENDAR_SPECIAL_DAY_TO_DATE",
    "CALENDAR_DATE_TO_HOUR",
}
UPSERT_REQUIRED_FIELDS = {
    "write_mode",
    "conflict_key_columns_json",
    "duplicate_within_batch_policy",
    "null_update_policy",
    "target_table",
}
FORBIDDEN_FIELD_ALIASES = {"batch_duplicate_policy", "conflict_keys"}
ALLOW_RULE_IDS = {
    "ALLOW_SOURCE_TO_TRANSFORM",
    "ALLOW_TRANSFORM_TO_LOAD",
    "ALLOW_SOURCE_TO_LOAD",
    "ALLOW_CRON_TO_SOURCE_TRIGGER",
}
DENY_RULE_IDS = {
    "DENY_LOAD_TO_CRON",
    "DENY_NOTIFICATION_TO_TRANSFORM",
    "DENY_FEATURE_TO_LOAD",
}


def _config_field_names(component: dict) -> set[str]:
    return {f["name"] for f in component.get("config_schema") or [] if isinstance(f, dict) and "name" in f}


def _field_values(component: dict, name: str) -> list[str]:
    for f in component.get("config_schema") or []:
        if isinstance(f, dict) and f.get("name") == name:
            return list(f.get("values") or [])
    return []


def run_service_tests() -> None:
    print("  [service] list_components")
    catalog = list_components()
    assert catalog["contract_version"] == COMPONENT_CONTRACT_VERSION
    items = catalog["items"]
    assert catalog["total"] == len(items) == 12, f"expected 12 components, got {catalog['total']}"

    by_type = {c["component_type"]: c for c in items}
    for t in ACTIVE_EXPECTED:
        assert t in by_type, f"missing ACTIVE {t}"
        assert by_type[t]["status"] == "ACTIVE"
    for t in DISABLED_EXPECTED:
        assert t in by_type, f"missing DISABLED {t}"
        assert by_type[t]["status"] == "DISABLED"
        assert by_type[t].get("disabled_reason"), f"{t} needs disabled_reason"

    assert set(ACTIVE_COMPONENT_TYPES) == ACTIVE_EXPECTED
    assert set(DISABLED_COMPONENT_TYPES) == DISABLED_EXPECTED
    print("  [ok] ACTIVE 4 + DISABLED 8")

    for t in ACTIVE_EXPECTED:
        c = by_type[t]
        assert "input_ports" in c and "output_ports" in c
        assert c.get("compile_role"), f"{t} missing compile_role"
        assert c.get("execution_adapter"), f"{t} missing execution_adapter"
        assert isinstance(c.get("config_schema"), list), f"{t} config_schema must be list"
        print(f"  [ok] contract fields {t}")

    load = by_type["VP_UPSERT_LOAD"]
    names = _config_field_names(load)
    for f in UPSERT_REQUIRED_FIELDS:
        assert f in names, f"VP_UPSERT_LOAD missing {f}"
    for bad in FORBIDDEN_FIELD_ALIASES:
        assert bad not in names, f"forbidden alias {bad} present"
    print("  [ok] UPSERT R10 field names")

    transform = by_type["VP_TRANSFORM"]
    tvals = set(_field_values(transform, "transform_type"))
    assert TRANSFORM_TYPES <= tvals, f"transform_type missing {TRANSFORM_TYPES - tvals}"
    print("  [ok] TRANSFORM types")

    cron = by_type["VP_CRON_SCHEDULE"]
    assert set(_field_values(cron, "schedule_type")) == {"CRON"}
    cron_names = _config_field_names(cron)
    assert "cron_expression" in cron_names and "timezone" in cron_names
    assert "max_retry_count" in cron_names
    print("  [ok] CRON schedule_type=CRON")

    source = by_type["VP_REST_API_SOURCE"]
    assert any(p.get("port_id") == "raw_rows" for p in source["output_ports"])
    assert any(p.get("port_id") == "trigger" for p in source["input_ports"])
    src_names = _config_field_names(source)
    assert "endpoint_path" in src_names and "http_method" in src_names
    assert "endpoint_url" not in src_names
    print("  [ok] SOURCE ports and R10 field names")

    print("  [service] get_component")
    one = get_component("vp_upsert_load")
    assert one["component_type"] == "VP_UPSERT_LOAD"
    try:
        get_component("VP_DOES_NOT_EXIST")
        raise AssertionError("expected LookupError")
    except LookupError as exc:
        assert "COMPONENT_NOT_FOUND" in str(exc)
    print("  [ok] get_component + 404 LookupError")

    print("  [service] list_connection_rules")
    rules = list_connection_rules()
    assert rules["total"] >= 7
    by_id = {r["rule_id"]: r for r in rules["items"]}
    for rid in ALLOW_RULE_IDS:
        assert rid in by_id and by_id[rid]["allowed"] is True, rid
    for rid in DENY_RULE_IDS:
        assert rid in by_id and by_id[rid]["allowed"] is False, rid
    assert rules.get("cardinality_rules"), "cardinality_rules required"
    print("  [ok] connection rules allow/deny + cardinality")

    filtered = list_components(status="ACTIVE")
    assert filtered["total"] == 4
    filtered2 = list_components(category="DATA_INPUT")
    assert all(c["category"] == "DATA_INPUT" for c in filtered2["items"])
    print("  [ok] status/category filters")


def _http_get(path: str) -> tuple[int, dict | None]:
    url = f"{API}{path}"
    try:
        with urllib.request.urlopen(url, timeout=5) as resp:
            body = json.loads(resp.read().decode("utf-8"))
            return resp.status, body
    except urllib.error.HTTPError as e:
        try:
            body = json.loads(e.read().decode("utf-8"))
        except Exception:
            body = None
        return e.code, body
    except Exception as exc:
        return -1, {"error": str(exc)}


def run_http_smoke() -> str:
    """Return 'PASS', 'SKIP', or raise on failure when backend is up."""
    code, health = _http_get_health()
    if code != 200:
        print(f"  [skip] HTTP smoke (backend not reachable, health={code})")
        return "SKIP"

    print("  [http] GET /visual-pipelines/components")
    status, body = _http_get("/visual-pipelines/components")
    assert status == 200, f"components status={status} body={body}"
    assert body and body.get("success") is True
    data = body["data"]
    assert data["total"] == 12
    types = {c["component_type"] for c in data["items"]}
    assert ACTIVE_EXPECTED <= types
    assert DISABLED_EXPECTED <= types
    print("  [ok] HTTP components")

    status, body = _http_get("/visual-pipelines/components/VP_TRANSFORM")
    assert status == 200 and body["data"]["component_type"] == "VP_TRANSFORM"
    print("  [ok] HTTP component detail")

    status, body = _http_get("/visual-pipelines/components/VP_DOES_NOT_EXIST")
    assert status == 404, f"expected 404, got {status}"
    print("  [ok] HTTP 404")

    status, body = _http_get("/visual-pipelines/connection-rules")
    assert status == 200
    assert body["data"]["total"] >= 7
    print("  [ok] HTTP connection-rules")
    return "PASS"


def _http_get_health() -> tuple[int, dict | None]:
    try:
        with urllib.request.urlopen(f"{BASE_URL}/health", timeout=3) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except Exception:
        return -1, None


def main() -> int:
    print("THERMOps R11-S1 Visual Pipeline component catalog test")
    try:
        run_service_tests()
        http_result = run_http_smoke()
        print(f"PASS (service=ok, http={http_result})")
        return 0
    except AssertionError as exc:
        print(f"FAIL: {exc}")
        return 1
    except Exception as exc:
        print(f"FAIL: {type(exc).__name__}: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
