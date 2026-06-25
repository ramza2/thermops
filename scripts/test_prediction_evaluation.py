#!/usr/bin/env python3
"""예측 성능 평가 API 통합 테스트 (P0-6)."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone

API_BASE = os.environ.get("THERMOOPS_API_BASE", "http://localhost:8000/api/v1")
DB_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://thermops:thermops@localhost:5432/thermops",
)


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


def ensure_schema() -> None:
    sql = """
    ALTER TABLE tb_model_performance_metric ADD COLUMN IF NOT EXISTS metric_json JSONB;
    ALTER TABLE tb_model_performance_metric ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT NOW();
    CREATE TABLE IF NOT EXISTS tb_prediction_actual_match (
        match_id BIGSERIAL PRIMARY KEY,
        prediction_id BIGINT NOT NULL REFERENCES tb_heat_demand_prediction(prediction_id),
        site_id VARCHAR(50) NOT NULL REFERENCES tb_site(site_id),
        target_at TIMESTAMP NOT NULL,
        model_version_id VARCHAR(80) NOT NULL REFERENCES tb_model_version(model_version_id),
        prediction_job_id VARCHAR(80),
        predicted_demand NUMERIC(18,6) NOT NULL,
        actual_demand NUMERIC(18,6) NOT NULL,
        error NUMERIC(18,6),
        abs_error NUMERIC(18,6),
        squared_error NUMERIC(18,6),
        ape NUMERIC(18,6),
        created_at TIMESTAMP NOT NULL DEFAULT NOW(),
        CONSTRAINT uk_pred_actual_match_prediction UNIQUE(prediction_id)
    );
    CREATE UNIQUE INDEX IF NOT EXISTS uk_pred_actual_match_site_time_model
        ON tb_prediction_actual_match(site_id, target_at, model_version_id);
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


def ensure_predictions_exist() -> tuple[str, str, str, str]:
    model_version_id = psql_scalar(
        "SELECT model_version_id FROM tb_heat_demand_prediction "
        "GROUP BY model_version_id ORDER BY COUNT(*) DESC LIMIT 1"
    )
    if not model_version_id:
        latest = psql_scalar(
            "SELECT model_version_id FROM tb_model_version ORDER BY registered_at DESC LIMIT 1"
        )
        if not latest:
            raise RuntimeError("trained model not found — run test_model_training.py first")
        raise RuntimeError("predictions not found — run test_batch_prediction.py first")

    pred_count = int(psql_scalar(
        f"SELECT COUNT(*) FROM tb_heat_demand_prediction WHERE model_version_id = '{model_version_id}'"
    ) or "0")
    if pred_count <= 0:
        raise RuntimeError("predictions not found — run test_batch_prediction.py first")

    job_id = psql_scalar(
        f"SELECT prediction_job_id FROM tb_heat_demand_prediction "
        f"WHERE model_version_id = '{model_version_id}' ORDER BY target_at DESC LIMIT 1"
    )
    start_at = psql_scalar(
        f"SELECT MIN(target_at)::text FROM tb_heat_demand_prediction WHERE model_version_id = '{model_version_id}'"
    )
    end_at = psql_scalar(
        f"SELECT MAX(target_at)::text FROM tb_heat_demand_prediction WHERE model_version_id = '{model_version_id}'"
    )
    return model_version_id, job_id or "", start_at, end_at


def main() -> int:
    print(f"THERMOps prediction evaluation test ({API_BASE})")
    try:
        ensure_schema()

        model_version_id, job_id, start_at, end_at = ensure_predictions_exist()
        print(f"  [model] model_version_id={model_version_id}")
        print(f"  [period] {start_at} ~ {end_at}")

        actual_count = int(psql_scalar("SELECT COUNT(*) FROM tb_heat_demand_actual") or "0")
        if actual_count <= 0:
            raise RuntimeError("actual demand data not found — run test_csv_ingestion.py first")
        print(f"  [actual] rows={actual_count}")

        body: dict = {
            "model_version_id": model_version_id,
            "start_at": start_at,
            "end_at": end_at,
        }
        if job_id:
            body["prediction_job_id"] = job_id

        result = api("POST", "/predictions/evaluate", body, timeout=300)
        print(f"  [evaluate] status={result.get('status')} matched={result.get('matched_count')}")

        if result.get("status") != "SUCCESS":
            raise RuntimeError(f"evaluation failed: {result}")
        if result.get("matched_count", 0) <= 0:
            raise RuntimeError("matched_count is 0")

        summary = result.get("metric_summary") or {}
        for key in ("mape", "mae", "rmse", "r2"):
            if key not in summary or summary[key] is None:
                raise RuntimeError(f"metric_summary missing {key}: {summary}")
        print(f"  [metrics] MAPE={summary['mape']:.2f} MAE={summary['mae']:.2f} RMSE={summary['rmse']:.2f} R2={summary['r2']:.3f}")

        db_match = int(psql_scalar("SELECT COUNT(*) FROM tb_prediction_actual_match") or "0")
        if db_match <= 0:
            raise RuntimeError("tb_prediction_actual_match is empty")
        print(f"  [DB] match rows={db_match}")

        errors = api("GET", f"/predictions/errors?model_version_id={model_version_id}&size=10")
        if not errors.get("items"):
            raise RuntimeError("GET /predictions/errors returned empty")
        item = errors["items"][0]
        for field in ("actual_demand", "predicted_demand", "error", "abs_error"):
            if field not in item:
                raise RuntimeError(f"errors item missing {field}")
        print(f"  [errors] count={errors.get('total_count', len(errors['items']))}")

        perf = api("GET", f"/performance-metrics?model_version_id={model_version_id}&eval_type=PREDICTION_ACTUAL_MATCH")
        if not perf.get("metrics"):
            raise RuntimeError("GET /performance-metrics returned empty metrics")
        pm = perf["metrics"][0]
        if pm.get("mape") is None:
            raise RuntimeError("performance metric mape is null")
        print(f"  [perf] sites={len(perf['metrics'])} mape={pm.get('mape')}")

        overview = api("GET", "/dashboard/overview")
        if overview.get("avg_mape_7d") is None:
            print("  [WARN] dashboard avg_mape_7d is null (may be outside 7d window)")
        else:
            print(f"  [dashboard] avg_mape_7d={overview['avg_mape_7d']}")

        print("\nPASSED: prediction evaluation flow")
        return 0
    except (urllib.error.URLError, RuntimeError, KeyError) as exc:
        print(f"\nFAILED: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
