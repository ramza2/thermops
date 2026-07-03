#!/usr/bin/env python3
"""Model/full regression 전 test platform·CSV fixture 준비 (운영 seed 변경 없음)."""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from test_fixtures import ensure_model_regression_fixtures, psql_scalar

API_BASE = os.environ.get("THERMOOPS_API_BASE", "http://localhost:8000/api/v1")


def api(method: str, path: str, body: dict | None = None) -> dict:
    url = f"{API_BASE}{path}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={"Content-Type": "application/json"} if data else {},
    )
    last_exc: Exception | None = None
    for attempt in range(6):
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                payload = json.loads(resp.read().decode())
            if not payload.get("success"):
                raise RuntimeError(f"API failed {method} {path}: {payload}")
            return payload["data"]
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, RuntimeError) as exc:
            last_exc = exc
            if attempt < 5:
                time.sleep(3 * (attempt + 1))
                continue
            raise
    raise RuntimeError(f"API failed {method} {path}: {last_exc}")


def main() -> int:
    print(f"THERMOps model regression fixture prepare ({API_BASE})")
    try:
        info = ensure_model_regression_fixtures(api)
        heat_rows = psql_scalar("SELECT COUNT(*) FROM tb_heat_demand_actual")
        weather_rows = psql_scalar("SELECT COUNT(*) FROM tb_weather_observation")
        print(f"  [ok] heat source={info['heat']['source_id']} mapping={info['heat']['mapping_id']} rows={heat_rows}")
        print(f"  [ok] weather source={info['weather']['source_id']} mapping={info['weather']['mapping_id']} rows={weather_rows}")
        print("PASSED: model regression fixtures ready")
        return 0
    except (urllib.error.URLError, RuntimeError, OSError) as exc:
        print(f"FAILED: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
