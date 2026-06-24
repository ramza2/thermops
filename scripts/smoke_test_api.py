#!/usr/bin/env python3
"""THERMOps API smoke test — checks HTTP status codes for key endpoints."""

from __future__ import annotations

import sys
import urllib.error
import urllib.request

BASE_URL = "http://localhost:8000"

ENDPOINTS = [
    "/health",
    "/api/v1/dashboard/overview",
    "/api/v1/data-sources",
    "/api/v1/mappings",
    "/api/v1/features",
    "/api/v1/feature-sets",
    "/api/v1/training-configs",
    "/api/v1/training-jobs",
    "/api/v1/models",
    "/api/v1/predictions",
    "/api/v1/pipeline-runs",
    "/api/v1/drift-reports",
    "/api/v1/retraining-candidates",
]


def check(path: str) -> tuple[bool, int | str]:
    url = f"{BASE_URL}{path}"
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            return resp.status == 200, resp.status
    except urllib.error.HTTPError as e:
        return False, e.code
    except urllib.error.URLError as e:
        return False, str(e.reason)


def main() -> int:
    print(f"THERMOps API smoke test ({BASE_URL})\n")
    failed = []
    for path in ENDPOINTS:
        ok, status = check(path)
        mark = "OK" if ok else "FAIL"
        print(f"  [{mark}] {path} -> {status}")
        if not ok:
            failed.append(path)

    print()
    if failed:
        print(f"FAILED: {len(failed)} endpoint(s)")
        return 1
    print(f"PASSED: {len(ENDPOINTS)} endpoint(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
