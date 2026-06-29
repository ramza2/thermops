#!/usr/bin/env python3
"""Feature Dataset 기간 조회 API 테스트."""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

API_BASE = os.environ.get("THERMOOPS_API_BASE", "http://localhost:8000/api/v1")
FEATURE_SET_ID = os.environ.get("THERMOOPS_FEATURE_SET_ID", "FS-TPL-LAG-ROLL")
EMPTY_FEATURE_SET_ID = os.environ.get("THERMOOPS_EMPTY_FEATURE_SET_ID", "FS-TPL-MINIMAL")


def api_get(path: str) -> dict:
    url = f"{API_BASE}{path}"
    req = urllib.request.Request(url, method="GET")
    with urllib.request.urlopen(req, timeout=60) as resp:
        payload = json.loads(resp.read().decode())
    if not payload.get("success"):
        raise RuntimeError(f"API failed {path}: {payload}")
    return payload["data"]


def api_post_query(path: str) -> dict:
    url = f"{API_BASE}{path}"
    req = urllib.request.Request(url, method="POST", data=b"")
    with urllib.request.urlopen(req, timeout=180) as resp:
        payload = json.loads(resp.read().decode())
    if not payload.get("success"):
        raise RuntimeError(f"API failed {path}: {payload}")
    return payload["data"]


def ensure_feature_dataset() -> None:
    data = api_get(f"/feature-sets/{FEATURE_SET_ID}/dataset-range")
    if data.get("exists") and int(data.get("row_count", 0)) > 0:
        print(f"  [skip] feature dataset exists rows={data['row_count']}")
        return
    print("  [build] creating feature dataset...")
    api_post_query(f"/feature-build-jobs?feature_set_id={FEATURE_SET_ID}")


def main() -> int:
    print(f"THERMOps feature dataset range test ({API_BASE})")
    try:
        ensure_feature_dataset()

        data = api_get(f"/feature-sets/{FEATURE_SET_ID}/dataset-range")
        assert data["feature_set_id"] == FEATURE_SET_ID
        assert data["exists"] is True, data
        assert data["row_count"] > 0, data
        assert data["min_target_at"], data
        assert data["max_target_at"], data
        assert "T" in data["min_target_at"]
        assert data["min_target_at"].endswith("Z") is False
        assert isinstance(data["sites"], list)
        print(f"  [ok] range {data['min_target_at']} ~ {data['max_target_at']} rows={data['row_count']}")

        empty = api_get(f"/feature-sets/{EMPTY_FEATURE_SET_ID}/dataset-range")
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
