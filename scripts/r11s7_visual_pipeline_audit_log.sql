-- R11-S7-13 Visual Pipeline Audit Log
-- Idempotent: safe to re-run via apply_dev_migrations.py
-- No FK: audit is independent of source row lifecycle

CREATE TABLE IF NOT EXISTS tb_visual_pipeline_audit_log (
    audit_id VARCHAR(40) PRIMARY KEY,
    event_type VARCHAR(80) NOT NULL,
    event_source VARCHAR(40) NOT NULL,
    pipeline_id VARCHAR(40),
    visual_run_id VARCHAR(40),
    activation_id VARCHAR(40),
    materialization_result_id VARCHAR(40),
    r10_schedule_id VARCHAR(40),
    actor_type VARCHAR(40),
    actor_id VARCHAR(120),
    action_status VARCHAR(30) NOT NULL,
    request_id VARCHAR(120),
    reason VARCHAR(200),
    before_json JSONB,
    after_json JSONB,
    metadata_json JSONB,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_vp_audit_event_created
    ON tb_visual_pipeline_audit_log (event_type, created_at);

CREATE INDEX IF NOT EXISTS idx_vp_audit_pipeline_created
    ON tb_visual_pipeline_audit_log (pipeline_id, created_at);

CREATE INDEX IF NOT EXISTS idx_vp_audit_run_created
    ON tb_visual_pipeline_audit_log (visual_run_id, created_at);

CREATE INDEX IF NOT EXISTS idx_vp_audit_activation_created
    ON tb_visual_pipeline_audit_log (activation_id, created_at);
