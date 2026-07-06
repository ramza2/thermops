-- R10-S2 External Code / Common Code Mapping

CREATE TABLE IF NOT EXISTS tb_external_code_mapping (
    mapping_id VARCHAR(50) PRIMARY KEY,
    source_system VARCHAR(100) NOT NULL,
    source_operation_id VARCHAR(50),
    external_code_group VARCHAR(100) NOT NULL,
    external_code VARCHAR(200) NOT NULL,
    external_code_name VARCHAR(300),
    external_code_description TEXT,
    target_type VARCHAR(50) NOT NULL,
    target_id VARCHAR(100) NOT NULL,
    target_display_name VARCHAR(300),
    mapping_status VARCHAR(30) NOT NULL DEFAULT 'ACTIVE',
    mapping_method VARCHAR(50) NOT NULL DEFAULT 'MANUAL',
    confidence_score NUMERIC(5, 4),
    priority INTEGER NOT NULL DEFAULT 1,
    valid_from DATE,
    valid_to DATE,
    active_yn BOOLEAN NOT NULL DEFAULT TRUE,
    archived_at TIMESTAMP,
    archived_reason TEXT,
    metadata_json JSONB,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP,
    CHECK (valid_from IS NULL OR valid_to IS NULL OR valid_from <= valid_to)
);

CREATE INDEX IF NOT EXISTS ix_ext_code_mapping_lookup
    ON tb_external_code_mapping(source_system, external_code_group, external_code);
CREATE INDEX IF NOT EXISTS ix_ext_code_mapping_target
    ON tb_external_code_mapping(target_type, target_id);
CREATE INDEX IF NOT EXISTS ix_ext_code_mapping_status
    ON tb_external_code_mapping(mapping_status);
CREATE INDEX IF NOT EXISTS ix_ext_code_mapping_active
    ON tb_external_code_mapping(active_yn, mapping_status);

CREATE TABLE IF NOT EXISTS tb_unmapped_external_code (
    unmapped_id VARCHAR(50) PRIMARY KEY,
    source_system VARCHAR(100) NOT NULL,
    source_operation_id VARCHAR(50),
    external_code_group VARCHAR(100) NOT NULL,
    external_code VARCHAR(200) NOT NULL,
    external_code_name VARCHAR(300),
    first_seen_at TIMESTAMP NOT NULL DEFAULT NOW(),
    last_seen_at TIMESTAMP NOT NULL DEFAULT NOW(),
    seen_count INTEGER NOT NULL DEFAULT 1,
    sample_payload_json JSONB,
    suggested_target_type VARCHAR(50),
    suggested_target_id VARCHAR(100),
    suggested_target_name VARCHAR(300),
    review_status VARCHAR(30) NOT NULL DEFAULT 'NEW',
    ignored_reason TEXT,
    resolved_mapping_id VARCHAR(50) REFERENCES tb_external_code_mapping(mapping_id),
    metadata_json JSONB,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP,
    UNIQUE(source_system, external_code_group, external_code)
);

CREATE INDEX IF NOT EXISTS ix_unmapped_ext_code_lookup
    ON tb_unmapped_external_code(source_system, external_code_group, external_code);
CREATE INDEX IF NOT EXISTS ix_unmapped_ext_code_review
    ON tb_unmapped_external_code(review_status);
CREATE INDEX IF NOT EXISTS ix_unmapped_ext_code_last_seen
    ON tb_unmapped_external_code(last_seen_at DESC);
