#!/usr/bin/env python3
"""배치 예측 기간 검증 API 테스트."""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timedelta

API_BASE = os.environ.get("THERMOOPS_API_BASE", "http://localhost:8000/api/v1")
FEATURE_SET_ID = os.environ.get("THERMOOPS_FEATURE_SET_ID", "FS-TPL-LAG-ROLL")
EMPTY_FEATURE_SET_ID = os.environ.get("THERMOOPS_EMPTY_FEATURE_SET_ID", "FS-TPL-MINIMAL")


def api(method: str, path: str, body: dict | None = None, timeout: int = 300) -> dict:
    url = f"{API_BASE}{path}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={"Content-Type": "application/json"} if data else {},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode())


def api_data(method: str, path: str, body: dict | None = None, timeout: int = 300) -> dict:
    payload = api(method, path, body, timeout=timeout)
    if not payload.get("success"):
        raise RuntimeError(f"API failed {path}: {payload}")
    return payload["data"]


def api_expect_error(method: str, path: str, body: dict, expected_code: str) -> dict:
    try:
        api(method, path, body)
        raise AssertionError(f"expected HTTP error for {expected_code}")
    except urllib.error.HTTPError as exc:
        body_text = exc.read().decode()
        if exc.code != 400:
            raise AssertionError(f"expected 400 got {exc.code}: {body_text}") from exc
        payload = json.loads(body_text)
        detail = payload.get("detail")
        if isinstance(detail, dict):
            assert detail.get("error_code") == expected_code, detail
            return detail
        raise AssertionError(f"expected structured detail, got {detail}")
    raise AssertionError("unreachable")


def ensure_feature_dataset() -> dict:
    data = api_data("GET", f"/feature-sets/{FEATURE_SET_ID}/dataset-range")
    if data.get("exists") and int(data.get("row_count", 0)) > 0:
        return data
    api_data("POST", f"/feature-build-jobs?feature_set_id={FEATURE_SET_ID}", timeout=180)
    return api_data("GET", f"/feature-sets/{FEATURE_SET_ID}/dataset-range")


def find_compatible_model_version() -> str | None:
    models = api_data("GET", "/models")
    for m in models:
        versions = api_data("GET", f"/models/{m['model_name']}/versions")
        if versions:
            return versions[0]["model_version_id"]
    return None


def ensure_model() -> str:
    mv = find_compatible_model_version()
    if mv:
        return mv
    configs = api_data("GET", "/training-configs")
    config_id = next(
        (c["config_id"] for c in configs if c.get("feature_set_id") == FEATURE_SET_ID),
        None,
    )
    if not config_id:
        raise RuntimeError("training config not found")
    result = api_data("POST", "/training-jobs", {"config_id": config_id}, timeout=300)
    if result.get("status") != "SUCCESS":
        raise RuntimeError(f"training failed: {result}")
    return result["model_version_id"]


def main() -> int:
    print(f"THERMOps prediction period validation test ({API_BASE})")
    try:
        range_data = ensure_feature_dataset()
        assert range_data["exists"], range_data
        min_at = range_data["min_target_at"]
        max_at = range_data["max_target_at"]
        model_version_id = ensure_model()
        print(f"  [range] {min_at} ~ {max_at}")
        print(f"  [model] {model_version_id}")

        ok_body = {
            "feature_set_id": FEATURE_SET_ID,
            "model_version_id": model_version_id,
            "start_at": min_at,
            "end_at": max_at,
            "prediction_horizon": "BATCH",
            "overwrite_yn": True,
        }
        result = api_data("POST", "/prediction-jobs", ok_body, timeout=300)
        assert result.get("status") == "SUCCESS", result
        print(f"  [ok] in-range prediction status={result.get('status')} count={result.get('predicted_count')}")

        max_dt = datetime.fromisoformat(max_at)
        out_start = (max_dt + timedelta(days=1)).isoformat(timespec="seconds")
        out_end = (max_dt + timedelta(days=3)).isoformat(timespec="seconds")
        detail = api_expect_error(
            "POST",
            "/prediction-jobs",
            {
                "feature_set_id": FEATURE_SET_ID,
                "model_version_id": model_version_id,
                "start_at": out_start,
                "end_at": out_end,
                "prediction_horizon": "BATCH",
                "overwrite_yn": True,
            },
            "PREDICTION_PERIOD_OUT_OF_FEATURE_RANGE",
        )
        assert detail.get("available_start_at") == min_at
        assert detail.get("available_end_at") == max_at
        print("  [ok] out-of-range -> 400 PREDICTION_PERIOD_OUT_OF_FEATURE_RANGE")

        empty_detail = api_expect_error(
            "POST",
            "/prediction-jobs",
            {
                "feature_set_id": EMPTY_FEATURE_SET_ID,
                "model_version_id": model_version_id,
                "start_at": min_at,
                "end_at": max_at,
                "prediction_horizon": "BATCH",
                "overwrite_yn": True,
            },
            "NO_FEATURE_DATASET",
        )
        assert empty_detail.get("feature_set_id") == EMPTY_FEATURE_SET_ID
        print(f"  [ok] no dataset -> 400 NO_FEATURE_DATASET")

        aware_body = dict(ok_body)
        aware_body["start_at"] = f"{min_at}Z"
        aware_body["end_at"] = f"{max_at}Z"
        aware_result = api_data("POST", "/prediction-jobs", aware_body, timeout=300)
        assert aware_result.get("status") == "SUCCESS", aware_result
        print("  [ok] timezone-aware input normalized and accepted")

        print("PASS")
        return 0
    except AssertionError as exc:
        print(f"ASSERT FAIL: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
