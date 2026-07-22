-- R11-S6-2 Visual Pipeline Compile Result persistence (Option C)
-- Idempotent: safe to re-run via apply_dev_migrations.py

CREATE TABLE IF NOT EXISTS tb_visual_pipeline_compile_result (
    compile_result_id VARCHAR(50) PRIMARY KEY,
    pipeline_id VARCHAR(50) NOT NULL REFERENCES tb_pipeline_definition(pipeline_id),
    compile_status VARCHAR(30) NOT NULL,
    validation_level VARCHAR(20) NOT NULL DEFAULT 'STRICT',
    graph_version_hash VARCHAR(100),
    config_hash VARCHAR(100),
    compile_version VARCHAR(30) NOT NULL DEFAULT 'R11-S6-2',
    compiled_artifact_json JSONB,
    issues_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    error_message TEXT,
    source VARCHAR(40) NOT NULL DEFAULT 'COMPILE_API',
    created_by VARCHAR(100),
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_vp_compile_result_pipeline_created
    ON tb_visual_pipeline_compile_result(pipeline_id, created_at DESC);

CREATE INDEX IF NOT EXISTS ix_vp_compile_result_pipeline_status_created
    ON tb_visual_pipeline_compile_result(pipeline_id, compile_status, created_at DESC);

CREATE INDEX IF NOT EXISTS ix_vp_compile_result_graph_hash
    ON tb_visual_pipeline_compile_result(graph_version_hash);
