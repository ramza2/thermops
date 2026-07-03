-- R10 Generic REST API Connector Builder

CREATE TABLE IF NOT EXISTS tb_api_connector_operation (
    operation_id VARCHAR(50) PRIMARY KEY,
    data_source_id VARCHAR(50) NOT NULL REFERENCES tb_data_source(data_source_id),
    operation_name VARCHAR(200) NOT NULL,
    operation_description TEXT,
    http_method VARCHAR(10) NOT NULL DEFAULT 'GET',
    endpoint_path TEXT NOT NULL,
    full_url_preview TEXT,
    request_content_type VARCHAR(50) NOT NULL DEFAULT 'QUERY',
    response_format VARCHAR(20) NOT NULL DEFAULT 'JSON',
    response_item_path TEXT,
    result_array_mode VARCHAR(30) NOT NULL DEFAULT 'AUTO',
    target_table VARCHAR(100),
    standard_dataset_id VARCHAR(50),
    active_yn BOOLEAN NOT NULL DEFAULT TRUE,
    archived_at TIMESTAMP,
    metadata_json JSONB,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_api_connector_op_source
    ON tb_api_connector_operation(data_source_id, active_yn);

CREATE TABLE IF NOT EXISTS tb_api_connector_param (
    param_id VARCHAR(50) PRIMARY KEY,
    operation_id VARCHAR(50) NOT NULL REFERENCES tb_api_connector_operation(operation_id) ON DELETE CASCADE,
    param_name VARCHAR(100) NOT NULL,
    display_name VARCHAR(200),
    param_location VARCHAR(20) NOT NULL DEFAULT 'QUERY',
    param_type VARCHAR(30) NOT NULL DEFAULT 'STRING',
    required_yn BOOLEAN NOT NULL DEFAULT FALSE,
    default_value TEXT,
    example_value TEXT,
    allowed_values_json JSONB,
    value_source VARCHAR(30) NOT NULL DEFAULT 'USER_INPUT',
    secret_key_ref VARCHAR(100),
    encode_yn BOOLEAN NOT NULL DEFAULT TRUE,
    sort_order INTEGER NOT NULL DEFAULT 0,
    active_yn BOOLEAN NOT NULL DEFAULT TRUE,
    metadata_json JSONB
);

CREATE INDEX IF NOT EXISTS ix_api_connector_param_op
    ON tb_api_connector_param(operation_id, sort_order);

CREATE TABLE IF NOT EXISTS tb_api_connector_credential (
    credential_id VARCHAR(50) PRIMARY KEY,
    data_source_id VARCHAR(50) NOT NULL REFERENCES tb_data_source(data_source_id) ON DELETE CASCADE,
    credential_name VARCHAR(200) NOT NULL DEFAULT 'default',
    credential_type VARCHAR(30) NOT NULL DEFAULT 'API_KEY',
    key_location VARCHAR(20) NOT NULL DEFAULT 'QUERY',
    key_name VARCHAR(100) NOT NULL DEFAULT 'serviceKey',
    secret_value_encrypted TEXT,
    secret_value_masked VARCHAR(200),
    encoding_policy VARCHAR(30) NOT NULL DEFAULT 'STORE_DECODED_ENCODE_ON_CALL',
    active_yn BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_api_connector_credential_source
    ON tb_api_connector_credential(data_source_id)
    WHERE active_yn = TRUE;

CREATE TABLE IF NOT EXISTS tb_api_connector_pagination (
    pagination_id VARCHAR(50) PRIMARY KEY,
    operation_id VARCHAR(50) NOT NULL UNIQUE REFERENCES tb_api_connector_operation(operation_id) ON DELETE CASCADE,
    pagination_type VARCHAR(30) NOT NULL DEFAULT 'NONE',
    page_param_name VARCHAR(100),
    size_param_name VARCHAR(100),
    page_start INTEGER NOT NULL DEFAULT 1,
    page_size INTEGER NOT NULL DEFAULT 100,
    max_pages INTEGER NOT NULL DEFAULT 1,
    total_count_path TEXT,
    next_link_path TEXT,
    stop_condition VARCHAR(50) NOT NULL DEFAULT 'EMPTY_ITEMS',
    active_yn BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS tb_api_connector_call_log (
    call_log_id VARCHAR(50) PRIMARY KEY,
    operation_id VARCHAR(50) NOT NULL REFERENCES tb_api_connector_operation(operation_id),
    data_source_id VARCHAR(50) NOT NULL REFERENCES tb_data_source(data_source_id),
    called_at TIMESTAMP NOT NULL DEFAULT NOW(),
    called_by VARCHAR(100),
    request_url_masked TEXT,
    request_params_masked JSONB,
    http_status INTEGER,
    success_yn BOOLEAN NOT NULL DEFAULT FALSE,
    response_format VARCHAR(20),
    response_item_count INTEGER NOT NULL DEFAULT 0,
    duration_ms INTEGER,
    error_message TEXT,
    raw_response_snapshot_id VARCHAR(50),
    metadata_json JSONB
);

CREATE INDEX IF NOT EXISTS ix_api_connector_call_log_op
    ON tb_api_connector_call_log(operation_id, called_at DESC);

CREATE TABLE IF NOT EXISTS tb_api_connector_response_snapshot (
    snapshot_id VARCHAR(50) PRIMARY KEY,
    operation_id VARCHAR(50) NOT NULL REFERENCES tb_api_connector_operation(operation_id),
    call_log_id VARCHAR(50) REFERENCES tb_api_connector_call_log(call_log_id),
    captured_at TIMESTAMP NOT NULL DEFAULT NOW(),
    response_format VARCHAR(20) NOT NULL DEFAULT 'JSON',
    raw_response_text TEXT,
    normalized_items_json JSONB,
    item_count INTEGER NOT NULL DEFAULT 0,
    sample_only_yn BOOLEAN NOT NULL DEFAULT TRUE,
    metadata_json JSONB
);

CREATE INDEX IF NOT EXISTS ix_api_connector_snapshot_op
    ON tb_api_connector_response_snapshot(operation_id, captured_at DESC);

CREATE TABLE IF NOT EXISTS tb_api_connector_load_run (
    load_run_id VARCHAR(50) PRIMARY KEY,
    operation_id VARCHAR(50) NOT NULL REFERENCES tb_api_connector_operation(operation_id),
    data_source_id VARCHAR(50) NOT NULL REFERENCES tb_data_source(data_source_id),
    target_table VARCHAR(100),
    standard_dataset_id VARCHAR(50),
    started_at TIMESTAMP NOT NULL DEFAULT NOW(),
    finished_at TIMESTAMP,
    run_status VARCHAR(30) NOT NULL DEFAULT 'PENDING',
    request_params_snapshot JSONB,
    request_params_masked JSONB,
    inserted_count INTEGER NOT NULL DEFAULT 0,
    updated_count INTEGER NOT NULL DEFAULT 0,
    skipped_count INTEGER NOT NULL DEFAULT 0,
    error_count INTEGER NOT NULL DEFAULT 0,
    raw_snapshot_id VARCHAR(50),
    result_summary JSONB,
    error_message TEXT
);

CREATE INDEX IF NOT EXISTS ix_api_connector_load_run_op
    ON tb_api_connector_load_run(operation_id, started_at DESC);
