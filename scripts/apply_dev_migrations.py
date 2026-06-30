#!/usr/bin/env python3
"""개발용 DB 스키마 보완 (기존 볼륨 마이그레이션)."""

from __future__ import annotations

import os
import subprocess
import sys

DB_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://thermops:thermops@localhost:5432/thermops",
)

MIGRATIONS = [
    (
        "tb_pipeline_run.result_summary",
        "ALTER TABLE tb_pipeline_run ADD COLUMN IF NOT EXISTS result_summary JSONB;",
    ),
    (
        "tb_drift_report P1-1 columns",
        """
        ALTER TABLE tb_drift_report ADD COLUMN IF NOT EXISTS feature_set_id VARCHAR(50);
        ALTER TABLE tb_drift_report ADD COLUMN IF NOT EXISTS site_id VARCHAR(50);
        ALTER TABLE tb_drift_report ADD COLUMN IF NOT EXISTS baseline_start_at TIMESTAMP;
        ALTER TABLE tb_drift_report ADD COLUMN IF NOT EXISTS baseline_end_at TIMESTAMP;
        ALTER TABLE tb_drift_report ADD COLUMN IF NOT EXISTS current_start_at TIMESTAMP;
        ALTER TABLE tb_drift_report ADD COLUMN IF NOT EXISTS current_end_at TIMESTAMP;
        ALTER TABLE tb_drift_report ADD COLUMN IF NOT EXISTS drift_type VARCHAR(20);
        ALTER TABLE tb_drift_report ADD COLUMN IF NOT EXISTS drift_score NUMERIC(10,6);
        ALTER TABLE tb_drift_report ADD COLUMN IF NOT EXISTS recommendation TEXT;
        """,
    ),
    (
        "tb_retraining_candidate P1-1 columns",
        """
        ALTER TABLE tb_retraining_candidate ADD COLUMN IF NOT EXISTS model_version_id VARCHAR(80);
        ALTER TABLE tb_retraining_candidate ADD COLUMN IF NOT EXISTS feature_set_id VARCHAR(50);
        ALTER TABLE tb_retraining_candidate ADD COLUMN IF NOT EXISTS reason_type VARCHAR(50);
        ALTER TABLE tb_retraining_candidate ADD COLUMN IF NOT EXISTS severity VARCHAR(20);
        ALTER TABLE tb_retraining_candidate ADD COLUMN IF NOT EXISTS reason_summary VARCHAR(500);
        ALTER TABLE tb_retraining_candidate ADD COLUMN IF NOT EXISTS metric_snapshot_json JSONB;
        ALTER TABLE tb_retraining_candidate ADD COLUMN IF NOT EXISTS drift_report_id VARCHAR(80);
        """,
    ),
    (
        "source_type columns (P1-1 stabilization)",
        """
        ALTER TABLE tb_drift_report ADD COLUMN IF NOT EXISTS source_type VARCHAR(20);
        ALTER TABLE tb_retraining_candidate ADD COLUMN IF NOT EXISTS source_type VARCHAR(20);
        UPDATE tb_drift_report SET source_type = 'COMPUTED'
          WHERE source_type IS NULL AND COALESCE(drift_score_json->>'computed', 'false') = 'true';
        UPDATE tb_drift_report SET source_type = 'SEED' WHERE source_type IS NULL;
        UPDATE tb_retraining_candidate SET source_type = 'COMPUTED'
          WHERE source_type IS NULL AND drift_report_id IS NOT NULL AND model_version_id IS NOT NULL;
        UPDATE tb_retraining_candidate SET source_type = 'SEED' WHERE source_type IS NULL;
        """,
    ),
    (
        "tb_retraining_candidate P1-2 train columns",
        """
        ALTER TABLE tb_retraining_candidate ADD COLUMN IF NOT EXISTS training_job_id VARCHAR(80);
        ALTER TABLE tb_retraining_candidate ADD COLUMN IF NOT EXISTS new_model_version_id VARCHAR(80);
        ALTER TABLE tb_retraining_candidate ADD COLUMN IF NOT EXISTS mlflow_run_id VARCHAR(80);
        ALTER TABLE tb_retraining_candidate ADD COLUMN IF NOT EXISTS trained_at TIMESTAMP;
        ALTER TABLE tb_retraining_candidate ADD COLUMN IF NOT EXISTS train_result_summary JSONB;
        ALTER TABLE tb_retraining_candidate ADD COLUMN IF NOT EXISTS error_message TEXT;
        """,
    ),
    (
        "tb_retraining_candidate P1-2 airflow columns",
        """
        ALTER TABLE tb_retraining_candidate ADD COLUMN IF NOT EXISTS retraining_dag_run_id VARCHAR(120);
        ALTER TABLE tb_retraining_candidate ADD COLUMN IF NOT EXISTS retraining_requested_at TIMESTAMP;
        ALTER TABLE tb_retraining_candidate ADD COLUMN IF NOT EXISTS retraining_started_at TIMESTAMP;
        ALTER TABLE tb_retraining_candidate ADD COLUMN IF NOT EXISTS retraining_finished_at TIMESTAMP;
        ALTER TABLE tb_retraining_candidate ADD COLUMN IF NOT EXISTS execution_mode VARCHAR(20);
        """,
    ),
    (
        "ix_heat_prediction_model_time",
        "CREATE INDEX IF NOT EXISTS ix_heat_prediction_model_time ON tb_heat_demand_prediction(model_version_id, target_at DESC);",
    ),
    (
        "external connector sample tables",
        """
        CREATE TABLE IF NOT EXISTS external_heat_demand_sample (
            site_id VARCHAR(50) NOT NULL,
            measured_at TIMESTAMP NOT NULL,
            heat_demand NUMERIC(18,6) NOT NULL,
            supply_temp NUMERIC(18,6)
        );
        CREATE TABLE IF NOT EXISTS external_weather_sample (
            weather_area_id VARCHAR(50) NOT NULL,
            measured_at TIMESTAMP NOT NULL,
            temperature NUMERIC(18,6),
            humidity NUMERIC(18,6),
            rainfall NUMERIC(18,6),
            wind_speed NUMERIC(18,6),
            data_type VARCHAR(20) DEFAULT 'OBSERVATION'
        );
        INSERT INTO external_heat_demand_sample (site_id, measured_at, heat_demand, supply_temp)
        SELECT site_id, measured_at, heat_demand, supply_temp
        FROM tb_heat_demand_actual
        WHERE NOT EXISTS (SELECT 1 FROM external_heat_demand_sample LIMIT 1)
        LIMIT 500;
        INSERT INTO external_weather_sample (weather_area_id, measured_at, temperature, humidity, rainfall, wind_speed, data_type)
        SELECT weather_area_id, measured_at, temperature, humidity, rainfall, wind_speed, data_type
        FROM tb_weather_observation
        WHERE NOT EXISTS (SELECT 1 FROM external_weather_sample LIMIT 1)
        LIMIT 500;
        """,
    ),
    (
        "tb_feature_lineage",
        """
        CREATE TABLE IF NOT EXISTS tb_feature_lineage (
            lineage_id BIGSERIAL PRIMARY KEY,
            dataset_version_id VARCHAR(80) NOT NULL REFERENCES tb_dataset_version(dataset_version_id),
            feature_build_job_id VARCHAR(80),
            feature_set_id VARCHAR(50) NOT NULL,
            feature_name VARCHAR(100) NOT NULL,
            registry_version VARCHAR(20) NOT NULL DEFAULT '1.0',
            calc_method VARCHAR(20) NOT NULL DEFAULT 'CODE',
            calc_expression TEXT,
            source_tables JSONB,
            source_columns JSONB,
            partition_keys JSONB,
            time_key VARCHAR(50),
            lookback_hours INTEGER,
            requires_shift BOOLEAN,
            leakage_safe BOOLEAN,
            build_start_at TIMESTAMP,
            build_end_at TIMESTAMP,
            site_filter VARCHAR(50),
            lineage_json JSONB,
            created_at TIMESTAMP NOT NULL DEFAULT NOW()
        );
        CREATE INDEX IF NOT EXISTS ix_feature_lineage_dsv ON tb_feature_lineage(dataset_version_id);
        CREATE INDEX IF NOT EXISTS ix_feature_lineage_job ON tb_feature_lineage(feature_build_job_id);
        CREATE UNIQUE INDEX IF NOT EXISTS ux_feature_lineage_dsv_feature ON tb_feature_lineage(dataset_version_id, feature_name);
        """,
    ),
    (
        "P1-4 CatBoost training configs",
        """
        INSERT INTO tb_training_config (config_id, config_name, feature_set_id, algorithm, train_period_months, validation_period_months, hyperparams) VALUES
        ('TRC-TPL-CATBOOST', 'CatBoost 학습', 'FS-TPL-LAG-ROLL', 'catboost', 1, 1, '{"validation_ratio":0.2,"iterations":80,"learning_rate":0.05,"depth":6}'),
        ('TRC-TPL-TWO-STAGE-CATBOOST', '2-Stage CatBoost 학습', 'FS-TPL-TWO-STAGE', 'two_stage_catboost', 1, 1, '{"validation_ratio":0.2,"iterations":80,"learning_rate":0.05,"depth":6}')
        ON CONFLICT DO NOTHING;
        """,
    ),
]


def run_sql(sql: str) -> None:
    if os.environ.get("THERMOOPS_USE_DOCKER", "1") == "1":
        subprocess.run(
            ["docker", "exec", "-i", "thermops-postgres", "psql", "-U", "thermops", "-d", "thermops", "-c", sql],
            check=True,
            capture_output=True,
            text=True,
        )
        return
    try:
        import psycopg2
    except ImportError as exc:
        raise RuntimeError("psycopg2 required when THERMOOPS_USE_DOCKER=0") from exc
    conn = psycopg2.connect(DB_URL)
    try:
        with conn.cursor() as cur:
            cur.execute(sql)
        conn.commit()
    finally:
        conn.close()


def main() -> int:
    print("THERMOps dev migrations")
    try:
        for label, sql in MIGRATIONS:
            print(f"  [apply] {label}")
            run_sql(sql)
        print("PASSED")
        return 0
    except subprocess.CalledProcessError as exc:
        print(f"FAILED: {exc.stderr or exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"FAILED: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
