#!/usr/bin/env python3
"""승인 후보 기반 재학습 Job 생성 테스트 (P1-2)."""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

API_BASE = os.environ.get("THERMOOPS_API_BASE", "http://localhost:8000/api/v1")
ORIGINAL_THRESHOLD = "10.0"
TEST_THRESHOLD = "0.01"


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
        payload = json.loads(resp.read().decode())
    if not payload.get("success"):
        raise RuntimeError(f"API failed {method} {path}: {payload}")
    return payload["data"]


def api_get(path: str, params: dict | None = None, timeout: int = 120) -> dict:
    if params:
        query = urllib.parse.urlencode({k: str(v).lower() if isinstance(v, bool) else v for k, v in params.items()})
        path = f"{path}?{query}"
    return api("GET", path, timeout=timeout)


def api_expect_fail(method: str, path: str, body: dict | None = None, timeout: int = 60) -> int:
    url = f"{API_BASE}{path}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={"Content-Type": "application/json"} if data else {},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            payload = json.loads(resp.read().decode())
        if payload.get("success"):
            raise RuntimeError(f"expected failure but succeeded: {path}")
        return resp.status
    except urllib.error.HTTPError as exc:
        return exc.code


def ensure_approved(candidate_id: str) -> None:
    rows = api_get("/retraining-candidates")
    row = next((c for c in rows if c["candidate_id"] == candidate_id), None) if isinstance(rows, list) else None
    if row and row.get("status") not in ("APPROVED", "TRAINED", "TRAINING"):
        api("POST", f"/retraining-candidates/{candidate_id}/approve", {})


def set_config(key: str, value: str) -> None:
    api("PUT", f"/system-configs/{key}", {"config_value": value})


def create_computed_candidate() -> str:
    versions = api("GET", "/models/heat_demand_lightgbm/versions")
    mv_id = versions[0]["model_version_id"] if versions else None
    if not mv_id:
        raise RuntimeError("model_version_id 없음")

    body = {
        "model_version_id": mv_id,
        "feature_set_id": "FS-TPL-LAG-ROLL",
        "baseline_start_at": "2026-05-22T00:00:00",
        "baseline_end_at": "2026-06-05T23:00:00",
        "current_start_at": "2026-06-06T00:00:00",
        "current_end_at": "2026-06-20T23:00:00",
        "force_candidate": True,
    }
    set_config("retraining_mape_threshold", TEST_THRESHOLD)
    result = api("POST", "/drift-checks", body)
    candidate_id = result.get("retraining_candidate_id")
    if not candidate_id:
        pending = api_get("/retraining-candidates", {"computed_only": True, "status": "PENDING"})
        if isinstance(pending, list):
            for row in pending:
                if row.get("status") in ("PENDING", "REVIEW"):
                    candidate_id = row["candidate_id"]
                    break
    if not candidate_id:
        raise RuntimeError("COMPUTED 후보 생성 실패")
    return candidate_id


def main() -> int:
    print(f"THERMOps retraining candidate train test ({API_BASE})")
    restored = False
    trained_id: str | None = None
    try:
        candidate_id = create_computed_candidate()
        restored = True
        print(f"  [setup] candidate_id={candidate_id}")

        detail = api_get("/retraining-candidates", {"computed_only": True})
        rows = detail if isinstance(detail, list) else []
        row = next((c for c in rows if c["candidate_id"] == candidate_id), None)
        if row and row.get("source_type") != "COMPUTED":
            raise RuntimeError(f"expected COMPUTED source_type, got {row.get('source_type')}")

        code = api_expect_fail("POST", f"/retraining-candidates/{candidate_id}/train")
        if code not in (400, 403, 409):
            print(f"  [guard] pending train blocked with HTTP {code}")
        print("  [guard] non-approved train blocked OK")

        api("POST", f"/retraining-candidates/{candidate_id}/approve", {})
        print("  [approve] OK")

        train_result = api("POST", f"/retraining-candidates/{candidate_id}/train", {}, timeout=600)
        candidate = train_result.get("candidate") or {}
        job_id = candidate.get("training_job_id") or train_result.get("training_job", {}).get("job_id")
        new_mv = candidate.get("new_model_version_id") or train_result.get("model_version", {}).get("model_version_id")
        if not job_id:
            raise RuntimeError(f"training_job_id missing: {train_result}")
        if not new_mv:
            raise RuntimeError(f"new_model_version_id missing: {train_result}")
        if candidate.get("status") != "TRAINED":
            raise RuntimeError(f"expected TRAINED, got {candidate.get('status')}")
        print(f"  [train] job_id={job_id} new_model_version_id={new_mv}")
        trained_id = candidate_id

        job = api("GET", f"/training-jobs/{job_id}")
        if job.get("status") != "SUCCESS":
            raise RuntimeError(f"training job not SUCCESS: {job.get('status')}")
        print("  [training-job] SUCCESS")

        model_name = train_result.get("model_version", {}).get("model_name") or "heat_demand_lightgbm_retrained"
        versions = api("GET", f"/models/{model_name}/versions")
        if not any(v.get("model_version_id") == new_mv for v in versions):
            raise RuntimeError("new model version not found in registry")
        print("  [registry] new model version OK")

        code = api_expect_fail("POST", f"/retraining-candidates/{candidate_id}/train")
        if code not in (400, 409):
            raise RuntimeError(f"expected re-train block, got HTTP {code}")
        print("  [guard] re-train blocked OK")

        seed_rows = api_get("/retraining-candidates", {"source_type": "SEED"})
        if isinstance(seed_rows, list) and seed_rows:
            seed_id = seed_rows[0]["candidate_id"]
            ensure_approved(seed_id)
            code = api_expect_fail("POST", f"/retraining-candidates/{seed_id}/train")
            if code != 400:
                raise RuntimeError(f"SEED train should return 400, got {code}")
            print("  [guard] SEED train blocked OK")

        print("PASSED")
        return 0
    except urllib.error.HTTPError as exc:
        body = exc.read().decode() if exc.fp else ""
        print(f"FAILED: HTTP {exc.code} ({exc.reason}) {body}", file=sys.stderr)
        return 1
    except urllib.error.URLError as exc:
        print(f"FAILED: cannot reach API ({exc})", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"FAILED: {exc}", file=sys.stderr)
        return 1
    finally:
        if restored:
            try:
                set_config("retraining_mape_threshold", ORIGINAL_THRESHOLD)
                print("  [cleanup] retraining_mape_threshold restored")
            except Exception as exc:
                print(f"  [WARN] cleanup failed: {exc}", file=sys.stderr)


if __name__ == "__main__":
    sys.exit(main())
