#!/usr/bin/env python3
"""Feature Set Legacy alias 공식명 일괄 대체 API 테스트."""

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
from test_fixtures import (
    FS_LAG_ROLL_ID,
    ensure_csv_ingested,
    ensure_feature_dataset_built,
    ensure_test_platform,
)

API_BASE = os.environ.get("THERMOOPS_API_BASE", "http://localhost:8000/api/v1")
TPL_FEATURE_SET_ID = os.environ.get("THERMOOPS_FEATURE_SET_ID", FS_LAG_ROLL_ID)
TEST_MARKER = "THERMOps test: legacy replace"


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
        with urllib.request.urlopen(req, timeout=180) as resp:
            payload = json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode()
        raise RuntimeError(f"HTTP {exc.code} {method} {path}: {detail}") from exc
    if not payload.get("success"):
        raise RuntimeError(f"API failed {method} {path}: {payload}")
    return payload["data"]


def get_feature_set(fs_id: str) -> dict:
    return api("GET", f"/feature-sets/{fs_id}")


def create_legacy_test_set(features: list[str]) -> str:
    fs = api(
        "POST",
        "/feature-sets",
        {
            "feature_set_name": f"Legacy replace test {uuid.uuid4().hex[:6]}",
            "target_domain": "HEAT_DEMAND",
            "apply_site_scope": "ALL",
            "features": features,
            "description": TEST_MARKER,
        },
    )
    return fs["feature_set_id"]


def replace_legacy(fs_id: str, dry_run: bool) -> dict:
    return api(
        "POST",
        f"/feature-sets/{fs_id}/replace-legacy-features",
        {"dry_run": dry_run},
    )


def delete_feature_set(fs_id: str) -> None:
    try:
        api("DELETE", f"/feature-sets/{fs_id}")
    except Exception:
        pass


def test_dry_run_mapping() -> None:
    fs_id = create_legacy_test_set(["hour", "hdd", "rolling_24h_avg"])
    try:
        before = get_feature_set(fs_id)["features"]
        plan = replace_legacy(fs_id, dry_run=True)
        after = get_feature_set(fs_id)["features"]
        assert before == after, "dry_run must not change DB"
        assert plan["changed"] is True, plan
        mapping = {r["from"]: r["to"] for r in plan["replacements"]}
        assert mapping.get("hdd") == "heating_degree_days", mapping
        assert mapping.get("rolling_24h_avg") == "demand_ma_24h", mapping
        assert plan["replaced_features"] == ["hour", "heating_degree_days", "demand_ma_24h"], plan
        print("  [ok] dry_run mapping hdd, rolling_24h_avg")
    finally:
        delete_feature_set(fs_id)


def test_apply_updates_features() -> None:
    fs_id = create_legacy_test_set(["temperature", "hdd", "cdd"])
    try:
        result = replace_legacy(fs_id, dry_run=False)
        assert result.get("applied") is True, result
        features = get_feature_set(fs_id)["features"]
        assert "heating_degree_days" in features, features
        assert "cooling_degree_days" in features, features
        assert "hdd" not in features and "cdd" not in features, features
        for name in ("heating_degree_days", "cooling_degree_days"):
            v = api("GET", f"/features/validate-name?feature_name={urllib.parse.quote(name)}")
            assert v["computable"] is True, v
        print("  [ok] apply updates features to official names")
    finally:
        delete_feature_set(fs_id)


def test_duplicate_removal() -> None:
    fs_id = create_legacy_test_set(["demand_ma_24h", "rolling_24h_avg", "hour"])
    try:
        plan = replace_legacy(fs_id, dry_run=True)
        assert plan["replaced_features"].count("demand_ma_24h") == 1, plan
        assert "rolling_24h_avg" in plan["removed_duplicates"] or plan["duplicate_removed_count"] >= 1, plan
        replace_legacy(fs_id, dry_run=False)
        features = get_feature_set(fs_id)["features"]
        assert features.count("demand_ma_24h") == 1, features
        print("  [ok] duplicate removal demand_ma_24h")
    finally:
        delete_feature_set(fs_id)


def test_no_legacy_remaining() -> None:
    fs_id = create_legacy_test_set(["lag_24h_demand", "demand_lag_24h"])
    try:
        replace_legacy(fs_id, dry_run=False)
        features = get_feature_set(fs_id)["features"]
        assert "lag_24h_demand" not in features, features
        assert features.count("demand_lag_24h") == 1, features
        plan = replace_legacy(fs_id, dry_run=True)
        assert plan["changed"] is False or plan["replacement_count"] == 0, plan
        print("  [ok] no legacy remaining after replace")
    finally:
        delete_feature_set(fs_id)


def test_put_blocks_new_legacy() -> None:
    fs_id = create_legacy_test_set(["hour", "temperature"])
    try:
        body = {
            "feature_set_name": "blocked legacy put",
            "target_domain": "HEAT_DEMAND",
            "apply_site_scope": "ALL",
            "features": ["hour", "temperature", "hdd"],
            "description": TEST_MARKER,
        }
        url = f"{API_BASE}/feature-sets/{fs_id}"
        req = urllib.request.Request(
            url,
            data=json.dumps(body).encode(),
            method="PUT",
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                raise RuntimeError(f"expected 400, got {resp.status}")
        except urllib.error.HTTPError as exc:
            if exc.code != 400:
                raise RuntimeError(f"expected 400, got {exc.code}: {exc.read().decode()}") from exc
        print("  [ok] PUT blocks new legacy alias")
    finally:
        delete_feature_set(fs_id)


def test_tpl_build_success() -> None:
    q = urllib.parse.urlencode({"feature_set_id": TPL_FEATURE_SET_ID})
    build = api("POST", f"/feature-build-jobs?{q}")
    summary = build.get("result_summary") or {}
    assert build.get("status") == "SUCCESS", build
    assert summary.get("missing_feature_count", 0) == 0, summary
    print(f"  [ok] TPL build SUCCESS ({TPL_FEATURE_SET_ID})")


def main() -> int:
    print(f"THERMOps feature set legacy replace test ({API_BASE})")
    try:
        ensure_test_platform()
        ensure_csv_ingested(api)
        test_dry_run_mapping()
        test_apply_updates_features()
        test_duplicate_removal()
        test_no_legacy_remaining()
        test_put_blocks_new_legacy()
        test_tpl_build_success()
        print("\nPASSED: feature set legacy replace")
        return 0
    except (urllib.error.URLError, AssertionError, RuntimeError, KeyError) as exc:
        print(f"\nFAILED: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
