#!/usr/bin/env python3
"""데이터 품질 점검 API 통합 테스트."""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

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
    with urllib.request.urlopen(req, timeout=120) as resp:
        payload = json.loads(resp.read().decode())
    if not payload.get("success"):
        raise RuntimeError(f"API 실패 {path}: {payload}")
    return payload["data"]


def run_domain_check(label: str, data_domain: str) -> str:
    print(f"\n=== {label} ({data_domain}) ===")
    qs = urllib.parse.urlencode({"data_domain": data_domain})
    result = api("POST", f"/data-quality/checks?{qs}")
    summary = result.get("result_summary") or {}
    print(f"  run_id={result.get('run_id')} status={result.get('status')}")
    print(f"  total_count={summary.get('total_count')} quality_score={summary.get('quality_score')}")
    print(f"  missing={summary.get('missing_count')} duplicate={summary.get('duplicate_count')}")
    print(f"  time_gap={summary.get('time_gap_count')} outlier={summary.get('outlier_count')}")
    if summary.get("warnings"):
        print(f"  warnings_count={len(summary.get('warnings', []))}")
    if summary.get("errors"):
        print(f"  errors={summary.get('errors')}")
    if summary.get("total_count", 0) <= 0 and result.get("status") == "FAILED":
        raise RuntimeError(f"{label} 점검 실패: 데이터 없음 또는 오류")
    if "quality_score" not in summary:
        raise RuntimeError(f"{label}: result_summary.quality_score 없음")
    return str(result.get("run_id"))


def main() -> int:
    print(f"THERMOps data quality test ({API_BASE})")
    try:
        heat_run = run_domain_check("열수요 품질", "HEAT_DEMAND")
        weather_run = run_domain_check("기상 품질", "WEATHER")

        runs = api("GET", "/data-quality/runs?page=1&size=20")
        run_ids = {r["run_id"] for r in runs["items"]}
        if heat_run not in run_ids:
            raise RuntimeError(f"열수요 점검 run_id {heat_run}가 이력에 없음")
        if weather_run not in run_ids:
            raise RuntimeError(f"기상 점검 run_id {weather_run}가 이력에 없음")
        print(f"\n  [runs] /data-quality/runs count={len(runs['items'])} (excl INGESTION)")

        print("\nPASSED: data quality check flow")
        return 0
    except (urllib.error.URLError, RuntimeError, KeyError) as exc:
        print(f"\nFAILED: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
