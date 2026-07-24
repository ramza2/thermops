-- R11-S7-9 Schedule/run hardening columns
-- Idempotent: safe to re-run via apply_dev_migrations.py

ALTER TABLE tb_visual_pipeline_schedule_activation
    ADD COLUMN IF NOT EXISTS paused_at TIMESTAMP;

ALTER TABLE tb_visual_pipeline_schedule_activation
    ADD COLUMN IF NOT EXISTS resumed_at TIMESTAMP;

ALTER TABLE tb_visual_pipeline_schedule_activation
    ADD COLUMN IF NOT EXISTS last_due_at TIMESTAMP;

ALTER TABLE tb_visual_pipeline_schedule_activation
    ADD COLUMN IF NOT EXISTS last_skip_at TIMESTAMP;

ALTER TABLE tb_visual_pipeline_schedule_activation
    ADD COLUMN IF NOT EXISTS last_skip_reason VARCHAR(80);

ALTER TABLE tb_visual_pipeline_schedule_activation
    ADD COLUMN IF NOT EXISTS missed_count INTEGER NOT NULL DEFAULT 0;
