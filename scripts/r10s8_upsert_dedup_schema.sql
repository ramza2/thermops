-- R10-S8 Upsert / Deduplicate schema

CREATE TABLE IF NOT EXISTS tb_api_connector_write_policy (
    write_policy_id VARCHAR(50) PRIMARY KEY,
    operation_id VARCHAR(50) NOT NULL REFERENCES tb_api_connector_operation(operation_id) ON DELETE CASCADE,
    target_table VARCHAR(100) NOT NULL,
    write_mode VARCHAR(30) NOT NULL DEFAULT 'INSERT_ONLY',
    conflict_key_columns_json JSONB,
    update_columns_json JSONB,
    exclude_update_columns_json JSONB,
    compare_columns_json JSONB,
    null_update_policy VARCHAR(30) NOT NULL DEFAULT 'KEEP_EXISTING',
    duplicate_within_batch_policy VARCHAR(30) NOT NULL DEFAULT 'KEEP_LAST',
    no_conflict_key_policy VARCHAR(30) NOT NULL DEFAULT 'WARN_INSERT_ONLY',
    active_yn BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP,
    metadata_json JSONB
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_api_connector_write_policy_active
    ON tb_api_connector_write_policy(operation_id, target_table)
    WHERE active_yn = TRUE;

CREATE INDEX IF NOT EXISTS ix_api_connector_write_policy_op_target_active
    ON tb_api_connector_write_policy(operation_id, target_table, active_yn);

CREATE TABLE IF NOT EXISTS tb_api_connector_load_dedup_summary (
    summary_id VARCHAR(50) PRIMARY KEY,
    load_run_id VARCHAR(50) REFERENCES tb_api_connector_load_run(load_run_id) ON DELETE SET NULL,
    schedule_run_id VARCHAR(50) REFERENCES tb_data_load_schedule_run(schedule_run_id) ON DELETE SET NULL,
    operation_id VARCHAR(50) NOT NULL REFERENCES tb_api_connector_operation(operation_id) ON DELETE CASCADE,
    target_table VARCHAR(100),
    write_mode VARCHAR(30) NOT NULL DEFAULT 'INSERT_ONLY',
    input_row_count INTEGER NOT NULL DEFAULT 0,
    unique_input_row_count INTEGER NOT NULL DEFAULT 0,
    duplicate_within_batch_count INTEGER NOT NULL DEFAULT 0,
    existing_match_count INTEGER NOT NULL DEFAULT 0,
    inserted_count INTEGER NOT NULL DEFAULT 0,
    updated_count INTEGER NOT NULL DEFAULT 0,
    skipped_duplicate_count INTEGER NOT NULL DEFAULT 0,
    unchanged_count INTEGER NOT NULL DEFAULT 0,
    error_count INTEGER NOT NULL DEFAULT 0,
    conflict_key_columns_json JSONB,
    sample_conflicts_json JSONB,
    warnings_json JSONB,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    metadata_json JSONB
);

CREATE INDEX IF NOT EXISTS ix_api_connector_dedup_summary_load_run
    ON tb_api_connector_load_dedup_summary(load_run_id);

CREATE INDEX IF NOT EXISTS ix_api_connector_dedup_summary_op_created
    ON tb_api_connector_load_dedup_summary(operation_id, created_at DESC);
