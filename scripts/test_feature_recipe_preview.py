#!/usr/bin/env python3
"""Feature Recipe Preview API 테스트 (Phase R3–R4)."""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

API_BASE = os.environ.get("THERMOOPS_API_BASE", "http://localhost:8000/api/v1")
HEAT_MAPPING_ID = os.environ.get("THERMOOPS_HEAT_MAPPING_ID", "MAP-CSV-001")
WEATHER_MAPPING_ID = os.environ.get("THERMOOPS_WEATHER_MAPPING_ID", "MAP-CSV-002")


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


def test_raw_column_preview() -> None:
    body = {
        "mapping_id": HEAT_MAPPING_ID,
        "recipe_type": "RAW_COLUMN",
        "source_columns": ["heat_demand"],
        "sample_size": 50,
    }
    data = api("POST", "/feature-recipes/preview", body)
    assert data["supported"] is True, data
    assert data["valid"] is True, data
    assert data["stats"]["row_count"] > 0, data
    assert len(data["preview_rows"]) > 0, data
    assert "heat_demand" in data["preview_rows"][0], data["preview_rows"][0]
    assert data["preview_id"].startswith("PREVIEW-LOCAL-")
    print("  [ok] RAW_COLUMN preview")


def test_date_part_preview() -> None:
    body = {
        "mapping_id": HEAT_MAPPING_ID,
        "recipe_type": "DATE_PART",
        "source_columns": ["measured_at"],
        "time_key": "measured_at",
        "params": {"parts": ["hour", "day_of_week"]},
        "sample_size": 100,
    }
    data = api("POST", "/feature-recipes/preview", body)
    assert data["valid"] is True, data
    names = data.get("generated_feature_names") or []
    assert "hour" in names and "day_of_week" in names, names
    assert data["stats"]["row_count"] > 0
    row = data["preview_rows"][0]
    assert "hour" in row and "day_of_week" in row, row
    print("  [ok] DATE_PART preview (hour, day_of_week)")


def test_date_part_reusable_validate() -> None:
    body = {
        "mapping_id": HEAT_MAPPING_ID,
        "recipe_type": "DATE_PART",
        "source_columns": ["measured_at"],
        "time_key": "measured_at",
        "params": {"parts": ["hour"]},
    }
    data = api("POST", "/feature-recipes/validate", body)
    assert data["valid"] is True, data
    assert data.get("reusable_existing_feature") is True, data
    reusable = data.get("reusable_existing_features") or []
    assert any(r.get("feature_name") == "hour" for r in reusable), reusable
    print("  [ok] DATE_PART reusable existing feature (validate)")


def test_date_part_reusable_preview() -> None:
    body = {
        "mapping_id": HEAT_MAPPING_ID,
        "recipe_type": "DATE_PART",
        "source_columns": ["measured_at"],
        "time_key": "measured_at",
        "params": {"parts": ["hour", "day_of_week"]},
        "sample_size": 30,
    }
    data = api("POST", "/feature-recipes/preview", body)
    assert data["valid"] is True, data
    reusable = data.get("reusable_existing_features") or []
    names = {r.get("feature_name") for r in reusable}
    assert "hour" in names or "day_of_week" in names, reusable
    print("  [ok] DATE_PART reusable in preview response")


def _lag_body(**overrides) -> dict:
    body = {
        "mapping_id": HEAT_MAPPING_ID,
        "recipe_type": "LAG",
        "source_columns": ["heat_demand"],
        "entity_keys": ["site_id"],
        "time_key": "measured_at",
        "params": {"offset_steps": 24, "granularity": "1h"},
        "sample_size": 100,
    }
    body.update(overrides)
    return body


def test_lag_preview() -> None:
    data = api("POST", "/feature-recipes/preview", _lag_body())
    assert data["supported"] is True, data
    assert data["valid"] is True, data
    names = data.get("generated_feature_names") or data.get("output_feature_names") or []
    assert "heat_demand_lag_24h" in names, names
    assert len(data["preview_rows"]) > 0, data
    row = data["preview_rows"][0]
    assert "heat_demand_lag_24h" in row, row
    assert data.get("time_series_preview", {}).get("row_step_based") is True, data
    feat = data["stats"]["features"]["heat_demand_lag_24h"]
    assert feat["null_count"] >= 0, feat
    assert feat.get("insufficient_history_count", 0) >= 0, feat
    print("  [ok] LAG preview success")


def test_lag_insufficient_history() -> None:
    data = api("POST", "/feature-recipes/preview", _lag_body(offset_steps=24, sample_size=50))
    assert data["valid"] is True, data
    feat = data["stats"]["features"]["heat_demand_lag_24h"]
    assert feat["insufficient_history_count"] > 0 or feat["null_count"] > 0, feat
    print("  [ok] LAG insufficient_history / null_count")


def test_rolling_mean_preview() -> None:
    body = {
        "mapping_id": HEAT_MAPPING_ID,
        "recipe_type": "ROLLING_MEAN",
        "source_columns": ["heat_demand"],
        "entity_keys": ["site_id"],
        "time_key": "measured_at",
        "params": {
            "window_steps": 24,
            "min_periods": 24,
            "granularity": "1h",
            "include_current_row": False,
        },
        "sample_size": 80,
    }
    data = api("POST", "/feature-recipes/preview", body)
    assert data["supported"] is True, data
    assert data["valid"] is True, data
    names = data.get("generated_feature_names") or []
    assert "heat_demand_ma_24h" in names, names
    assert len(data["preview_rows"]) > 0
    print("  [ok] ROLLING_MEAN preview success")


def test_rolling_sum_preview() -> None:
    body = {
        "mapping_id": HEAT_MAPPING_ID,
        "recipe_type": "ROLLING_SUM",
        "source_columns": ["heat_demand"],
        "entity_keys": ["site_id"],
        "time_key": "measured_at",
        "params": {
            "window_steps": 12,
            "min_periods": 12,
            "granularity": "1h",
            "include_current_row": False,
        },
        "sample_size": 60,
    }
    data = api("POST", "/feature-recipes/preview", body)
    assert data["valid"] is True, data
    names = data.get("generated_feature_names") or []
    assert "heat_demand_sum_12h" in names, names
    print("  [ok] ROLLING_SUM preview success")


def test_rolling_leakage_warning_preview() -> None:
    body = {
        "mapping_id": HEAT_MAPPING_ID,
        "recipe_type": "ROLLING_MEAN",
        "source_columns": ["heat_demand"],
        "entity_keys": ["site_id"],
        "time_key": "measured_at",
        "target_column": "heat_demand",
        "params": {
            "window_steps": 24,
            "granularity": "1h",
            "include_current_row": True,
        },
        "sample_size": 50,
    }
    data = api("POST", "/feature-recipes/preview", body)
    assert data["valid"] is True, data
    leakage = data.get("leakage_warnings") or []
    warnings = data.get("warnings") or []
    combined = " ".join(leakage + warnings)
    assert "누수" in combined, data
    print("  [ok] ROLLING leakage warning in preview")


def test_unsupported_diff_preview() -> None:
    body = {
        "mapping_id": HEAT_MAPPING_ID,
        "recipe_type": "DIFF",
        "source_columns": ["heat_demand"],
        "entity_keys": ["site_id"],
        "time_key": "measured_at",
        "params": {"diff_steps": 1, "granularity": "1h"},
    }
    data = api("POST", "/feature-recipes/preview", body)
    assert data["supported"] is False, data
    assert data["valid"] is False
    assert any(e.get("code") == "PREVIEW_NOT_SUPPORTED" for e in data.get("errors", []))
    print("  [ok] DIFF preview not supported")


def test_lag_preview_infos() -> None:
    data = api("POST", "/feature-recipes/preview", _lag_body(sample_size=30))
    assert data["valid"] is True, data
    infos = data.get("infos") or []
    combined = " ".join(infos)
    assert "과거" in combined or "누수" in combined or "row step" in combined.lower(), infos
    print("  [ok] LAG preview infos (leakage / row-step guidance)")


def test_lag_invalid_granularity() -> None:
    data = api("POST", "/feature-recipes/preview", _lag_body(
        params={"offset_steps": 24, "granularity": "2h"},
    ))
    assert data["valid"] is False, data
    assert any(e.get("code") == "INVALID_PARAM" for e in data.get("errors", []))
    print("  [ok] invalid granularity error")


def test_min_periods_gt_window_validate() -> None:
    body = {
        "mapping_id": HEAT_MAPPING_ID,
        "recipe_type": "ROLLING_MEAN",
        "source_columns": ["heat_demand"],
        "entity_keys": ["site_id"],
        "time_key": "measured_at",
        "params": {"window_steps": 12, "min_periods": 20, "granularity": "1h"},
    }
    data = api("POST", "/feature-recipes/validate", body)
    assert data["valid"] is False, data
    assert any(e.get("code") == "INVALID_PARAM" for e in data.get("errors", []))
    print("  [ok] min_periods > window_steps validate error")


def test_invalid_source_column() -> None:
    body = {
        "mapping_id": HEAT_MAPPING_ID,
        "recipe_type": "RAW_COLUMN",
        "source_columns": ["__no_such_column__"],
    }
    data = api("POST", "/feature-recipes/preview", body)
    assert data["valid"] is False, data
    assert any(e.get("code") == "UNKNOWN_SOURCE_COLUMN" for e in data.get("errors", []))
    print("  [ok] invalid source column error")


def test_sample_size_cap() -> None:
    body = {
        "mapping_id": HEAT_MAPPING_ID,
        "recipe_type": "RAW_COLUMN",
        "source_columns": ["heat_demand"],
        "sample_size": 1000,
    }
    data = api("POST", "/feature-recipes/preview", body)
    assert data["valid"] is True, data
    assert data["stats"]["row_count"] <= 500, data["stats"]
    print("  [ok] sample_size capped at 500")


def test_missing_parts() -> None:
    body = {
        "mapping_id": HEAT_MAPPING_ID,
        "recipe_type": "DATE_PART",
        "source_columns": ["measured_at"],
        "time_key": "measured_at",
        "params": {},
    }
    data = api("POST", "/feature-recipes/preview", body)
    assert data["valid"] is True, data
    assert (data.get("generated_feature_names") or ["hour"])[0] == "hour"
    print("  [ok] DATE_PART default part hour")


def test_output_name_multiple_parts_error() -> None:
    body = {
        "mapping_id": HEAT_MAPPING_ID,
        "recipe_type": "DATE_PART",
        "source_columns": ["measured_at"],
        "time_key": "measured_at",
        "params": {"parts": ["hour", "month"]},
        "output_feature_name": "hour",
    }
    data = api("POST", "/feature-recipes/validate", body)
    assert data["valid"] is False, data
    assert any(e.get("code") == "INVALID_OUTPUT_NAME" for e in data.get("errors", []))
    print("  [ok] output_feature_name + multiple parts error")


def test_preview_no_persist_fields() -> None:
    body = {
        "mapping_id": HEAT_MAPPING_ID,
        "recipe_type": "RAW_COLUMN",
        "source_columns": ["heat_demand"],
        "sample_size": 10,
    }
    data = api("POST", "/feature-recipes/preview", body)
    assert "dataset_version_id" not in data
    assert "recipe_id" not in data
    assert "feature_build_job_id" not in data
    assert data.get("preview_id", "").startswith("PREVIEW-LOCAL-")
    print("  [ok] preview response has no persistence fields")


def test_weather_raw_column_preview() -> None:
    body = {
        "mapping_id": WEATHER_MAPPING_ID,
        "recipe_type": "RAW_COLUMN",
        "source_columns": ["data_type"],
        "sample_size": 20,
    }
    data = api("POST", "/feature-recipes/preview", body)
    assert data["valid"] is True, data
    assert data["stats"]["row_count"] > 0
    print("  [ok] weather mapping RAW_COLUMN preview")


def main() -> int:
    print("test_feature_recipe_preview.py")
    tests = [
        test_raw_column_preview,
        test_date_part_preview,
        test_date_part_reusable_validate,
        test_date_part_reusable_preview,
        test_lag_preview,
        test_lag_insufficient_history,
        test_rolling_mean_preview,
        test_rolling_sum_preview,
        test_rolling_leakage_warning_preview,
        test_unsupported_diff_preview,
        test_lag_preview_infos,
        test_lag_invalid_granularity,
        test_min_periods_gt_window_validate,
        test_invalid_source_column,
        test_sample_size_cap,
        test_missing_parts,
        test_output_name_multiple_parts_error,
        test_preview_no_persist_fields,
        test_weather_raw_column_preview,
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
