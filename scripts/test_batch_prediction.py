#!/usr/bin/env python3
"""배치 예측 API 통합 테스트."""

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
from test_http_debug import api_error_summary

API_BASE = os.environ.get("THERMOOPS_API_BASE", "http://localhost:8000/api/v1")
DB_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://thermops:thermops@localhost:5432/thermops",
)
FEATURE_SET_ID = os.environ.get("THERMOOPS_FEATURE_SET_ID", "FS-TPL-LAG-ROLL")


def api(method: str, path: str, body: dict | None = None, timeout: int = 300) -> dict:
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
    except urllib.error.HTTPError as exc:
        raise RuntimeError(api_error_summary(method, path, exc)) from exc
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


def ensure_schema() -> None:
    sql = """
    ALTER TABLE tb_prediction_job ADD COLUMN IF NOT EXISTS started_at TIMESTAMP;
    ALTER TABLE tb_prediction_job ADD COLUMN IF NOT EXISTS result_summary JSONB;
    ALTER TABLE tb_prediction_job ADD COLUMN IF NOT EXISTS error_message TEXT;
    ALTER TABLE tb_heat_demand_prediction ADD COLUMN IF NOT EXISTS feature_set_id VARCHAR(50);
    CREATE UNIQUE INDEX IF NOT EXISTS uk_heat_pred_site_model_time
        ON tb_heat_demand_prediction(site_id, target_at, model_version_id);
    """
    try:
        subprocess.run(
            ["docker", "exec", "-i", "thermops-postgres", "psql", "-U", "thermops", "-d", "thermops", "-c", sql],
            check=True,
            capture_output=True,
            text=True,
        )
    except Exception:
        pass


def ensure_feature_dataset() -> None:
    count = psql_scalar(
        f"SELECT COUNT(*) FROM tb_feature_dataset WHERE feature_json->>'feature_set_id' = '{FEATURE_SET_ID}'"
    )
    if count and int(count) > 0:
        print(f"  [feature] existing rows={count}")
        return
    print("  [feature] building feature dataset...")
    api("POST", f"/feature-build-jobs?feature_set_id={FEATURE_SET_ID}", timeout=180)


def find_compatible_model_version(feature_set_id: str) -> str | None:
    sql = f"""
    SELECT mv.model_version_id
    FROM tb_model_version mv
    JOIN tb_model_experiment me ON mv.experiment_id = me.experiment_id
    WHERE me.parameter_json->>'feature_set_id' = '{feature_set_id}'
    ORDER BY
      CASE WHEN mv.model_name LIKE '%lightgbm%' THEN 0 ELSE 1 END,
      mv.registered_at DESC
    LIMIT 1
    """
    return psql_scalar(sql) or None


def ensure_trained_model() -> str:
    row = find_compatible_model_version(FEATURE_SET_ID)
    if row:
        print(f"  [model] compatible model_version_id={row}")
        return row

    print("  [train] no compatible model found, running LightGBM training...")
    configs = api("GET", "/training-configs")
    config_id = next(
        (
            c["config_id"]
            for c in configs
            if c.get("feature_set_id") == FEATURE_SET_ID
            and "lightgbm" in c.get("algorithm", "").lower()
        ),
        None,
    )
    if not config_id:
        config_id = next(
            (c["config_id"] for c in configs if c.get("feature_set_id") == FEATURE_SET_ID),
            configs[0]["config_id"] if configs else None,
        )
    if not config_id:
        raise RuntimeError("training config not found")
    result = api("POST", "/training-jobs", {"config_id": config_id}, timeout=300)
    if result.get("status") != "SUCCESS":
        raise RuntimeError(f"training failed: {result}")
    model_version_id = result.get("model_version_id")
    if not model_version_id:
        raise RuntimeError("model_version_id missing after training")
    return model_version_id


def prediction_period() -> tuple[str, str]:
    data = api("GET", f"/feature-sets/{FEATURE_SET_ID}/dataset-range")
    if data.get("exists") and data.get("min_target_at") and data.get("max_target_at"):
        return data["min_target_at"], data["max_target_at"]
    now = datetime.now(timezone.utc)
    return (now - timedelta(days=7)).isoformat(), now.isoformat()


def main() -> int:
    print(f"THERMOps batch prediction test ({API_BASE})")
    try:
        ensure_schema()
        models = api("GET", "/models")
        print(f"  [list] models: {len(models)}")

        ensure_feature_dataset()
        model_version_id = ensure_trained_model()
        print(f"  [model] model_version_id={model_version_id}")

        start_at, end_at = prediction_period()
        before = int(psql_scalar("SELECT COUNT(*) FROM tb_heat_demand_prediction") or "0")

        result = api("POST", "/prediction-jobs", {
            "feature_set_id": FEATURE_SET_ID,
            "model_version_id": model_version_id,
            "start_at": start_at,
            "end_at": end_at,
            "prediction_horizon": "BATCH",
            "overwrite_yn": True,
        }, timeout=300)

        job_id = result["job_id"]
        print(f"  [predict] job_id={job_id} status={result.get('status')}")
        if result.get("status") != "SUCCESS":
            raise RuntimeError(f"prediction failed: {result}")

        predicted_count = result.get("predicted_count", 0)
        if predicted_count <= 0:
            raise RuntimeError("predicted_count is 0")

        job = api("GET", f"/prediction-jobs/{job_id}")
        if job.get("status") != "SUCCESS":
            raise RuntimeError(f"job status not SUCCESS: {job}")

        after = int(psql_scalar("SELECT COUNT(*) FROM tb_heat_demand_prediction") or "0")
        if after <= before and predicted_count > 0:
            print(f"  [WARN] row count {before}->{after} (upsert may have updated existing rows)")

        db_rows = psql_scalar(
            f"SELECT COUNT(*) FROM tb_heat_demand_prediction WHERE prediction_job_id = '{job_id}'"
        )
        if not db_rows or int(db_rows) <= 0:
            raise RuntimeError("tb_heat_demand_prediction has no rows for job")

        preds = api("GET", f"/predictions?model_version_id={model_version_id}&size=5")
        items = preds.get("items") if isinstance(preds, dict) else preds
        if not items:
            raise RuntimeError("GET /predictions returned empty")
        first = items[0]
        for key in ("predicted_demand", "target_at", "site_id", "model_version_id"):
            if key not in first:
                raise RuntimeError(f"GET /predictions missing field: {key}")
        if "actual_demand" not in first:
            raise RuntimeError("GET /predictions missing actual_demand (nullable expected)")

        summary = api("GET", f"/predictions/summary?model_version_id={model_version_id}")
        if summary.get("count", 0) <= 0:
            raise RuntimeError("GET /predictions/summary count is 0")

        print(f"  [DB] prediction rows for job={db_rows}")
        print(f"  [summary] count={summary.get('count')} avg={summary.get('avg_predicted_demand')}")

        print("\nPASSED: batch prediction flow")
        return 0
    except (urllib.error.URLError, RuntimeError, KeyError) as exc:
        print(f"\nFAILED: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
