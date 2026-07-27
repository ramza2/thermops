-- R11-S8-4 Visual Pipeline Run Retry lineage columns
-- Idempotent: safe to re-run via apply_dev_migrations.py

ALTER TABLE tb_visual_pipeline_run
    ADD COLUMN IF NOT EXISTS retry_of_run_id VARCHAR(40);

ALTER TABLE tb_visual_pipeline_run
    ADD COLUMN IF NOT EXISTS retry_attempt INTEGER NOT NULL DEFAULT 0;

ALTER TABLE tb_visual_pipeline_run
    ADD COLUMN IF NOT EXISTS retry_reason VARCHAR(300);

ALTER TABLE tb_visual_pipeline_run
    ADD COLUMN IF NOT EXISTS retry_mode VARCHAR(40);

CREATE INDEX IF NOT EXISTS ix_vp_run_retry_of
    ON tb_visual_pipeline_run (retry_of_run_id, created_at);

CREATE INDEX IF NOT EXISTS ix_vp_run_pipeline_retry
    ON tb_visual_pipeline_run (pipeline_id, retry_of_run_id);
