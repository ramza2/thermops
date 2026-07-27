-- R11-S8-3 Visual Pipeline Run Event — step-level progress (observability only)
-- Idempotent: safe to re-run via apply_dev_migrations.py

CREATE TABLE IF NOT EXISTS tb_visual_pipeline_run_event (
    event_id VARCHAR(50) PRIMARY KEY,
    visual_run_id VARCHAR(50) NOT NULL,
    pipeline_id VARCHAR(50) NOT NULL,
    event_type VARCHAR(80) NOT NULL,
    step_key VARCHAR(50),
    step_name VARCHAR(120),
    progress_percent INTEGER,
    message TEXT,
    metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_vp_run_event_visual_run_created
    ON tb_visual_pipeline_run_event(visual_run_id, created_at ASC);

CREATE INDEX IF NOT EXISTS ix_vp_run_event_pipeline_created
    ON tb_visual_pipeline_run_event(pipeline_id, created_at DESC);
