-- Pipeline Definition 실행 이력 연결 (R9)
CREATE TABLE IF NOT EXISTS tb_pipeline_run_link (
    link_id VARCHAR(50) PRIMARY KEY,
    pipeline_id VARCHAR(50) NOT NULL REFERENCES tb_pipeline_definition(pipeline_id),
    template_id VARCHAR(50) NOT NULL REFERENCES tb_pipeline_template(template_id),
    pipeline_run_id VARCHAR(80) NOT NULL,
    airflow_dag_id VARCHAR(200),
    airflow_run_id VARCHAR(250),
    run_source VARCHAR(50) NOT NULL DEFAULT 'PIPELINE_DEFINITION',
    run_status VARCHAR(50) NOT NULL DEFAULT 'REQUESTED',
    runtime_params_snapshot JSONB,
    node_config_snapshot JSONB,
    validation_snapshot JSONB,
    trigger_response_json JSONB,
    error_message TEXT,
    requested_by VARCHAR(100),
    requested_at TIMESTAMP NOT NULL DEFAULT NOW(),
    started_at TIMESTAMP,
    finished_at TIMESTAMP,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_pipeline_run_link_pipeline
    ON tb_pipeline_run_link(pipeline_id, requested_at DESC);

CREATE INDEX IF NOT EXISTS ix_pipeline_run_link_template
    ON tb_pipeline_run_link(template_id, requested_at DESC);

CREATE INDEX IF NOT EXISTS ix_pipeline_run_link_run_id
    ON tb_pipeline_run_link(pipeline_run_id);

CREATE INDEX IF NOT EXISTS ix_pipeline_run_link_airflow
    ON tb_pipeline_run_link(airflow_dag_id, airflow_run_id);

CREATE INDEX IF NOT EXISTS ix_pipeline_run_link_status
    ON tb_pipeline_run_link(run_status, requested_at DESC);
