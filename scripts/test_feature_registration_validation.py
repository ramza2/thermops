#!/usr/bin/env python3
"""Feature 등록·Registry 검증 API 및 Build missing summary 테스트."""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
import uuid

API_BASE = os.environ.get("THERMOOPS_API_BASE", "http://localhost:8000/api/v1")
TPL_FEATURE_SET_ID = os.environ.get("THERMOOPS_FEATURE_SET_ID", "FS-TPL-LAG-ROLL")
CUSTOM_FEATURE_NAME = f"test_catalog_only_{uuid.uuid4().hex[:8]}"


def api(method: str, path: str, body: dict | None = None) -> dict | list:
    url = f"{API_BASE}{path}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={"Content-Type": "application/json"} if data else {},
    )
    with urllib.request.urlopen(req, timeout=180) as resp:
        payload = json.loads(resp.read().decode())
    if not payload.get("success"):
        raise RuntimeError(f"API failed {method} {path}: {payload}")
    return payload["data"]


def validate_name(feature_name: str) -> dict:
    q = urllib.parse.urlencode({"feature_name": feature_name})
    return api("GET", f"/features/validate-name?{q}")


def test_registry_computable() -> None:
    v = validate_name("demand_lag_24h")
    assert v["status"] == "COMPUTABLE", v
    assert v["computable"] is True, v
    assert v["registry_registered"] is True, v
    print("  [ok] demand_lag_24h -> COMPUTABLE")


def test_legacy_aliases() -> None:
    cases = {
        "hdd": "heating_degree_days",
        "cdd": "cooling_degree_days",
        "rolling_24h_avg": "demand_ma_24h",
    }
    for alias, official in cases.items():
        v = validate_name(alias)
        assert v["status"] == "LEGACY_ALIAS", v
        assert v["recommended_name"] == official, v
        assert v["computable"] is False, v
        print(f"  [ok] {alias} -> LEGACY_ALIAS ({official})")


def test_catalog_only_unknown() -> None:
    v = validate_name("demand_lag_48h")
    assert v["status"] == "CATALOG_ONLY", v
    assert v["computable"] is False, v
    assert v["catalog_registered"] is False, v
    print("  [ok] demand_lag_48h -> CATALOG_ONLY (미등록)")


def test_duplicate_catalog_only() -> None:
    created_id: str | None = None
    try:
        created = api(
            "POST",
            "/features",
            {
                "feature_name": CUSTOM_FEATURE_NAME,
                "feature_group": "테스트",
                "feature_type": "NUMERIC",
                "calc_expression": "테스트용 카탈로그 전용",
                "description": "THERMOps registration validation test",
            },
        )
        created_id = created.get("feature_id")
        v = validate_name(CUSTOM_FEATURE_NAME)
        assert v["status"] == "DUPLICATE", v
        assert v["catalog_registered"] is True, v
        assert v["computable"] is False, v
        print(f"  [ok] {CUSTOM_FEATURE_NAME} -> DUPLICATE")

        match = None
        for page in range(1, 11):
            listed = api("GET", f"/features?page={page}&size=100")
            items = listed.get("items") if isinstance(listed, dict) else listed
            if not items:
                break
            match = next((i for i in items if i.get("feature_name") == CUSTOM_FEATURE_NAME), None)
            if match:
                break
        assert match and match.get("registration", {}).get("status") == "DUPLICATE", match
        print("  [ok] catalog-only feature list registration status")
    finally:
        if created_id:
            try:
                api("DELETE", f"/features/{created_id}")
            except Exception:
                pass


def test_tpl_build_success_with_coverage() -> None:
    q = urllib.parse.urlencode({"feature_set_id": TPL_FEATURE_SET_ID})
    build = api("POST", f"/feature-build-jobs?{q}")
    summary = build.get("result_summary") or {}
    missing_count = summary.get("missing_feature_count", 0)
    assert build.get("status") == "SUCCESS", build
    assert missing_count == 0, summary
    print(f"  [ok] TPL build SUCCESS missing_feature_count=0 ({TPL_FEATURE_SET_ID})")


def test_custom_set_build_warning() -> None:
    build_fs_id: str | None = None
    feat_id: str | None = None
    name = f"test_build_missing_{uuid.uuid4().hex[:8]}"
    try:
        created_feat = api(
            "POST",
            "/features",
            {
                "feature_name": name,
                "feature_group": "테스트",
                "feature_type": "NUMERIC",
                "calc_expression": "없음",
                "description": "Build missing summary test",
            },
        )
        feat_id = created_feat.get("feature_id")
        fs = api(
            "POST",
            "/feature-sets",
            {
                "feature_set_name": "Registration validation test set",
                "target_domain": "HEAT_DEMAND",
                "apply_site_scope": "ALL",
                "features": ["temperature", name],
                "description": "THERMOps test: catalog-only missing feature",
            },
        )
        build_fs_id = fs.get("feature_set_id")
        q = urllib.parse.urlencode({"feature_set_id": build_fs_id})
        build = api("POST", f"/feature-build-jobs?{q}")
        summary = build.get("result_summary") or {}
        assert build.get("status") == "WARNING", build
        assert summary.get("missing_feature_count", 0) >= 1, summary
        assert name in (summary.get("missing_features") or []), summary
        assert name in (summary.get("catalog_only_features") or []), summary
        print("  [ok] custom set build WARNING with catalog_only_features")
    finally:
        if build_fs_id:
            try:
                api("DELETE", f"/feature-sets/{build_fs_id}")
            except Exception:
                pass
        if feat_id:
            try:
                api("DELETE", f"/features/{feat_id}")
            except Exception:
                pass


def test_custom_set_quality_registration() -> None:
    build_fs_id: str | None = None
    feat_id: str | None = None
    name = f"test_quality_reg_{uuid.uuid4().hex[:8]}"
    try:
        created_feat = api(
            "POST",
            "/features",
            {
                "feature_name": name,
                "feature_group": "테스트",
                "feature_type": "NUMERIC",
                "calc_expression": "없음",
                "description": "Quality registration status test",
            },
        )
        feat_id = created_feat.get("feature_id")
        fs = api(
            "POST",
            "/feature-sets",
            {
                "feature_set_name": "Quality registration test set",
                "target_domain": "HEAT_DEMAND",
                "apply_site_scope": "ALL",
                "features": ["temperature", name],
                "description": "THERMOps test: catalog-only quality registration",
            },
        )
        build_fs_id = fs.get("feature_set_id")
        q = urllib.parse.urlencode({"feature_set_id": build_fs_id})
        build = api("POST", f"/feature-build-jobs?{q}")
        dsv = build.get("dataset_version_id") or (build.get("result_summary") or {}).get("dataset_version_id")
        assert dsv, build
        quality = api(
            "POST",
            "/feature-quality-runs",
            {"feature_set_id": build_fs_id, "dataset_version_id": dsv},
        )
        rs = quality.get("result_summary") or {}
        by_name = {f["feature_name"]: f for f in rs.get("features", [])}
        custom = by_name.get(name)
        assert custom, by_name.keys()
        assert custom.get("registration_status") in ("CATALOG_ONLY", "DUPLICATE"), custom
        assert custom.get("computable") is False, custom
        reg_sum = rs.get("registration_summary") or rs.get("summary") or {}
        assert reg_sum.get("non_computable_feature_count", 0) >= 1, reg_sum
        assert (
            reg_sum.get("catalog_only_feature_count", 0) >= 1
            or reg_sum.get("non_computable_feature_count", 0) >= 1
        ), reg_sum
        print("  [ok] custom set quality registration_status for catalog-only")
    finally:
        if build_fs_id:
            try:
                api("DELETE", f"/feature-sets/{build_fs_id}")
            except Exception:
                pass
        if feat_id:
            try:
                api("DELETE", f"/features/{feat_id}")
            except Exception:
                pass


def main() -> int:
    print(f"THERMOps feature registration validation test ({API_BASE})")
    try:
        test_registry_computable()
        test_legacy_aliases()
        test_catalog_only_unknown()
        test_duplicate_catalog_only()
        test_tpl_build_success_with_coverage()
        test_custom_set_build_warning()
        test_custom_set_quality_registration()
        print("\nPASSED: feature registration validation")
        return 0
    except (urllib.error.URLError, AssertionError, RuntimeError, KeyError) as exc:
        print(f"\nFAILED: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
