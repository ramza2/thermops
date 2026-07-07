-- R10-S3 Wide Hour to Long transform config

CREATE TABLE IF NOT EXISTS tb_api_connector_transform_config (
    transform_config_id VARCHAR(50) PRIMARY KEY,
    operation_id VARCHAR(50) NOT NULL UNIQUE REFERENCES tb_api_connector_operation(operation_id) ON DELETE CASCADE,
    transform_type VARCHAR(50) NOT NULL DEFAULT 'NONE',
    transform_name VARCHAR(200),
    source_system VARCHAR(100) NOT NULL DEFAULT 'HEAT_DEMAND_API',
    external_code_group VARCHAR(100) NOT NULL DEFAULT 'NODE',
    external_code_field VARCHAR(100) NOT NULL DEFAULT 'ND_ID',
    external_name_field VARCHAR(100) NOT NULL DEFAULT 'ND_KORN_NM',
    date_field VARCHAR(100) NOT NULL DEFAULT 'BAS_YMD',
    date_format VARCHAR(50) NOT NULL DEFAULT 'YYYYMMDD',
    hour_column_prefix VARCHAR(100) NOT NULL DEFAULT 'HTDND_AMNT_',
    hour_column_suffix VARCHAR(50) NOT NULL DEFAULT 'HR',
    hour_start INTEGER NOT NULL DEFAULT 1,
    hour_end INTEGER NOT NULL DEFAULT 24,
    value_output_field VARCHAR(100) NOT NULL DEFAULT 'heat_demand',
    measured_at_output_field VARCHAR(100) NOT NULL DEFAULT 'measured_at',
    entity_id_output_field VARCHAR(100) NOT NULL DEFAULT 'entity_id',
    entity_code_output_field VARCHAR(100) NOT NULL DEFAULT 'site_id',
    external_code_output_field VARCHAR(100) NOT NULL DEFAULT 'external_node_id',
    external_name_output_field VARCHAR(100) NOT NULL DEFAULT 'external_node_name',
    timestamp_policy VARCHAR(50) NOT NULL DEFAULT 'HOUR_LABEL_AS_END',
    hour_24_policy VARCHAR(50) NOT NULL DEFAULT 'NEXT_DAY_00',
    unmapped_policy VARCHAR(50) NOT NULL DEFAULT 'FAIL_LOAD',
    null_value_policy VARCHAR(50) NOT NULL DEFAULT 'SKIP_NULL',
    numeric_parse_policy VARCHAR(50) NOT NULL DEFAULT 'ALLOW_COMMA',
    active_yn BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP,
    metadata_json JSONB
);

CREATE INDEX IF NOT EXISTS ix_api_connector_transform_op
    ON tb_api_connector_transform_config(operation_id)
    WHERE active_yn = TRUE;
