#!/usr/bin/env python3
"""Feature Build Job 목록 API 검증."""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))
from test_fixtures import FS_LAG_ROLL_ID, ensure_csv_ingested, ensure_test_platform

API_BASE = os.environ.get("THERMOOPS_API_BASE", "http://localhost:8000/api/v1")
FEATURE_SET_ID = os.environ.get("THERMOOPS_FEATURE_SET_ID", FS_LAG_ROLL_ID)


def api(method: str, path: str) -> dict:
    url = f"{API_BASE}{path}"
    req = urllib.request.Request(url, method=method)
    with urllib.request.urlopen(req, timeout=180) as resp:
        payload = json.loads(resp.read().decode())
    if not payload.get("success"):
        raise RuntimeError(f"API failed {path}: {payload}")
    return payload["data"]


def ensure_build() -> str:
    qs = urllib.parse.urlencode({"feature_set_id": FEATURE_SET_ID})
    build = api("POST", f"/feature-build-jobs?{qs}")
    if build.get("status") not in ("SUCCESS", "WARNING"):
        raise RuntimeError(f"feature build failed: {build}")
    job_id = build.get("job_id")
    if not job_id:
        raise RuntimeError("job_id missing from build response")
    print(f"  [build] {FEATURE_SET_ID} -> {job_id}")
    return job_id


def check_list_api() -> str:
    qs = urllib.parse.urlencode({
        "feature_set_id": FEATURE_SET_ID,
        "limit": 5,
        "offset": 0,
    })
    data = api("GET", f"/feature-build-jobs?{qs}")
    for key in ("items", "total", "limit", "offset"):
        if key not in data:
            raise RuntimeError(f"missing key in list response: {key}")
    items = data["items"]
    if not isinstance(items, list):
        raise RuntimeError("items is not a list")
    print(f"  [list] total={data['total']} returned={len(items)} limit={data['limit']}")

    if data["limit"] != 5:
        raise RuntimeError(f"limit mismatch: {data['limit']}")

    if not items:
        job_id = ensure_build()
        data = api("GET", f"/feature-build-jobs?{qs}")
        items = data["items"]
        if not items:
            raise RuntimeError("list still empty after build")

    latest = items[0]
    job_id = latest.get("job_id") or latest.get("run_id")
    if not job_id:
        raise RuntimeError("latest job missing job_id/run_id")
    if latest.get("feature_set_id") and latest["feature_set_id"] != FEATURE_SET_ID:
        raise RuntimeError(f"feature_set_id filter failed: {latest.get('feature_set_id')}")
    print(f"  [list] latest job_id={job_id} status={latest.get('status')}")
    return job_id


def check_filter_and_lineage(job_id: str) -> None:
    other_qs = urllib.parse.urlencode({
        "feature_set_id": "FS-NONEXIST-999",
        "limit": 5,
    })
    other = api("GET", f"/feature-build-jobs?{other_qs}")
    if other.get("total", 0) != 0:
        raise RuntimeError("filter should return 0 for nonexistent feature set")

    lineage = api("GET", f"/feature-build-jobs/{job_id}/lineage")
    if "items" not in lineage:
        raise RuntimeError("lineage response missing items")
    print(f"  [lineage] job={job_id} rows={len(lineage.get('items') or [])}")


def main() -> int:
    print(f"THERMOps feature build jobs test ({API_BASE})")
    try:
        ensure_test_platform()
        ensure_csv_ingested(api)
        job_id = check_list_api()
        check_filter_and_lineage(job_id)
        print("\nPASSED: feature build jobs API")
        return 0
    except (urllib.error.URLError, RuntimeError, json.JSONDecodeError) as exc:
        print(f"\nFAILED: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
