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


def _load_sql(filename: str) -> str:
    path = os.path.join(os.path.dirname(__file__), filename)
    with open(path, encoding="utf-8") as handle:
        return handle.read()


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
        "R7 standard dataset schema",
        _load_sql("r7_standard_dataset_schema.sql"),
    ),
    (
        "R8 pipeline builder schema",
        _load_sql("r8_pipeline_builder_schema.sql"),
    ),
    (
        "tb_feature_column_role",
        """
        CREATE TABLE IF NOT EXISTS tb_feature_column_role (
            role_id VARCHAR(50) PRIMARY KEY,
            mapping_id VARCHAR(50) REFERENCES tb_data_mapping(mapping_id),
            data_source_id VARCHAR(50) REFERENCES tb_data_source(data_source_id),
            source_table VARCHAR(100),
            target_table VARCHAR(100),
            source_column VARCHAR(100) NOT NULL,
            target_column VARCHAR(100),
            data_type VARCHAR(50),
            column_role VARCHAR(50) NOT NULL,
            inferred_role VARCHAR(50),
            inference_confidence NUMERIC(5,2),
            role_source VARCHAR(20) NOT NULL DEFAULT 'MANUAL',
            description TEXT,
            active_yn CHAR(1) NOT NULL DEFAULT 'Y',
            created_at TIMESTAMP NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMP
        );
        CREATE UNIQUE INDEX IF NOT EXISTS ux_feature_column_role_mapping_source
            ON tb_feature_column_role(mapping_id, source_column)
            WHERE mapping_id IS NOT NULL AND active_yn = 'Y';
        CREATE INDEX IF NOT EXISTS ix_feature_column_role_mapping
            ON tb_feature_column_role(mapping_id)
            WHERE active_yn = 'Y';
        CREATE INDEX IF NOT EXISTS ix_feature_column_role_target_table
            ON tb_feature_column_role(target_table)
            WHERE active_yn = 'Y';
        """,
    ),
    (
        "tb_feature_recipe R5 tables",
        """
        CREATE TABLE IF NOT EXISTS tb_feature_recipe (
            recipe_id VARCHAR(50) PRIMARY KEY,
            feature_name VARCHAR(100),
            display_name VARCHAR(200) NOT NULL,
            description TEXT,
            domain VARCHAR(50),
            task_type VARCHAR(50),
            calc_mode VARCHAR(20) NOT NULL DEFAULT 'TEMPLATE',
            recipe_type VARCHAR(50) NOT NULL,
            mapping_id VARCHAR(50),
            data_source_id VARCHAR(50),
            source_table VARCHAR(100),
            target_table VARCHAR(100),
            source_columns JSONB NOT NULL DEFAULT '[]',
            entity_keys JSONB,
            time_key VARCHAR(100),
            target_column VARCHAR(100),
            params JSONB NOT NULL DEFAULT '{}',
            output_feature_names JSONB,
            output_data_type VARCHAR(50),
            unit VARCHAR(50),
            null_handling VARCHAR(50),
            leakage_policy VARCHAR(50),
            validation_summary JSONB,
            preview_summary JSONB,
            lineage_preview JSONB,
            quality_preview JSONB,
            status VARCHAR(30) NOT NULL DEFAULT 'DRAFT',
            version INTEGER NOT NULL DEFAULT 1,
            owner VARCHAR(100),
            active_yn CHAR(1) NOT NULL DEFAULT 'Y',
            published_at TIMESTAMP,
            created_at TIMESTAMP NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMP NOT NULL DEFAULT NOW()
        );
        CREATE TABLE IF NOT EXISTS tb_feature_recipe_version (
            version_id VARCHAR(50) PRIMARY KEY,
            recipe_id VARCHAR(50) NOT NULL REFERENCES tb_feature_recipe(recipe_id),
            version_no INTEGER NOT NULL,
            recipe_snapshot JSONB NOT NULL,
            change_reason TEXT,
            created_at TIMESTAMP NOT NULL DEFAULT NOW()
        );
        CREATE UNIQUE INDEX IF NOT EXISTS ux_feature_recipe_published_feature_name
            ON tb_feature_recipe(feature_name)
            WHERE active_yn = 'Y' AND status = 'PUBLISHED' AND feature_name IS NOT NULL;
        CREATE INDEX IF NOT EXISTS ix_feature_recipe_status ON tb_feature_recipe(status) WHERE active_yn = 'Y';
        CREATE INDEX IF NOT EXISTS ix_feature_recipe_mapping ON tb_feature_recipe(mapping_id) WHERE active_yn = 'Y';
        CREATE INDEX IF NOT EXISTS ix_feature_recipe_type ON tb_feature_recipe(recipe_type) WHERE active_yn = 'Y';
        """,
    ),
    (
        "R9 pipeline run link schema",
        _load_sql("r9_pipeline_run_link_schema.sql"),
    ),
]


def _postgres_container() -> str:
    project = os.environ.get("COMPOSE_PROJECT_NAME", "thermops")
    return os.environ.get("THERMOOPS_POSTGRES_CONTAINER", f"{project}-postgres")


def run_sql(sql: str) -> None:
    if os.environ.get("THERMOOPS_USE_DOCKER", "1") == "1":
        container = _postgres_container()
        subprocess.run(
            ["docker", "exec", "-i", container, "psql", "-U", "thermops", "-d", "thermops", "-c", sql],
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
