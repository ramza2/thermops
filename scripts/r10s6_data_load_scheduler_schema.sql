-- R10-S6 Data Load Scheduler

CREATE TABLE IF NOT EXISTS tb_data_load_schedule (
    schedule_id VARCHAR(50) PRIMARY KEY,
    schedule_name VARCHAR(200) NOT NULL,
    schedule_description TEXT,
    operation_id VARCHAR(50) NOT NULL,
    data_source_id VARCHAR(50),
    schedule_type VARCHAR(30) NOT NULL DEFAULT 'MANUAL',
    cron_expression VARCHAR(120),
    timezone VARCHAR(50) NOT NULL DEFAULT 'Asia/Seoul',
    start_at TIMESTAMP,
    end_at TIMESTAMP,
    active_yn BOOLEAN NOT NULL DEFAULT TRUE,
    run_policy VARCHAR(30) NOT NULL DEFAULT 'LOAD_RUN',
    load_window_type VARCHAR(30) NOT NULL DEFAULT 'NONE',
    window_offset_minutes INTEGER,
    runtime_params_template JSONB,
    max_pages_override INTEGER,
    retry_enabled_yn BOOLEAN NOT NULL DEFAULT FALSE,
    max_retry_count INTEGER NOT NULL DEFAULT 0,
    retry_interval_minutes INTEGER NOT NULL DEFAULT 10,
    on_failure_policy VARCHAR(30) NOT NULL DEFAULT 'STOP',
    last_run_at TIMESTAMP,
    last_success_at TIMESTAMP,
    last_failure_at TIMESTAMP,
    next_run_at TIMESTAMP,
    last_run_status VARCHAR(30),
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP,
    metadata_json JSONB
);

CREATE TABLE IF NOT EXISTS tb_data_load_schedule_run (
    schedule_run_id VARCHAR(50) PRIMARY KEY,
    schedule_id VARCHAR(50) NOT NULL,
    operation_id VARCHAR(50) NOT NULL,
    api_load_run_id VARCHAR(50),
    run_source VARCHAR(30) NOT NULL DEFAULT 'SCHEDULED_LOAD',
    scheduled_for TIMESTAMP,
    started_at TIMESTAMP NOT NULL,
    finished_at TIMESTAMP,
    run_status VARCHAR(30) NOT NULL DEFAULT 'RUNNING',
    attempt_no INTEGER NOT NULL DEFAULT 1,
    parent_schedule_run_id VARCHAR(50),
    runtime_params_snapshot JSONB,
    runtime_params_masked JSONB,
    request_summary JSONB,
    result_summary JSONB,
    inserted_count INTEGER NOT NULL DEFAULT 0,
    updated_count INTEGER NOT NULL DEFAULT 0,
    skipped_count INTEGER NOT NULL DEFAULT 0,
    error_count INTEGER NOT NULL DEFAULT 0,
    error_message TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    metadata_json JSONB
);

CREATE TABLE IF NOT EXISTS tb_data_load_schedule_event (
    event_id VARCHAR(50) PRIMARY KEY,
    schedule_id VARCHAR(50) NOT NULL,
    schedule_run_id VARCHAR(50),
    event_type VARCHAR(50) NOT NULL,
    event_message TEXT,
    event_payload_json JSONB,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_data_load_schedule_active_next
    ON tb_data_load_schedule(active_yn, next_run_at);
CREATE INDEX IF NOT EXISTS ix_data_load_schedule_operation
    ON tb_data_load_schedule(operation_id);
CREATE INDEX IF NOT EXISTS ix_data_load_schedule_run_schedule
    ON tb_data_load_schedule_run(schedule_id, started_at DESC);
CREATE INDEX IF NOT EXISTS ix_data_load_schedule_run_status
    ON tb_data_load_schedule_run(run_status);
CREATE INDEX IF NOT EXISTS ix_data_load_schedule_event_schedule
    ON tb_data_load_schedule_event(schedule_id, created_at DESC);
