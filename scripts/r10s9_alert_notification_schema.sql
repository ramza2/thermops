-- R10-S9 Alert / Notification schema

CREATE TABLE IF NOT EXISTS tb_notification_channel (
    channel_id VARCHAR(50) PRIMARY KEY,
    channel_name VARCHAR(200) NOT NULL,
    channel_type VARCHAR(50) NOT NULL,
    enabled_yn BOOLEAN NOT NULL DEFAULT TRUE,
    config_json JSONB,
    secret_config_encrypted TEXT,
    mask_policy_json JSONB,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP,
    metadata_json JSONB
);

CREATE TABLE IF NOT EXISTS tb_notification_recipient (
    recipient_id VARCHAR(50) PRIMARY KEY,
    recipient_name VARCHAR(200) NOT NULL,
    recipient_type VARCHAR(50) NOT NULL,
    address_masked VARCHAR(300),
    address_encrypted TEXT,
    enabled_yn BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP,
    metadata_json JSONB
);

CREATE TABLE IF NOT EXISTS tb_alert_rule (
    alert_rule_id VARCHAR(50) PRIMARY KEY,
    rule_name VARCHAR(200) NOT NULL,
    rule_description TEXT,
    enabled_yn BOOLEAN NOT NULL DEFAULT TRUE,
    event_source VARCHAR(80) NOT NULL,
    event_type VARCHAR(80) NOT NULL,
    min_severity VARCHAR(30) NOT NULL DEFAULT 'WARNING',
    condition_json JSONB,
    dedup_window_minutes INTEGER NOT NULL DEFAULT 30,
    suppress_yn BOOLEAN NOT NULL DEFAULT FALSE,
    create_incident_yn BOOLEAN NOT NULL DEFAULT TRUE,
    channel_ids_json JSONB,
    recipient_ids_json JSONB,
    message_template TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP,
    metadata_json JSONB
);

CREATE INDEX IF NOT EXISTS ix_alert_rule_source_type_enabled
    ON tb_alert_rule(event_source, event_type, enabled_yn);

CREATE TABLE IF NOT EXISTS tb_notification_event (
    event_id VARCHAR(50) PRIMARY KEY,
    event_source VARCHAR(80) NOT NULL,
    event_type VARCHAR(80) NOT NULL,
    severity VARCHAR(30) NOT NULL,
    title VARCHAR(300) NOT NULL,
    message TEXT,
    resource_type VARCHAR(100),
    resource_id VARCHAR(100),
    correlation_id VARCHAR(100),
    dedup_key VARCHAR(300),
    event_payload_json JSONB,
    masked_payload_json JSONB,
    occurred_at TIMESTAMP NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    metadata_json JSONB
);

CREATE INDEX IF NOT EXISTS ix_notification_event_source_type_occurred
    ON tb_notification_event(event_source, event_type, occurred_at DESC);

CREATE INDEX IF NOT EXISTS ix_notification_event_dedup_occurred
    ON tb_notification_event(dedup_key, occurred_at DESC);

CREATE TABLE IF NOT EXISTS tb_incident (
    incident_id VARCHAR(50) PRIMARY KEY,
    event_id VARCHAR(50) REFERENCES tb_notification_event(event_id) ON DELETE SET NULL,
    alert_rule_id VARCHAR(50) REFERENCES tb_alert_rule(alert_rule_id) ON DELETE SET NULL,
    severity VARCHAR(30) NOT NULL,
    status VARCHAR(30) NOT NULL DEFAULT 'OPEN',
    title VARCHAR(300) NOT NULL,
    summary TEXT,
    resource_type VARCHAR(100),
    resource_id VARCHAR(100),
    dedup_key VARCHAR(300),
    first_occurred_at TIMESTAMP NOT NULL,
    last_occurred_at TIMESTAMP NOT NULL,
    occurrence_count INTEGER NOT NULL DEFAULT 1,
    acknowledged_at TIMESTAMP,
    acknowledged_by VARCHAR(100),
    resolved_at TIMESTAMP,
    resolved_by VARCHAR(100),
    resolution_note TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP,
    metadata_json JSONB
);

CREATE INDEX IF NOT EXISTS ix_incident_status_severity_last
    ON tb_incident(status, severity, last_occurred_at DESC);

CREATE INDEX IF NOT EXISTS ix_incident_dedup_status
    ON tb_incident(dedup_key, status);

CREATE TABLE IF NOT EXISTS tb_notification_delivery (
    delivery_id VARCHAR(50) PRIMARY KEY,
    event_id VARCHAR(50) NOT NULL REFERENCES tb_notification_event(event_id) ON DELETE CASCADE,
    incident_id VARCHAR(50) REFERENCES tb_incident(incident_id) ON DELETE SET NULL,
    alert_rule_id VARCHAR(50) REFERENCES tb_alert_rule(alert_rule_id) ON DELETE SET NULL,
    channel_id VARCHAR(50) REFERENCES tb_notification_channel(channel_id) ON DELETE SET NULL,
    recipient_id VARCHAR(50) REFERENCES tb_notification_recipient(recipient_id) ON DELETE SET NULL,
    delivery_status VARCHAR(30) NOT NULL,
    severity VARCHAR(30) NOT NULL,
    title VARCHAR(300) NOT NULL,
    message TEXT,
    destination_masked VARCHAR(300),
    request_payload_masked JSONB,
    response_payload_masked JSONB,
    error_message TEXT,
    sent_at TIMESTAMP,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    metadata_json JSONB
);

CREATE INDEX IF NOT EXISTS ix_notification_delivery_event
    ON tb_notification_delivery(event_id);

CREATE INDEX IF NOT EXISTS ix_notification_delivery_status_created
    ON tb_notification_delivery(delivery_status, created_at DESC);
