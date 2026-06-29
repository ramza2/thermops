#!/usr/bin/env python3
"""Airflow DAG 연동 파이프라인 API 통합 테스트."""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from base64 import b64encode

API_BASE = os.environ.get("THERMOOPS_API_BASE", "http://localhost:8000/api/v1")
AIRFLOW_BASE = os.environ.get("AIRFLOW_BASE_URL", "http://localhost:8080")
AIRFLOW_USER = os.environ.get("AIRFLOW_USERNAME", "admin")
AIRFLOW_PASS = os.environ.get("AIRFLOW_PASSWORD", "admin")
POLL_INTERVAL = int(os.environ.get("AIRFLOW_POLL_INTERVAL", "5"))
POLL_TIMEOUT = int(os.environ.get("AIRFLOW_POLL_TIMEOUT", "180"))
TEST_DAG = os.environ.get("THERMOOPS_TEST_DAG", "data_quality_dag")


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
        run = api("GET", f"/pipeline-runs/{run_id}?sync_airflow=true")
        status = run.get("run_status")
        print(f"  [poll] run_id={run_id} status={status}")
        if status in ("SUCCESS", "FAILED"):
            return run
        time.sleep(POLL_INTERVAL)
    raise RuntimeError(f"timeout waiting for pipeline run {run_id}")


def main() -> int:
    print(f"THERMOps Airflow pipeline test (API={API_BASE}, Airflow={AIRFLOW_BASE})")
    try:
        health = airflow_get("/health")
        print(f"  [airflow] health={health}")

        dags = airflow_get("/dags?limit=50")
        dag_ids = [d.get("dag_id") for d in dags.get("dags", [])]
        print(f"  [airflow] dags={len(dag_ids)}")
        if TEST_DAG not in dag_ids:
            print(f"  [WARN] {TEST_DAG} not in Airflow DAG list yet: {dag_ids[:10]}")

        pipelines = api("GET", "/pipelines")
        print(f"  [pipelines] count={len(pipelines)} source={pipelines[0].get('source') if pipelines else 'n/a'}")
        if not any(p.get("pipeline_id") == TEST_DAG for p in pipelines):
            raise RuntimeError(f"{TEST_DAG} missing from /pipelines")

        trigger = api("POST", f"/pipelines/{TEST_DAG}/trigger", {
            "business_date": "2026-06-20",
            "parameters": {"data_domain": "HEAT_DEMAND"},
        })
        run_id = trigger.get("pipeline_run_id")
        dag_run_id = trigger.get("orchestrator_run_id") or trigger.get("dag_run_id")
        if not run_id:
            raise RuntimeError(f"trigger response missing pipeline_run_id: {trigger}")
        print(f"  [trigger] pipeline_run_id={run_id} dag_run_id={dag_run_id} status={trigger.get('status')}")

        detail = api("GET", f"/pipeline-runs/{run_id}?sync_airflow=true")
        if not detail.get("orchestrator_run_id") and dag_run_id:
            raise RuntimeError("orchestrator_run_id not stored on pipeline run")
        print(f"  [detail] orchestrator_run_id={detail.get('orchestrator_run_id')} status={detail.get('run_status')}")

        final = wait_for_run(run_id)
        if final.get("run_status") not in ("SUCCESS", "RUNNING"):
            if final.get("run_status") == "FAILED":
                print(f"  [result] FAILED message={final.get('message')}")
                print(f"  [result] summary={final.get('result_summary')}")
                raise RuntimeError("pipeline run ended with FAILED")
        print(f"  [result] status={final.get('run_status')} summary_keys={list((final.get('result_summary') or {}).keys())}")

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
