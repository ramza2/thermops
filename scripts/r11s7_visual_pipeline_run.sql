-- R11-S7-1 Visual Pipeline Manual Run mapping (Option C: R10 load_run + VP provenance)
-- Idempotent: safe to re-run via apply_dev_migrations.py

CREATE TABLE IF NOT EXISTS tb_visual_pipeline_run (
    visual_run_id VARCHAR(50) PRIMARY KEY,
    pipeline_id VARCHAR(50) NOT NULL REFERENCES tb_pipeline_definition(pipeline_id),
    compile_result_id VARCHAR(50) NOT NULL,
    materialization_result_id VARCHAR(50) NOT NULL,
    graph_version_hash VARCHAR(100),
    load_run_id VARCHAR(50),
    mode VARCHAR(30) NOT NULL DEFAULT 'MANUAL',
    execution_mode VARCHAR(30) NOT NULL DEFAULT 'SYNC',
    run_status VARCHAR(30) NOT NULL,
    request_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    result_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    issues_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    error_message TEXT,
    started_at TIMESTAMP,
    finished_at TIMESTAMP,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_vp_run_pipeline_created
    ON tb_visual_pipeline_run(pipeline_id, created_at DESC);

CREATE INDEX IF NOT EXISTS ix_vp_run_pipeline_status
    ON tb_visual_pipeline_run(pipeline_id, run_status);
