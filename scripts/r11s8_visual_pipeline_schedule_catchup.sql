-- R11-S8-6 Visual Pipeline Schedule Catch-up provenance columns
-- Idempotent: safe to re-run via apply_dev_migrations.py

ALTER TABLE tb_visual_pipeline_run
    ADD COLUMN IF NOT EXISTS catchup_of_activation_id VARCHAR(40);

ALTER TABLE tb_visual_pipeline_run
    ADD COLUMN IF NOT EXISTS catchup_for_scheduled_at TIMESTAMP;

ALTER TABLE tb_visual_pipeline_run
    ADD COLUMN IF NOT EXISTS catchup_reason VARCHAR(300);

ALTER TABLE tb_visual_pipeline_run
    ADD COLUMN IF NOT EXISTS catchup_requested_by VARCHAR(120);

ALTER TABLE tb_visual_pipeline_run
    ADD COLUMN IF NOT EXISTS catchup_requested_at TIMESTAMP;

CREATE INDEX IF NOT EXISTS ix_vp_run_catchup_activation
    ON tb_visual_pipeline_run (catchup_of_activation_id, catchup_for_scheduled_at);

CREATE INDEX IF NOT EXISTS ix_vp_run_pipeline_catchup
    ON tb_visual_pipeline_run (pipeline_id, catchup_of_activation_id);
