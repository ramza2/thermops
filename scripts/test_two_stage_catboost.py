#!/usr/bin/env python3
"""2-Stage CatBoost 모델 학습·예측 API 통합 테스트."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))
from test_fixtures import (
    FS_TWO_STAGE_ID,
    TRC_TWO_STAGE_ID,
    ensure_csv_ingested,
    ensure_feature_dataset_built,
    ensure_test_platform,
    ensure_test_training_configs,
)

API_BASE = os.environ.get("THERMOOPS_API_BASE", "http://localhost:8000/api/v1")
DB_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://thermops:thermops@localhost:5432/thermops",
)
FEATURE_SET_ID = os.environ.get("THERMOOPS_FEATURE_SET_ID", FS_TWO_STAGE_ID)
TRAINING_CONFIG_ID = os.environ.get("THERMOOPS_TRAINING_CONFIG_ID", TRC_TWO_STAGE_ID)


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
        raise RuntimeError(f"API failed {path}: {payload}")
    return payload["data"]


def psql_scalar(sql: str) -> str:
    try:
        import psycopg2
    except ImportError:
        out = subprocess.check_output(
            [
                "docker", "exec", "thermops-postgres", "psql", "-U", "thermops", "-d", "thermops",
                "-t", "-A", "-c", sql,
            ],
            text=True,
        )
        return out.strip()
    conn = psycopg2.connect(DB_URL.replace("+asyncpg", ""))
    try:
        with conn.cursor() as cur:
            cur.execute(sql)
            row = cur.fetchone()
            return str(row[0]).strip() if row and row[0] is not None else ""
    finally:
        conn.close()


def ensure_feature_dataset() -> None:
    ensure_feature_dataset_built(api, FEATURE_SET_ID, timeout=180)


def resolve_training_config_id() -> str:
    ensure_test_training_configs()
    configs = api("GET", "/training-configs")
    for cfg in configs:
        if cfg.get("config_id") == TRAINING_CONFIG_ID:
            return TRAINING_CONFIG_ID
        if cfg.get("feature_set_id") == FEATURE_SET_ID and "two_stage" in cfg.get("algorithm", "").lower():
            return cfg["config_id"]

    created = api("POST", "/training-configs", {
        "config_name": "Test 2-Stage CatBoost",
        "feature_set_id": FEATURE_SET_ID,
        "algorithm": "two_stage_catboost",
        "train_period_months": 1,
        "validation_period_months": 1,
        "hyperparams": {"validation_ratio": 0.2, "iterations": 50, "learning_rate": 0.05, "depth": 6},
    })
    return created.get("config_id") or TRAINING_CONFIG_ID


def ensure_minio_bucket() -> None:
    try:
        subprocess.run(
            [
                "docker", "exec", "thermops-backend", "python", "-c",
                "import boto3; s3=boto3.client('s3',endpoint_url='http://minio:9000',"
                "aws_access_key_id='minioadmin',aws_secret_access_key='minioadmin');"
                "s3.create_bucket(Bucket='mlflow')",
            ],
            check=False,
            capture_output=True,
            text=True,
        )
    except Exception:
        pass


def prediction_period(feature_set_id: str) -> tuple[str, str]:
    data = api("GET", f"/feature-sets/{feature_set_id}/dataset-range")
    if data.get("exists") and data.get("min_target_at") and data.get("max_target_at"):
        return data["min_target_at"], data["max_target_at"]
    now = datetime.now(timezone.utc)
    return (now - timedelta(days=7)).isoformat(), now.isoformat()


def run_prediction(model_version_id: str, feature_set_id: str) -> None:
    start_at, end_at = prediction_period(feature_set_id)
    before = int(psql_scalar(
        f"SELECT COUNT(*) FROM tb_heat_demand_prediction WHERE model_version_id = '{model_version_id}'"
    ) or "0")

    result = api("POST", "/prediction-jobs", {
        "feature_set_id": feature_set_id,
        "model_version_id": model_version_id,
        "start_at": start_at,
        "end_at": end_at,
        "prediction_horizon": "BATCH",
        "overwrite_yn": True,
    }, timeout=300)

    if result.get("status") != "SUCCESS":
        raise RuntimeError(f"prediction failed: {result}")

    after = int(psql_scalar(
        f"SELECT COUNT(*) FROM tb_heat_demand_prediction WHERE model_version_id = '{model_version_id}'"
    ) or "0")
    if after <= before:
        raise RuntimeError("prediction results were not saved")


def main() -> int:
    print(f"THERMOps 2-Stage CatBoost training test ({API_BASE})")
    try:
        ensure_test_platform()
        ensure_csv_ingested(api)
        ensure_minio_bucket()
        ensure_feature_dataset()
        config_id = resolve_training_config_id()
        print(f"  [config] config_id={config_id}")

        before_versions = int(psql_scalar("SELECT COUNT(*) FROM tb_model_version") or "0")

        result = api("POST", "/training-jobs", {"config_id": config_id, "register_model_yn": True}, timeout=900)
        job_id = result["job_id"]
        print(f"  [train] job_id={job_id} status={result.get('status')}")

        if result.get("status") != "SUCCESS":
            raise RuntimeError(f"training failed: {result}")

        job = api("GET", f"/training-jobs/{job_id}")
        if job.get("status") != "SUCCESS":
            raise RuntimeError(f"job status not SUCCESS: {job}")

        metrics = job.get("metrics") or result.get("metrics") or {}
        for key in ("mape", "mae", "rmse", "r2"):
            if key not in metrics:
                raise RuntimeError(f"missing metric: {key}")
        print(
            f"  [metrics] MAPE={metrics.get('mape')} MAE={metrics.get('mae')} "
            f"stage1_mape={metrics.get('stage1_validation_mape')}"
        )

        mlflow_run_id = job.get("mlflow_run_id") or result.get("mlflow_run_id")
        if not mlflow_run_id:
            raise RuntimeError("mlflow_run_id missing")
        print(f"  [mlflow] run_id={mlflow_run_id}")

        experiment = psql_scalar(
            f"SELECT algorithm FROM tb_model_experiment WHERE mlflow_run_id = '{mlflow_run_id}'"
        )
        if experiment and "two_stage" not in experiment.lower():
            print(f"  [warn] experiment algorithm={experiment}")

        model_version_id = result.get("model_version_id") or job.get("model_version_id")
        if not model_version_id:
            raise RuntimeError("model_version_id missing")

        db_count = psql_scalar("SELECT COUNT(*) FROM tb_model_version")
        if int(db_count) <= before_versions:
            raise RuntimeError("tb_model_version row was not created")

        model_name = result.get("model_name") or job.get("registered_model_name")
        if model_name and "two_stage" not in model_name:
            print(f"  [warn] unexpected model_name={model_name}")

        print(f"  [DB] model_version_id={model_version_id}")
        run_prediction(model_version_id, FEATURE_SET_ID)
        print("  [predict] prediction job SUCCESS")

        print("\nPASSED: 2-Stage CatBoost training flow")
        return 0
    except (urllib.error.URLError, RuntimeError, KeyError) as exc:
        print(f"\nFAILED: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
