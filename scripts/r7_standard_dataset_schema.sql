CREATE TABLE IF NOT EXISTS tb_standard_dataset_type (
    dataset_type_id VARCHAR(50) PRIMARY KEY,
    dataset_type_code VARCHAR(80) NOT NULL UNIQUE,
    dataset_type_name VARCHAR(200) NOT NULL,
    description TEXT,
    domain VARCHAR(80),
    category VARCHAR(80),
    target_table VARCHAR(120) NOT NULL,
    physical_table_yn CHAR(1) NOT NULL DEFAULT 'Y',
    physical_table_exists_yn CHAR(1) NOT NULL DEFAULT 'Y',
    build_supported_yn CHAR(1) NOT NULL DEFAULT 'N',
    recipe_supported_yn CHAR(1) NOT NULL DEFAULT 'N',
    mapping_supported_yn CHAR(1) NOT NULL DEFAULT 'Y',
    status VARCHAR(30) NOT NULL DEFAULT 'ACTIVE',
    owner VARCHAR(100),
    active_yn CHAR(1) NOT NULL DEFAULT 'Y',
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS tb_standard_dataset_column (
    column_id VARCHAR(50) PRIMARY KEY,
    dataset_type_id VARCHAR(50) NOT NULL REFERENCES tb_standard_dataset_type(dataset_type_id),
    column_name VARCHAR(120) NOT NULL,
    display_name VARCHAR(200),
    data_type VARCHAR(80) NOT NULL,
    nullable_yn CHAR(1) NOT NULL DEFAULT 'Y',
    required_yn CHAR(1) NOT NULL DEFAULT 'N',
    primary_key_yn CHAR(1) NOT NULL DEFAULT 'N',
    default_column_role VARCHAR(50),
    role_required_yn CHAR(1) NOT NULL DEFAULT 'N',
    description TEXT,
    example_value VARCHAR(500),
    sort_order INTEGER NOT NULL DEFAULT 0,
    active_yn CHAR(1) NOT NULL DEFAULT 'Y',
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_standard_dataset_column_active
    ON tb_standard_dataset_column(dataset_type_id, column_name)
    WHERE active_yn = 'Y';

CREATE INDEX IF NOT EXISTS ix_standard_dataset_type_target_table
    ON tb_standard_dataset_type(target_table)
    WHERE active_yn = 'Y';
