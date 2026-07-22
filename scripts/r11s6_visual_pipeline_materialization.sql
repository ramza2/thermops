-- R11-S6-4 Visual Pipeline Materialization Result (Option 2)
-- Idempotent: safe to re-run via apply_dev_migrations.py

CREATE TABLE IF NOT EXISTS tb_visual_pipeline_materialization_result (
    materialization_result_id VARCHAR(50) PRIMARY KEY,
    pipeline_id VARCHAR(50) NOT NULL REFERENCES tb_pipeline_definition(pipeline_id),
    compile_result_id VARCHAR(50) NOT NULL,
    materialization_status VARCHAR(30) NOT NULL,
    graph_version_hash VARCHAR(100),
    materialization_version VARCHAR(30) NOT NULL DEFAULT 'R11-S6-4',
    objects_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    updated_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    skipped_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    issues_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    warnings_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    activation VARCHAR(40) NOT NULL DEFAULT 'NOT_REQUESTED',
    run_created BOOLEAN NOT NULL DEFAULT FALSE,
    error_message TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_vp_materialization_pipeline_created
    ON tb_visual_pipeline_materialization_result(pipeline_id, created_at DESC);

CREATE INDEX IF NOT EXISTS ix_vp_materialization_compile_result
    ON tb_visual_pipeline_materialization_result(compile_result_id);
