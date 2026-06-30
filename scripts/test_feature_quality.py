#!/usr/bin/env python3
"""Feature Dataset(feature_json) 품질 검증 API 테스트."""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

API_BASE = os.environ.get("THERMOOPS_API_BASE", "http://localhost:8000/api/v1")
FEATURE_SET_ID = os.environ.get("THERMOOPS_FEATURE_SET_ID", "FS-TPL-LAG-ROLL")
REQUIRED_FEATURES = ("demand_lag_24h", "demand_lag_168h", "demand_ma_24h", "demand_ma_168h")


def api(method: str, path: str, body: dict | None = None) -> dict:
    url = f"{API_BASE}{path}"
    data = json.dumps(body).encode() if body is not None else None
    headers = {"Content-Type": "application/json"} if body is not None else {}
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            payload = json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode()
        raise RuntimeError(f"HTTP {exc.code} {path}: {detail}") from exc
    if not payload.get("success"):
        raise RuntimeError(f"API failed {path}: {payload}")
    return payload["data"]


def ensure_dataset_version() -> str:
    range_info = api("GET", f"/feature-sets/{FEATURE_SET_ID}/dataset-range")
    dsv = range_info.get("dataset_version_id")
    if dsv and range_info.get("exists"):
        print(f"  [range] dataset_version_id={dsv} rows={range_info.get('row_count')}")
        return dsv

    qs = urllib.parse.urlencode({"feature_set_id": FEATURE_SET_ID})
    build = api("POST", f"/feature-build-jobs?{qs}", {})
    if build.get("status") not in ("SUCCESS", "WARNING"):
        raise RuntimeError(f"feature build failed: {build}")
    dsv = build.get("dataset_version_id") or (build.get("result_summary") or {}).get("dataset_version_id")
    if not dsv:
        raise RuntimeError("dataset_version_id missing after build")
    print(f"  [build] dataset_version_id={dsv}")
    return dsv


def check_post_quality(dsv: str) -> str:
    body = {"feature_set_id": FEATURE_SET_ID, "dataset_version_id": dsv}
    result = api("POST", "/feature-quality-runs", body)
    for key in ("run_id", "status", "score", "result_summary"):
        if key not in result:
            raise RuntimeError(f"POST response missing {key}: {result.keys()}")
    rs = result["result_summary"]
    for key in ("feature_set_id", "dataset_version_id", "row_count", "feature_count"):
        if key not in rs:
            raise RuntimeError(f"result_summary missing {key}")
    names = {f["feature_name"] for f in rs.get("features", [])}
    for feat in REQUIRED_FEATURES:
        if feat not in names:
            raise RuntimeError(f"feature result missing {feat}: {sorted(names)[:8]}...")
    print(
        f"  [post] run_id={result['run_id']} status={result['status']} "
        f"score={result['score']} rows={rs['row_count']}"
    )
    return result["run_id"]


def check_registration_metadata(run_id: str) -> None:
    detail = api("GET", f"/feature-quality-runs/{run_id}")
    rs = detail.get("result_summary") or {}
    feats = {f["feature_name"]: f for f in rs.get("features", [])}
    for feat in REQUIRED_FEATURES:
        row = feats.get(feat)
        if not row:
            raise RuntimeError(f"missing feature row {feat}")
        if row.get("registration_status") != "COMPUTABLE":
            raise RuntimeError(f"{feat} expected COMPUTABLE, got {row.get('registration_status')}")
        if row.get("computable") is not True:
            raise RuntimeError(f"{feat} computable flag false")
    reg_sum = rs.get("registration_summary") or rs.get("summary") or {}
    if "non_computable_feature_count" not in reg_sum:
        raise RuntimeError(f"registration summary missing counts: {reg_sum.keys()}")
    print("  [registration] COMPUTABLE status on official features OK")


def check_list_and_get(run_id: str) -> None:
    qs = urllib.parse.urlencode({"feature_set_id": FEATURE_SET_ID, "limit": 5})
    listed = api("GET", f"/feature-quality-runs?{qs}")
    if not listed.get("items"):
        raise RuntimeError("list empty")
    if listed["items"][0].get("run_id") != run_id:
        print(f"  [list] latest run differs (ok if parallel): {listed['items'][0].get('run_id')}")
    print(f"  [list] total={listed.get('total')}")

    detail = api("GET", f"/feature-quality-runs/{run_id}")
    if detail.get("run_id") != run_id:
        raise RuntimeError("detail run_id mismatch")
    print(f"  [get] status={detail.get('status')} score={detail.get('score')}")


def check_bad_dataset() -> None:
    body = {
        "feature_set_id": FEATURE_SET_ID,
        "dataset_version_id": "DSV-NONEXIST-00000000000000",
    }
    result = api("POST", "/feature-quality-runs", body)
    if result.get("status") != "FAILED":
        raise RuntimeError(f"expected FAILED for bad dsv, got {result.get('status')}")
    print("  [bad-dsv] FAILED as expected")


def check_data_quality_isolation() -> None:
    runs = api("GET", "/data-quality/runs?page=1&size=50")
    items = runs.get("items", [])
    bad = [r for r in items if r.get("check_type") in ("FEATURE_QUALITY", "FEATURE_BUILD", "INGESTION")]
    if bad:
        raise RuntimeError(f"data-quality/runs leaked non-source types: {[r.get('check_type') for r in bad[:3]]}")
    print(f"  [isolation] data-quality/runs items={len(items)} (no FEATURE_QUALITY)")


def main() -> int:
    print(f"THERMOps feature quality test ({API_BASE})")
    try:
        dsv = ensure_dataset_version()
        run_id = check_post_quality(dsv)
        check_registration_metadata(run_id)
        check_list_and_get(run_id)
        check_bad_dataset()
        check_data_quality_isolation()
        print("\nPASSED: feature quality API")
        return 0
    except Exception as exc:
        print(f"\nFAILED: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
