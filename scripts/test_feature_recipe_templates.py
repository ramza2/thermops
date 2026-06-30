#!/usr/bin/env python3
"""Feature Recipe Template Catalog 및 Validate API 테스트 (Phase R2)."""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

API_BASE = os.environ.get("THERMOOPS_API_BASE", "http://localhost:8000/api/v1")
HEAT_MAPPING_ID = os.environ.get("THERMOOPS_HEAT_MAPPING_ID", "MAP-CSV-001")
WEATHER_MAPPING_ID = os.environ.get("THERMOOPS_WEATHER_MAPPING_ID", "MAP-CSV-002")

REQUIRED_TYPES = frozenset({
    "RAW_COLUMN",
    "DATE_PART",
    "LAG",
    "ROLLING_MEAN",
    "ROLLING_SUM",
    "DIFF",
    "RATIO",
    "BINNING",
    "FILL_NULL",
    "CATEGORY_ENCODING",
})


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


def test_list_templates() -> None:
    data = api("GET", "/feature-recipe-templates")
    items = data.get("items") or []
    types = {i["recipe_type"] for i in items}
    assert REQUIRED_TYPES.issubset(types), sorted(types)
    assert data["summary"]["total_count"] >= len(REQUIRED_TYPES)
    print(f"  [ok] template catalog ({len(items)}개)")


def test_get_lag_detail() -> None:
    data = api("GET", "/feature-recipe-templates/LAG")
    assert data["recipe_type"] == "LAG"
    assert "param_schema" in data
    assert data["leakage_policy"] == "SHIFT_REQUIRED"
    print("  [ok] LAG template detail")


def test_availability_with_mapping() -> None:
    data = api(
        "GET",
        f"/feature-recipe-templates?{urllib.parse.urlencode({'mapping_id': HEAT_MAPPING_ID, 'include_availability': 'true'})}",
    )
    by_type = {i["recipe_type"]: i for i in data["items"]}
    assert by_type["LAG"]["available"] is True, by_type["LAG"]
    assert by_type["ROLLING_MEAN"]["available"] is True, by_type["ROLLING_MEAN"]
    assert data["summary"]["available_count"] >= 5
    print(f"  [ok] mapping availability ({data['summary']['available_count']} available)")


def test_validate_raw_column() -> None:
    body = {
        "mapping_id": HEAT_MAPPING_ID,
        "recipe_type": "RAW_COLUMN",
        "source_columns": ["site_id"],
    }
    data = api("POST", "/feature-recipes/validate", body)
    assert data["valid"] is True, data
    assert data["output_feature_name"] == "site_id"
    print("  [ok] validate RAW_COLUMN")


def test_validate_date_part() -> None:
    body = {
        "mapping_id": HEAT_MAPPING_ID,
        "recipe_type": "DATE_PART",
        "source_columns": ["measured_at"],
        "time_key": "measured_at",
        "params": {"parts": ["week_of_year"]},
    }
    data = api("POST", "/feature-recipes/validate", body)
    assert data["valid"] is True, data
    assert data["generated_feature_name"] == "measured_at_week_of_year", data
    print("  [ok] validate DATE_PART")


def test_validate_lag() -> None:
    body = {
        "mapping_id": HEAT_MAPPING_ID,
        "recipe_type": "LAG",
        "source_columns": ["heat_demand"],
        "entity_keys": ["site_id"],
        "time_key": "measured_at",
        "target_column": "heat_demand",
        "params": {"offset_steps": 24, "granularity": "1h", "include_current_row": False},
    }
    data = api("POST", "/feature-recipes/validate", body)
    assert data["valid"] is True, data
    assert data["generated_feature_name"] == "heat_demand_lag_24h", data
    assert data["lineage_preview"]["calc_method"] == "TEMPLATE"
    print("  [ok] validate LAG + generated_feature_name")


def test_validate_ratio_insufficient() -> None:
    body = {
        "mapping_id": HEAT_MAPPING_ID,
        "recipe_type": "RATIO",
        "source_columns": ["heat_demand"],
        "params": {"epsilon": 1e-9},
    }
    data = api("POST", "/feature-recipes/validate", body)
    assert data["valid"] is False, data
    codes = {e["code"] for e in data["errors"]}
    assert "INVALID_SOURCE_COUNT" in codes, data["errors"]
    print("  [ok] validate RATIO insufficient columns")


def test_validate_ratio_success() -> None:
    body = {
        "mapping_id": WEATHER_MAPPING_ID,
        "recipe_type": "RATIO",
        "source_columns": ["rainfall", "wind_speed"],
        "params": {"epsilon": 1e-9},
    }
    data = api("POST", "/feature-recipes/validate", body)
    assert data["valid"] is True, data
    assert data["generated_feature_name"] == "rainfall_over_wind_speed"
    print("  [ok] validate RATIO success")


def test_validate_rolling_leakage_warning() -> None:
    body = {
        "mapping_id": HEAT_MAPPING_ID,
        "recipe_type": "ROLLING_MEAN",
        "source_columns": ["heat_demand"],
        "entity_keys": ["site_id"],
        "time_key": "measured_at",
        "target_column": "heat_demand",
        "params": {"window_steps": 24, "granularity": "1h", "include_current_row": True},
    }
    data = api("POST", "/feature-recipes/validate", body)
    assert any("누수" in w for w in data.get("warnings", [])), data
    print("  [ok] rolling leakage warning")


def test_validate_invalid_recipe_type() -> None:
    data = api("POST", "/feature-recipes/validate", {"recipe_type": "NOPE", "source_columns": ["x"]})
    assert data["valid"] is False
    assert any(e["code"] == "UNKNOWN_RECIPE_TYPE" for e in data["errors"])
    print("  [ok] invalid recipe_type")


def test_validate_duplicate_feature_name() -> None:
    body = {
        "mapping_id": WEATHER_MAPPING_ID,
        "recipe_type": "RAW_COLUMN",
        "source_columns": ["temperature"],
        "output_feature_name": "temperature",
    }
    data = api("POST", "/feature-recipes/validate", body)
    assert data["valid"] is False, data
    assert any(e["code"] == "DUPLICATE_FEATURE_NAME" for e in data["errors"]), data["errors"]
    print("  [ok] duplicate feature_name error")


def test_validate_param_offset_zero() -> None:
    body = {
        "mapping_id": HEAT_MAPPING_ID,
        "recipe_type": "LAG",
        "source_columns": ["heat_demand"],
        "entity_keys": ["site_id"],
        "time_key": "measured_at",
        "params": {"offset_steps": 0, "granularity": "1h"},
    }
    data = api("POST", "/feature-recipes/validate", body)
    assert data["valid"] is False
    assert any(e["code"] == "INVALID_PARAM" for e in data["errors"])
    print("  [ok] param offset_steps=0 error")


def test_validate_bins_unsorted() -> None:
    body = {
        "mapping_id": HEAT_MAPPING_ID,
        "recipe_type": "BINNING",
        "source_columns": ["heat_demand"],
        "params": {"strategy": "custom", "bins": [10, 5, 20]},
    }
    data = api("POST", "/feature-recipes/validate", body)
    assert data["valid"] is False
    assert any(e["code"] == "INVALID_PARAM" for e in data["errors"])
    print("  [ok] bins unsorted error")


def test_lag_unavailable_without_roles() -> None:
    body = {
        "recipe_type": "LAG",
        "source_columns": ["heat_demand"],
        "params": {"offset_steps": 24, "granularity": "1h"},
    }
    data = api("POST", "/feature-recipes/validate", body)
    assert data["valid"] is True, data
    print("  [ok] validate LAG without mapping roles (no role block)")


def main() -> int:
    print("test_feature_recipe_templates.py")
    tests = [
        test_list_templates,
        test_get_lag_detail,
        test_availability_with_mapping,
        test_validate_raw_column,
        test_validate_date_part,
        test_validate_lag,
        test_validate_ratio_insufficient,
        test_validate_ratio_success,
        test_validate_rolling_leakage_warning,
        test_validate_invalid_recipe_type,
        test_validate_duplicate_feature_name,
        test_validate_param_offset_zero,
        test_validate_bins_unsorted,
        test_lag_unavailable_without_roles,
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
