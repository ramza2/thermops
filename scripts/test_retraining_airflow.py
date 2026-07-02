#!/usr/bin/env python3
"""승인 후보 Airflow retraining_dag 비동기 재학습 테스트 (P1-2 안정화)."""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from base64 import b64encode
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))
from test_fixtures import FS_LAG_ROLL_ID, ensure_test_platform

API_BASE = os.environ.get("THERMOOPS_API_BASE", "http://localhost:8000/api/v1")
AIRFLOW_BASE = os.environ.get("AIRFLOW_BASE_URL", "http://localhost:8080")
AIRFLOW_USER = os.environ.get("AIRFLOW_USERNAME", "admin")
AIRFLOW_PASS = os.environ.get("AIRFLOW_PASSWORD", "admin")
POLL_INTERVAL = int(os.environ.get("AIRFLOW_POLL_INTERVAL", "5"))
POLL_TIMEOUT = int(os.environ.get("AIRFLOW_POLL_TIMEOUT", "600"))
STARTUP_TIMEOUT = int(os.environ.get("THERMOOPS_STARTUP_TIMEOUT", "180"))
ORIGINAL_THRESHOLD = "10.0"
TEST_THRESHOLD = "0.01"
RETRAINING_DAG_ID = "retraining_dag"


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


def airflow_get(path: str, timeout: int = 30) -> dict:
    auth = b64encode(f"{AIRFLOW_USER}:{AIRFLOW_PASS}".encode()).decode()
    url = f"{AIRFLOW_BASE}/api/v1{path}"
    req = urllib.request.Request(url, method="GET", headers={"Authorization": f"Basic {auth}"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode())


def _probe_get(url: str, headers: dict | None = None, timeout: int = 5) -> bool:
    try:
        req = urllib.request.Request(url, method="GET", headers=headers or {})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status < 500
    except Exception:
        return False


def wait_for_services() -> None:
    """Backend/Airflow 기동 및 retraining_dag 로드 대기."""
    backend_health = API_BASE.rsplit("/api/v1", 1)[0] + "/health"
    airflow_health = f"{AIRFLOW_BASE.rstrip('/')}/health"
    deadline = time.time() + STARTUP_TIMEOUT
    backend_ok = False
    airflow_ok = False
    print(f"  [wait] services (timeout={STARTUP_TIMEOUT}s)...")
    while time.time() < deadline:
        if not backend_ok and _probe_get(backend_health):
            backend_ok = True
            print("  [ready] backend OK")
        if not airflow_ok and _probe_get(airflow_health):
            airflow_ok = True
            print("  [ready] airflow health OK")
        if backend_ok and airflow_ok:
            try:
                dags = airflow_get("/dags?limit=100", timeout=15)
                dag_ids = [d.get("dag_id") for d in dags.get("dags", [])]
                if RETRAINING_DAG_ID in dag_ids:
                    print(f"  [ready] {RETRAINING_DAG_ID} loaded")
                    return
            except Exception:
                pass
        time.sleep(3)
    raise RuntimeError(
        f"서비스 준비 시간 초과 ({STARTUP_TIMEOUT}s). "
        f"backend={backend_ok}, airflow={airflow_ok}. "
        "docker compose up -d 후 1~2분 대기하거나 THERMOOPS_STARTUP_TIMEOUT을 늘리세요."
    )


def set_config(key: str, value: str) -> None:
    api("PUT", f"/system-configs/{key}", {"config_value": value})


def ensure_approved(candidate_id: str) -> None:
    rows = api_get("/retraining-candidates")
    row = next((c for c in rows if c["candidate_id"] == candidate_id), None) if isinstance(rows, list) else None
    if row and row.get("status") not in ("APPROVED", "TRAINED", "TRAINING"):
        api("POST", f"/retraining-candidates/{candidate_id}/approve", {})


def create_computed_candidate() -> str:
    versions = api("GET", "/models/heat_demand_lightgbm/versions")
    mv_id = versions[0]["model_version_id"] if versions else None
    if not mv_id:
        raise RuntimeError("model_version_id 없음")

    body = {
        "model_version_id": mv_id,
        "feature_set_id": FS_LAG_ROLL_ID,
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


def wait_for_candidate_trained(candidate_id: str) -> dict:
    deadline = time.time() + POLL_TIMEOUT
    while time.time() < deadline:
        row = api_get(f"/retraining-candidates/{candidate_id}", {"sync_airflow": True})
        status = row.get("status")
        dag_run_id = row.get("retraining_dag_run_id")
        print(f"  [poll] candidate={candidate_id} status={status} dag_run={dag_run_id}")
        if status == "TRAINED":
            return row
        if status == "FAILED":
            raise RuntimeError(f"candidate FAILED: {row.get('error_message')}")
        time.sleep(POLL_INTERVAL)
    raise RuntimeError(f"timeout waiting for candidate {candidate_id} to become TRAINED")


def main() -> int:
    print(f"THERMOps retraining Airflow test ({API_BASE})")
    restored = False
    try:
        ensure_test_platform()
        wait_for_services()

        dags = airflow_get("/dags?limit=100")
        dag_ids = [d.get("dag_id") for d in dags.get("dags", [])]
        if RETRAINING_DAG_ID not in dag_ids:
            raise RuntimeError(f"{RETRAINING_DAG_ID} not loaded in Airflow: {dag_ids[:12]}")
        print(f"  [airflow] {RETRAINING_DAG_ID} loaded OK")

        pipelines = api("GET", "/pipelines")
        if not any(p.get("pipeline_id") == RETRAINING_DAG_ID for p in pipelines):
            raise RuntimeError(f"{RETRAINING_DAG_ID} missing from /pipelines")
        print("  [pipelines] retraining_dag registered OK")

        candidate_id = create_computed_candidate()
        restored = True
        print(f"  [setup] candidate_id={candidate_id}")

        api("POST", f"/retraining-candidates/{candidate_id}/approve", {})
        print("  [approve] OK")

        trigger = api("POST", f"/retraining-candidates/{candidate_id}/train?execution_mode=AIRFLOW", {})
        dag_run_id = trigger.get("retraining_dag_run_id") or trigger.get("dag_run_id")
        candidate = trigger.get("candidate") or {}
        if not dag_run_id:
            raise RuntimeError(f"retraining_dag_run_id missing: {trigger}")
        if candidate.get("status") != "TRAINING":
            raise RuntimeError(f"expected TRAINING after trigger, got {candidate.get('status')}")
        print(f"  [trigger] dag_run_id={dag_run_id}")

        final = wait_for_candidate_trained(candidate_id)
        job_id = final.get("training_job_id")
        new_mv = final.get("new_model_version_id")
        mlflow_run_id = final.get("mlflow_run_id")
        if not job_id:
            raise RuntimeError("training_job_id missing after Airflow run")
        if not new_mv:
            raise RuntimeError("new_model_version_id missing after Airflow run")
        if not mlflow_run_id:
            raise RuntimeError("mlflow_run_id missing after Airflow run")
        print(f"  [candidate] TRAINED job_id={job_id} new_model_version_id={new_mv}")

        job = api("GET", f"/training-jobs/{job_id}")
        if job.get("status") != "SUCCESS":
            raise RuntimeError(f"training job not SUCCESS: {job.get('status')}")
        print("  [training-job] SUCCESS")

        model_name = (final.get("train_result_summary") or {}).get("model_name") or "heat_demand_lightgbm_retrained"
        versions = api("GET", f"/models/{model_name}/versions")
        if not any(v.get("model_version_id") == new_mv for v in versions):
            raise RuntimeError("new model version not found in registry")
        print("  [registry] new model version OK")

        code = api_expect_fail("POST", f"/retraining-candidates/{candidate_id}/train?execution_mode=AIRFLOW")
        if code not in (400, 409):
            raise RuntimeError(f"expected re-train block, got HTTP {code}")
        print("  [guard] re-train blocked OK")

        seed_rows = api_get("/retraining-candidates", {"source_type": "SEED"})
        if isinstance(seed_rows, list) and seed_rows:
            seed_id = seed_rows[0]["candidate_id"]
            ensure_approved(seed_id)
            code = api_expect_fail("POST", f"/retraining-candidates/{seed_id}/train?execution_mode=AIRFLOW")
            if code != 400:
                raise RuntimeError(f"SEED async train should return 400, got {code}")
            print("  [guard] SEED async train blocked OK")

        print("PASSED")
        return 0
    except urllib.error.HTTPError as exc:
        body = exc.read().decode() if exc.fp else ""
        print(f"FAILED: HTTP {exc.code} ({exc.reason}) {body}", file=sys.stderr)
        return 1
    except urllib.error.URLError as exc:
        print(f"FAILED: cannot reach service ({exc})", file=sys.stderr)
        print(
            "  hint: docker compose up -d backend airflow 후 "
            "1~2분 대기하거나 THERMOOPS_STARTUP_TIMEOUT=300 으로 재실행하세요.",
            file=sys.stderr,
        )
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
