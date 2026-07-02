#!/usr/bin/env python3
"""배치 예측 기간 검증 API 테스트."""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))
from test_fixtures import (
    FS_LAG_ROLL_ID,
    FS_MINIMAL_ID,
    FS_TWO_STAGE_ID,
    ensure_csv_ingested,
    ensure_test_platform,
)
from test_http_debug import api_error_summary

API_BASE = os.environ.get("THERMOOPS_API_BASE", "http://localhost:8000/api/v1")
FEATURE_SET_ID = os.environ.get("THERMOOPS_FEATURE_SET_ID", FS_LAG_ROLL_ID)
# 테스트 전용: Dataset 없는 Feature Set (기본은 실행 시 생성·재사용)
TEST_NO_DATASET_FS_NAME = "TEST-NO-DATASET period validation"
TEST_NO_DATASET_FS_MARKER = "THERMOps test: no feature dataset (period validation)"
# Dataset 있는 다른 Feature Set 후보 (MODEL_FEATURE_SET_MISMATCH)
ALT_FEATURE_SET_CANDIDATES = (FS_MINIMAL_ID, FS_TWO_STAGE_ID)


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
    try:
        payload = api(method, path, body, timeout=timeout)
    except urllib.error.HTTPError as exc:
        raise RuntimeError(api_error_summary(method, path, exc)) from exc
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


def _dataset_range(feature_set_id: str) -> dict:
    return api_data("GET", f"/feature-sets/{feature_set_id}/dataset-range")


def _feature_set_exists(feature_set_id: str) -> bool:
    path = f"/feature-sets/{feature_set_id}"
    try:
        payload = api("GET", path)
        return bool(payload.get("success"))
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return False
        raise RuntimeError(api_error_summary("GET", path, exc)) from exc


def ensure_no_dataset_feature_set() -> str:
    """Dataset 없는 Feature Set 확보 (메타만 존재, Feature Build 미실행)."""
    env_id = os.environ.get("THERMOOPS_EMPTY_FEATURE_SET_ID")
    if env_id:
        if not _feature_set_exists(env_id):
            raise RuntimeError(f"THERMOOPS_EMPTY_FEATURE_SET_ID={env_id} not found")
        dr = _dataset_range(env_id)
        if dr.get("exists") and int(dr.get("row_count", 0)) > 0:
            raise RuntimeError(
                f"THERMOOPS_EMPTY_FEATURE_SET_ID={env_id} has dataset rows={dr.get('row_count')}; "
                "expected empty for NO_FEATURE_DATASET test"
            )
        print(f"  [setup] using env empty feature set {env_id}")
        return env_id

    for fs in api_data("GET", "/feature-sets"):
        if fs.get("description") == TEST_NO_DATASET_FS_MARKER or fs.get("feature_set_name") == TEST_NO_DATASET_FS_NAME:
            fsid = fs["feature_set_id"]
            dr = _dataset_range(fsid)
            if dr.get("exists") and int(dr.get("row_count", 0)) > 0:
                raise RuntimeError(
                    f"test feature set {fsid} has dataset rows={dr.get('row_count')}; "
                    "delete dataset or use THERMOOPS_EMPTY_FEATURE_SET_ID"
                )
            print(f"  [setup] reusing no-dataset feature set {fsid}")
            return fsid

    created = api_data(
        "POST",
        "/feature-sets",
        {
            "feature_set_name": TEST_NO_DATASET_FS_NAME,
            "target_domain": "HEAT_DEMAND",
            "features": ["temperature", "hour"],
            "apply_site_scope": "ALL",
            "description": TEST_NO_DATASET_FS_MARKER,
        },
    )
    fsid = created["feature_set_id"]
    print(f"  [setup] created no-dataset feature set {fsid}")
    return fsid


def ensure_other_feature_set_with_dataset(primary_id: str) -> tuple[str, dict]:
    """primary와 다른 Feature Set 중 Dataset이 있는 것을 반환 (없으면 build)."""
    for fsid in ALT_FEATURE_SET_CANDIDATES:
        if fsid == primary_id:
            continue
        if not _feature_set_exists(fsid):
            continue
        dr = _dataset_range(fsid)
        if dr.get("exists") and int(dr.get("row_count", 0)) > 0:
            return fsid, dr

    for fsid in ALT_FEATURE_SET_CANDIDATES:
        if fsid == primary_id:
            continue
        if not _feature_set_exists(fsid):
            continue
        print(f"  [setup] building dataset for mismatch test: {fsid}")
        api_data("POST", f"/feature-build-jobs?feature_set_id={fsid}", timeout=180)
        dr = _dataset_range(fsid)
        if dr.get("exists") and int(dr.get("row_count", 0)) > 0:
            return fsid, dr

    raise RuntimeError(
        f"no alternate feature set with dataset found (candidates={ALT_FEATURE_SET_CANDIDATES})"
    )


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
        ensure_test_platform()
        ensure_csv_ingested(api_data)
        range_data = ensure_feature_dataset()
        assert range_data["exists"], range_data
        min_at = range_data["min_target_at"]
        max_at = range_data["max_target_at"]
        model_version_id = ensure_model()
        no_dataset_fs_id = ensure_no_dataset_feature_set()
        print(f"  [range] {min_at} ~ {max_at}")
        print(f"  [model] {model_version_id}")
        print(f"  [no-dataset-fs] {no_dataset_fs_id}")

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
                "feature_set_id": no_dataset_fs_id,
                "start_at": min_at,
                "end_at": max_at,
                "prediction_horizon": "BATCH",
                "overwrite_yn": True,
            },
            "NO_FEATURE_DATASET",
        )
        assert empty_detail.get("feature_set_id") == no_dataset_fs_id
        print(f"  [ok] no dataset ({no_dataset_fs_id}) -> 400 NO_FEATURE_DATASET")

        alt_fs_id, alt_range = ensure_other_feature_set_with_dataset(FEATURE_SET_ID)
        mismatch_detail = api_expect_error(
            "POST",
            "/prediction-jobs",
            {
                "feature_set_id": alt_fs_id,
                "model_version_id": model_version_id,
                "start_at": alt_range["min_target_at"],
                "end_at": alt_range["max_target_at"],
                "prediction_horizon": "BATCH",
                "overwrite_yn": True,
            },
            "MODEL_FEATURE_SET_MISMATCH",
        )
        assert mismatch_detail.get("message")
        print(f"  [ok] model/fs mismatch ({alt_fs_id}) -> 400 MODEL_FEATURE_SET_MISMATCH")

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
