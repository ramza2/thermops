#!/usr/bin/env python3
"""thermops_full_pipeline_dag E2E Airflow 통합 테스트."""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request
from base64 import b64encode

API_BASE = os.environ.get("THERMOOPS_API_BASE", "http://localhost:8000/api/v1")
AIRFLOW_BASE = os.environ.get("AIRFLOW_BASE_URL", "http://localhost:8080")
AIRFLOW_USER = os.environ.get("AIRFLOW_USERNAME", "admin")
AIRFLOW_PASS = os.environ.get("AIRFLOW_PASSWORD", "admin")
POLL_INTERVAL = int(os.environ.get("AIRFLOW_POLL_INTERVAL", "10"))
POLL_TIMEOUT = int(os.environ.get("FULL_PIPELINE_POLL_TIMEOUT", "1200"))
FULL_PIPELINE_DAG = "thermops_full_pipeline_dag"

EXPECTED_STEPS = (
    "data_ingestion",
    "data_quality",
    "feature_build",
    "model_training",
    "batch_prediction",
    "prediction_evaluation",
)


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


def airflow_get(path: str, timeout: int = 30) -> dict:
    auth = b64encode(f"{AIRFLOW_USER}:{AIRFLOW_PASS}".encode()).decode()
    url = f"{AIRFLOW_BASE}/api/v1{path}"
    req = urllib.request.Request(url, method="GET", headers={"Authorization": f"Basic {auth}"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode())


def wait_for_run(run_id: str) -> dict:
    deadline = time.time() + POLL_TIMEOUT
    while time.time() < deadline:
        run = api("GET", f"/pipeline-runs/{run_id}?sync_airflow=true", timeout=60)
        status = run.get("run_status")
        steps = (run.get("result_summary") or {}).get("steps") or {}
        print(f"  [poll] status={status} steps={list(steps.keys())}")
        if status in ("SUCCESS", "FAILED"):
            return run
        time.sleep(POLL_INTERVAL)
    raise RuntimeError(f"timeout ({POLL_TIMEOUT}s) waiting for pipeline run {run_id}")


def assert_xcom_chain(summary: dict) -> None:
    steps = summary.get("steps") or {}
    train = steps.get("model_training") or {}
    predict = steps.get("batch_prediction") or {}
    evaluate = steps.get("prediction_evaluation") or {}
    if train.get("model_version_id") and predict.get("model_version_id"):
        if train["model_version_id"] != predict["model_version_id"]:
            raise RuntimeError("model_version_id XCom chain mismatch")
    if predict.get("prediction_job_id") and evaluate.get("prediction_job_id"):
        if predict["prediction_job_id"] != evaluate["prediction_job_id"]:
            raise RuntimeError("prediction_job_id XCom chain mismatch")


def main() -> int:
    print(f"THERMOps full pipeline E2E test (timeout={POLL_TIMEOUT}s)")
    try:
        pipelines = api("GET", "/pipelines")
        full = next((p for p in pipelines if p.get("pipeline_id") == FULL_PIPELINE_DAG), None)
        if not full:
            raise RuntimeError(f"{FULL_PIPELINE_DAG} not found in /pipelines")

        trigger = api("POST", f"/pipelines/{FULL_PIPELINE_DAG}/trigger", {
            "business_date": "2026-06-20",
            "parameters": {
                "source_id": "DS-CSV-001",
                "weather_source_id": "DS-CSV-002",
                "feature_set_id": "FS-TPL-LAG-ROLL",
                "config_id": "TRC-TPL-LAG-ROLL",
                "model_name": "heat_demand_lightgbm",
                "data_domain": "HEAT_DEMAND",
                "start_at": "2026-06-01",
                "end_at": "2026-06-20",
            },
        })
        run_id = trigger.get("pipeline_run_id")
        dag_run_id = trigger.get("orchestrator_run_id") or trigger.get("dag_run_id")
        if not run_id or not dag_run_id:
            raise RuntimeError(f"invalid trigger response: {trigger}")
        print(f"  [trigger] run_id={run_id} dag_run_id={dag_run_id}")

        final = wait_for_run(run_id)
        status = final.get("run_status")
        summary = final.get("result_summary") or {}
        steps = summary.get("steps") or {}

        if status != "SUCCESS":
            print(f"  [FAILED] message={final.get('message')}")
            print(f"  [FAILED] summary={json.dumps(summary, ensure_ascii=False)[:2000]}")
            raise RuntimeError(f"full pipeline ended with {status}")

        missing = [s for s in EXPECTED_STEPS if s not in steps]
        if missing:
            raise RuntimeError(f"missing step results: {missing}")

        assert_xcom_chain(summary)
        print(f"  [SUCCESS] steps={list(steps.keys())}")
        print(f"  [SUCCESS] model_version_id={steps.get('model_training', {}).get('model_version_id')}")
        print(f"  [SUCCESS] prediction_job_id={steps.get('batch_prediction', {}).get('prediction_job_id')}")
        print(f"  [SUCCESS] matched_count={steps.get('prediction_evaluation', {}).get('matched_count')}")

        airflow_deadline = time.time() + 60
        airflow_state = None
        while time.time() < airflow_deadline:
            dag_run = airflow_get(f"/dags/{FULL_PIPELINE_DAG}/dagRuns/{dag_run_id}")
            airflow_state = dag_run.get("state")
            if airflow_state == "success":
                break
            if airflow_state == "failed":
                raise RuntimeError(f"Airflow dag_run state={airflow_state}")
            time.sleep(5)
        if airflow_state != "success":
            print(f"  [WARN] Airflow state={airflow_state} (DB already SUCCESS)")

        print("PASSED")
        return 0
    except urllib.error.URLError as exc:
        print(f"FAILED: cannot reach service ({exc})", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"FAILED: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
