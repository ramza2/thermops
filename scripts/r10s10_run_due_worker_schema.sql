-- R10-S10 Run Due Worker schema

CREATE TABLE IF NOT EXISTS tb_run_due_worker_instance (
    worker_instance_id VARCHAR(100) PRIMARY KEY,
    worker_name VARCHAR(200) NOT NULL,
    worker_mode VARCHAR(30) NOT NULL,
    host_name VARCHAR(200),
    process_id INTEGER,
    enabled_yn BOOLEAN NOT NULL DEFAULT TRUE,
    status VARCHAR(30) NOT NULL DEFAULT 'STARTING',
    poll_interval_seconds INTEGER NOT NULL DEFAULT 60,
    last_heartbeat_at TIMESTAMP,
    last_run_started_at TIMESTAMP,
    last_run_finished_at TIMESTAMP,
    last_run_status VARCHAR(30),
    consecutive_failure_count INTEGER NOT NULL DEFAULT 0,
    total_run_count INTEGER NOT NULL DEFAULT 0,
    total_success_count INTEGER NOT NULL DEFAULT 0,
    total_failure_count INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP,
    metadata_json JSONB
);

CREATE TABLE IF NOT EXISTS tb_run_due_worker_run (
    worker_run_id VARCHAR(50) PRIMARY KEY,
    worker_instance_id VARCHAR(100),
    worker_name VARCHAR(200),
    run_mode VARCHAR(30) NOT NULL,
    started_at TIMESTAMP NOT NULL,
    finished_at TIMESTAMP,
    run_status VARCHAR(30) NOT NULL DEFAULT 'RUNNING',
    due_schedule_count INTEGER NOT NULL DEFAULT 0,
    executed_schedule_count INTEGER NOT NULL DEFAULT 0,
    success_schedule_count INTEGER NOT NULL DEFAULT 0,
    failed_schedule_count INTEGER NOT NULL DEFAULT 0,
    skipped_schedule_count INTEGER NOT NULL DEFAULT 0,
    run_due_result_json JSONB,
    error_message TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    metadata_json JSONB
);

CREATE TABLE IF NOT EXISTS tb_run_due_worker_lock (
    lock_key VARCHAR(100) PRIMARY KEY,
    owner_instance_id VARCHAR(100) NOT NULL,
    acquired_at TIMESTAMP NOT NULL,
    expires_at TIMESTAMP NOT NULL,
    heartbeat_at TIMESTAMP NOT NULL,
    metadata_json JSONB
);

CREATE INDEX IF NOT EXISTS ix_run_due_worker_instance_status_hb
    ON tb_run_due_worker_instance(status, last_heartbeat_at);

CREATE INDEX IF NOT EXISTS ix_run_due_worker_run_instance_started
    ON tb_run_due_worker_run(worker_instance_id, started_at DESC);

CREATE INDEX IF NOT EXISTS ix_run_due_worker_run_status_started
    ON tb_run_due_worker_run(run_status, started_at DESC);

CREATE INDEX IF NOT EXISTS ix_run_due_worker_lock_expires
    ON tb_run_due_worker_lock(expires_at);
