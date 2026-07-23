-- R11-S7-6 Visual Pipeline Run Worker claim/lock columns (Option C PoC)
-- Idempotent: safe to re-run via apply_dev_migrations.py

ALTER TABLE tb_visual_pipeline_run
    ADD COLUMN IF NOT EXISTS claimed_at TIMESTAMP;

ALTER TABLE tb_visual_pipeline_run
    ADD COLUMN IF NOT EXISTS claimed_by VARCHAR(120);

ALTER TABLE tb_visual_pipeline_run
    ADD COLUMN IF NOT EXISTS locked_until TIMESTAMP;

ALTER TABLE tb_visual_pipeline_run
    ADD COLUMN IF NOT EXISTS heartbeat_at TIMESTAMP;

ALTER TABLE tb_visual_pipeline_run
    ADD COLUMN IF NOT EXISTS attempt_count INTEGER NOT NULL DEFAULT 0;

CREATE INDEX IF NOT EXISTS ix_vp_run_status_created
    ON tb_visual_pipeline_run(run_status, created_at);

CREATE INDEX IF NOT EXISTS ix_vp_run_status_locked_until
    ON tb_visual_pipeline_run(run_status, locked_until);
