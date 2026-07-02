#!/usr/bin/env python3
"""Feature Dataset 기간 조회 API 테스트."""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))
from test_fixtures import (
    FS_LAG_ROLL_ID,
    FS_MINIMAL_ID,
    ensure_csv_ingested,
    ensure_test_platform,
)

API_BASE = os.environ.get("THERMOOPS_API_BASE", "http://localhost:8000/api/v1")
FEATURE_SET_ID = os.environ.get("THERMOOPS_FEATURE_SET_ID", FS_LAG_ROLL_ID)
EMPTY_FEATURE_SET_ID = os.environ.get("THERMOOPS_EMPTY_FEATURE_SET_ID", FS_MINIMAL_ID)


def api(method: str, path: str) -> dict:
    url = f"{API_BASE}{path}"
    req = urllib.request.Request(url, method=method, data=b"" if method == "POST" else None)
    with urllib.request.urlopen(req, timeout=180) as resp:
        payload = json.loads(resp.read().decode())
    if not payload.get("success"):
        raise RuntimeError(f"API failed {path}: {payload}")
    return payload["data"]


def ensure_feature_dataset() -> None:
    data = api("GET", f"/feature-sets/{FEATURE_SET_ID}/dataset-range")
    if data.get("exists") and int(data.get("row_count", 0)) > 0:
        print(f"  [skip] feature dataset exists rows={data['row_count']}")
        return
    print("  [build] creating feature dataset...")
    api("POST", f"/feature-build-jobs?feature_set_id={FEATURE_SET_ID}")


def main() -> int:
    print(f"THERMOps feature dataset range test ({API_BASE})")
    try:
        ensure_test_platform()
        ensure_csv_ingested(api)
        ensure_feature_dataset()

        data = api("GET", f"/feature-sets/{FEATURE_SET_ID}/dataset-range")
        assert data["feature_set_id"] == FEATURE_SET_ID
        assert data["exists"] is True, data
        assert data["row_count"] > 0, data
        assert data["min_target_at"], data
        assert data["max_target_at"], data
        assert "T" in data["min_target_at"]
        assert data["min_target_at"].endswith("Z") is False
        assert isinstance(data["sites"], list)
        print(f"  [ok] range {data['min_target_at']} ~ {data['max_target_at']} rows={data['row_count']}")

        empty = api("GET", f"/feature-sets/{EMPTY_FEATURE_SET_ID}/dataset-range")
        if empty.get("exists"):
            print(f"  [warn] {EMPTY_FEATURE_SET_ID} unexpectedly has dataset rows={empty.get('row_count')}")
        else:
            assert empty["exists"] is False
            assert empty["row_count"] == 0
            assert empty["min_target_at"] is None
            print(f"  [ok] empty range for {EMPTY_FEATURE_SET_ID}")

        print("PASS")
        return 0
    except urllib.error.HTTPError as exc:
        body = exc.read().decode()
        print(f"HTTP {exc.code}: {body}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
