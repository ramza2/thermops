CREATE TABLE IF NOT EXISTS tb_pipeline_template (
    template_id VARCHAR(50) PRIMARY KEY,
    template_code VARCHAR(80) NOT NULL UNIQUE,
    template_name VARCHAR(200) NOT NULL,
    description TEXT,
    pipeline_type VARCHAR(80) NOT NULL,
    airflow_dag_id VARCHAR(200),
    template_version VARCHAR(30) NOT NULL DEFAULT '1.0',
    node_schema_json JSONB NOT NULL,
    edge_schema_json JSONB NOT NULL,
    default_config_json JSONB,
    status VARCHAR(30) NOT NULL DEFAULT 'ACTIVE',
    active_yn CHAR(1) NOT NULL DEFAULT 'Y',
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS tb_pipeline_definition (
    pipeline_id VARCHAR(50) PRIMARY KEY,
    template_id VARCHAR(50) NOT NULL REFERENCES tb_pipeline_template(template_id),
    pipeline_name VARCHAR(200) NOT NULL,
    description TEXT,
    pipeline_type VARCHAR(80) NOT NULL,
    airflow_dag_id VARCHAR(200),
    node_config_json JSONB NOT NULL DEFAULT '{}',
    edge_config_json JSONB,
    runtime_params_json JSONB,
    schedule_config_json JSONB,
    validation_result_json JSONB,
    status VARCHAR(30) NOT NULL DEFAULT 'DRAFT',
    last_validated_at TIMESTAMP,
    last_run_id VARCHAR(80),
    active_yn CHAR(1) NOT NULL DEFAULT 'Y',
    created_by VARCHAR(100),
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS tb_pipeline_definition_version (
    version_id VARCHAR(50) PRIMARY KEY,
    pipeline_id VARCHAR(50) NOT NULL REFERENCES tb_pipeline_definition(pipeline_id),
    version_no INTEGER NOT NULL,
    snapshot_json JSONB NOT NULL,
    change_summary TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_pipeline_definition_template
    ON tb_pipeline_definition(template_id)
    WHERE active_yn = 'Y';

CREATE INDEX IF NOT EXISTS ix_pipeline_definition_status
    ON tb_pipeline_definition(status)
    WHERE active_yn = 'Y';

CREATE UNIQUE INDEX IF NOT EXISTS ux_pipeline_definition_version
    ON tb_pipeline_definition_version(pipeline_id, version_no);
