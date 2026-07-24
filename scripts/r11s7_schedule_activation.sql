-- R11-S7-8 Visual Pipeline Schedule Activation PoC
-- Idempotent: safe to re-run via apply_dev_migrations.py
-- Activation does NOT call run_load; due enqueue creates PENDING scheduled runs only.

-- 1) Activation table
CREATE TABLE IF NOT EXISTS tb_visual_pipeline_schedule_activation (
    activation_id VARCHAR(40) PRIMARY KEY,
    pipeline_id VARCHAR(50) NOT NULL,
    materialization_result_id VARCHAR(40) NOT NULL,
    compile_result_id VARCHAR(40),
    r10_schedule_id VARCHAR(40) NOT NULL,
    activation_status VARCHAR(30) NOT NULL,
    cron_expression VARCHAR(120),
    timezone VARCHAR(80),
    activated_at TIMESTAMP,
    deactivated_at TIMESTAMP,
    next_due_at TIMESTAMP,
    last_triggered_at TIMESTAMP,
    trigger_count INTEGER NOT NULL DEFAULT 0,
    metadata_json JSONB,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_vp_schedule_activation_pipeline_status
    ON tb_visual_pipeline_schedule_activation(pipeline_id, activation_status);

CREATE INDEX IF NOT EXISTS ix_vp_schedule_activation_status_next_due
    ON tb_visual_pipeline_schedule_activation(activation_status, next_due_at);

CREATE INDEX IF NOT EXISTS ix_vp_schedule_activation_mat_result
    ON tb_visual_pipeline_schedule_activation(materialization_result_id);

CREATE INDEX IF NOT EXISTS ix_vp_schedule_activation_r10_schedule
    ON tb_visual_pipeline_schedule_activation(r10_schedule_id);

-- One ACTIVE activation per pipeline
CREATE UNIQUE INDEX IF NOT EXISTS ux_vp_schedule_activation_pipeline_active
    ON tb_visual_pipeline_schedule_activation(pipeline_id)
    WHERE activation_status = 'ACTIVE';

-- 2) Scheduled run provenance on tb_visual_pipeline_run
ALTER TABLE tb_visual_pipeline_run
    ADD COLUMN IF NOT EXISTS activation_id VARCHAR(40);

ALTER TABLE tb_visual_pipeline_run
    ADD COLUMN IF NOT EXISTS r10_schedule_id VARCHAR(40);

ALTER TABLE tb_visual_pipeline_run
    ADD COLUMN IF NOT EXISTS scheduled_for TIMESTAMP;

ALTER TABLE tb_visual_pipeline_run
    ADD COLUMN IF NOT EXISTS triggered_at TIMESTAMP;

ALTER TABLE tb_visual_pipeline_run
    ADD COLUMN IF NOT EXISTS dedup_key VARCHAR(160);

CREATE INDEX IF NOT EXISTS ix_vp_run_activation_scheduled_for
    ON tb_visual_pipeline_run(activation_id, scheduled_for);

CREATE UNIQUE INDEX IF NOT EXISTS ux_vp_run_dedup_key
    ON tb_visual_pipeline_run(dedup_key)
    WHERE dedup_key IS NOT NULL;
