#!/usr/bin/env python3
"""prediction-trend API 통합 테스트 (dummy fallback 제거 검증)."""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

API_BASE = os.environ.get("THERMOOPS_API_BASE", "http://localhost:8000/api/v1")

# 과거 dummy 패턴: predicted = 120 + hour*3 (h=0,2,4,...)
DUMMY_PREDICTED = [120 + h * 3 for h in range(0, 24, 2)]


def api(method: str, path: str, body: dict | None = None, timeout: int = 120) -> dict:
    url = f"{API_BASE}{path}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={"Content-Type": "application/json"} if data else {},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        payload = json.loads(resp.read().decode())
    if not payload.get("success"):
        raise RuntimeError(f"API failed {path}: {payload}")
    return payload["data"]


def assert_no_dummy_pattern(items: list) -> None:
    preds = []
    for item in items:
        p = item.get("predicted")
        if p is None:
            p = item.get("predicted_demand")
        if p is not None:
            preds.append(float(p))
    if not preds:
        return
    dummy_hits = sum(1 for p in preds if p in DUMMY_PREDICTED)
    if dummy_hits >= 3 and len(preds) == len(DUMMY_PREDICTED):
        raise RuntimeError(f"dummy trend pattern detected (120+h*3): {preds[:6]}...")


def parse_ts(item: dict) -> datetime | None:
    raw = item.get("target_at") or item.get("timestamp")
    if not raw:
        return None
    return datetime.fromisoformat(raw.replace("Z", "+00:00"))


def main() -> int:
    print(f"THERMOps prediction-trend test ({API_BASE})")
    try:
        trend = api("GET", "/dashboard/prediction-trend")
        if "data_source" not in trend or "items" not in trend:
            raise RuntimeError(f"unexpected response shape: {list(trend.keys())}")
        items = trend.get("items") or []
        ds = trend.get("data_source")
        print(f"  [default] data_source={ds} count={len(items)}")
        assert_no_dummy_pattern(items)

        if ds == "MATCHED":
            sample = items[0]
            has_pred = sample.get("predicted") is not None or sample.get("predicted_demand") is not None
            has_actual = sample.get("actual") is not None or sample.get("actual_demand") is not None
            if not has_pred or not has_actual:
                raise RuntimeError(f"MATCHED trend missing predicted/actual: {sample}")
            print("  [matched] actual/predicted fields present")
        elif ds == "PREDICTION_ONLY":
            if items and items[0].get("actual_demand") is not None:
                raise RuntimeError("PREDICTION_ONLY should not include actual_demand")
            print("  [prediction_only] predicted-only trend")
        elif ds == "EMPTY":
            if items:
                raise RuntimeError("EMPTY data_source should return empty items")
            print("  [empty] no trend data")

        far_future = (datetime.now(timezone.utc) + timedelta(days=3650)).strftime("%Y-%m-%d")
        far_end = (datetime.now(timezone.utc) + timedelta(days=3651)).strftime("%Y-%m-%d")
        q = urllib.parse.urlencode({"start_at": f"{far_future}T00:00:00", "end_at": f"{far_end}T23:59:59"})
        empty_range = api("GET", f"/dashboard/prediction-trend?{q}")
        if empty_range.get("data_source") != "EMPTY":
            raise RuntimeError(f"future range should be EMPTY, got {empty_range.get('data_source')}")
        if empty_range.get("items"):
            raise RuntimeError("future range should return empty items")
        print("  [date_filter] empty future range OK")

        if items:
            first_ts = parse_ts(items[0])
            last_ts = parse_ts(items[-1])
            if first_ts and last_ts:
                start = (first_ts - timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%S")
                end = (last_ts + timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%S")
                q2 = urllib.parse.urlencode({"start_at": start, "end_at": end, "limit": 50})
                filtered = api("GET", f"/dashboard/prediction-trend?{q2}")
                fitems = filtered.get("items") or []
                if not fitems:
                    raise RuntimeError("narrow date filter returned no items while source had data")
                for it in fitems:
                    ts = parse_ts(it)
                    if ts and (ts < first_ts - timedelta(hours=2) or ts > last_ts + timedelta(hours=2)):
                        raise RuntimeError(f"item outside filter range: {ts}")
                print(f"  [date_filter] narrowed range count={len(fitems)}")

        site_q = urllib.parse.urlencode({"site_id": "SITE-NONEXIST", "limit": 10})
        site_empty = api("GET", f"/dashboard/prediction-trend?{site_q}")
        if site_empty.get("items"):
            raise RuntimeError("nonexistent site should return empty trend")
        print("  [site_filter] nonexistent site empty OK")

        print("PASSED")
        return 0
    except urllib.error.URLError as exc:
        print(f"FAILED: cannot reach API ({exc})", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"FAILED: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
