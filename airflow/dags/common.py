"""Airflow DAG 공통 유틸 — 백엔드 API 호출."""
from __future__ import annotations

import os
import time
import traceback
from typing import Any

import requests

DEFAULT_ARGS = {
    "owner": "thermops",
    "depends_on_past": False,
    "email_on_failure": False,
    "retries": 1,
    "retry_delay": __import__("datetime").timedelta(minutes=1),
}

BACKEND_BASE_URL = os.environ.get("THERMOPS_BACKEND_BASE_URL", "http://backend:8000/api/v1").rstrip("/")
REQUEST_TIMEOUT = int(os.environ.get("THERMOPS_BACKEND_TIMEOUT", "300"))
REQUEST_RETRIES = int(os.environ.get("THERMOPS_BACKEND_RETRIES", "2"))


def get_backend_base_url() -> str:
    return BACKEND_BASE_URL


def extract_conf(context: dict) -> dict[str, Any]:
    dag_run = context.get("dag_run")
    if dag_run and getattr(dag_run, "conf", None):
        return dict(dag_run.conf)
    return {}


def call_backend_api(
    method: str,
    path: str,
    *,
    params: dict[str, Any] | None = None,
    json_body: dict[str, Any] | None = None,
) -> Any:
    url = f"{BACKEND_BASE_URL}{path}"
    last_error: Exception | None = None
    for attempt in range(REQUEST_RETRIES + 1):
        try:
            resp = requests.request(
                method,
                url,
                params=params,
                json=json_body,
                timeout=REQUEST_TIMEOUT,
            )
            payload = resp.json()
            if resp.status_code >= 400 or not payload.get("success"):
                raise RuntimeError(
                    f"Backend API failed {method} {path} ({resp.status_code}): "
                    f"{payload.get('message')} {payload.get('data')}"
                )
            return payload.get("data")
        except Exception as exc:
            last_error = exc
            if attempt < REQUEST_RETRIES:
                time.sleep(3)
    raise RuntimeError(str(last_error))


def update_pipeline_status(
    pipeline_run_id: str | None,
    status: str,
    step_name: str | None = None,
    message: str | None = None,
    result_summary: dict[str, Any] | None = None,
) -> None:
    if not pipeline_run_id:
        return
    call_backend_api(
        "POST",
        f"/pipeline-runs/{pipeline_run_id}/status",
        json_body={
            "status": status,
            "step_name": step_name,
            "message": message,
            "result_summary": result_summary or {},
        },
    )


def log_pipeline_run(pipeline_type: str, pipeline_id: str, status: str, message: str = "") -> None:
    print(f"[{pipeline_type}] {pipeline_id} -> {status}: {message}")


def on_pipeline_task_failure(context: dict) -> None:
    """Airflow task 실패 시 pipeline_run 상태를 FAILED로 갱신."""
    conf = extract_conf(context)
    pipeline_run_id = conf.get("pipeline_run_id")
    if not pipeline_run_id:
        return

    ti = context.get("task_instance")
    step_name = ti.task_id if ti else "unknown"
    exc = context.get("exception")
    error_message = str(exc) if exc else "task failed"
    tb_text = traceback.format_exc(limit=8)[-2000:]

    try:
        update_pipeline_status(
            pipeline_run_id,
            "FAILED",
            step_name,
            f"{step_name} failed: {error_message}",
            {
                "error_message": error_message,
                "failed_step": step_name,
                "traceback": tb_text,
            },
        )
    except Exception as notify_exc:
        print(f"[pipeline_failure] status update failed: {notify_exc}")


def on_retraining_task_failure(context: dict) -> None:
    """retraining_dag task 실패 시 후보 FAILED 갱신."""
    conf = extract_conf(context)
    candidate_id = conf.get("candidate_id")
    if not candidate_id:
        print("[retraining_failure] candidate_id missing in conf")
        return

    ti = context.get("task_instance")
    step_name = ti.task_id if ti else "unknown"
    exc = context.get("exception")
    error_message = str(exc) if exc else "task failed"
    tb_text = traceback.format_exc(limit=8)[-2000:]

    try:
        call_backend_api(
            "POST",
            f"/retraining-candidates/{candidate_id}/mark-failed",
            json_body={
                "error_message": f"{step_name} failed: {error_message}",
                "failed_step": step_name,
                "traceback": tb_text,
            },
        )
    except Exception as notify_exc:
        print(f"[retraining_failure] mark-failed failed: {notify_exc}")


RETRAINING_DEFAULT_ARGS = {
    **DEFAULT_ARGS,
    "on_failure_callback": on_retraining_task_failure,
}


# 모든 DAG task에 on_failure_callback 적용
DEFAULT_ARGS["on_failure_callback"] = on_pipeline_task_failure
