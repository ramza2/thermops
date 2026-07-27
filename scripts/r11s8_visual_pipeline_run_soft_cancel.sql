-- R11-S8-5 Visual Pipeline Run soft-cancel columns
-- Idempotent: safe to re-run via apply_dev_migrations.py

ALTER TABLE tb_visual_pipeline_run
    ADD COLUMN IF NOT EXISTS cancel_requested_at TIMESTAMP;

ALTER TABLE tb_visual_pipeline_run
    ADD COLUMN IF NOT EXISTS cancel_requested_by VARCHAR(120);

ALTER TABLE tb_visual_pipeline_run
    ADD COLUMN IF NOT EXISTS cancel_reason VARCHAR(300);

ALTER TABLE tb_visual_pipeline_run
    ADD COLUMN IF NOT EXISTS cancel_acknowledged_at TIMESTAMP;

CREATE INDEX IF NOT EXISTS ix_vp_run_cancel_requested
    ON tb_visual_pipeline_run (pipeline_id, cancel_requested_at);
