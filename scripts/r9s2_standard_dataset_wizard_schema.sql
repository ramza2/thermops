-- R9-S2-1 Standard Dataset Physical Table Wizard schema extensions

ALTER TABLE tb_standard_dataset_type
    ADD COLUMN IF NOT EXISTS physical_table_schema VARCHAR(63) NOT NULL DEFAULT 'public';

ALTER TABLE tb_standard_dataset_type
    ADD COLUMN IF NOT EXISTS managed_table_yn CHAR(1) NOT NULL DEFAULT 'N';

ALTER TABLE tb_standard_dataset_type
    ADD COLUMN IF NOT EXISTS table_create_status VARCHAR(30) NOT NULL DEFAULT 'NOT_CREATED';

ALTER TABLE tb_standard_dataset_type
    ADD COLUMN IF NOT EXISTS table_create_sql_preview TEXT;

ALTER TABLE tb_standard_dataset_type
    ADD COLUMN IF NOT EXISTS table_create_error TEXT;

ALTER TABLE tb_standard_dataset_type
    ADD COLUMN IF NOT EXISTS physical_table_created_at TIMESTAMP;

ALTER TABLE tb_standard_dataset_type
    ADD COLUMN IF NOT EXISTS physical_table_created_by VARCHAR(100);

ALTER TABLE tb_standard_dataset_type
    ADD COLUMN IF NOT EXISTS archived_at TIMESTAMP;

ALTER TABLE tb_standard_dataset_type
    ADD COLUMN IF NOT EXISTS archive_reason TEXT;

ALTER TABLE tb_standard_dataset_column
    ADD COLUMN IF NOT EXISTS data_length INTEGER;

ALTER TABLE tb_standard_dataset_column
    ADD COLUMN IF NOT EXISTS numeric_precision INTEGER;

ALTER TABLE tb_standard_dataset_column
    ADD COLUMN IF NOT EXISTS numeric_scale INTEGER;

ALTER TABLE tb_standard_dataset_column
    ADD COLUMN IF NOT EXISTS unique_yn CHAR(1) NOT NULL DEFAULT 'N';

CREATE TABLE IF NOT EXISTS tb_standard_dataset_table_create_log (
    log_id VARCHAR(50) PRIMARY KEY,
    dataset_type_id VARCHAR(50) NOT NULL REFERENCES tb_standard_dataset_type(dataset_type_id),
    action_type VARCHAR(30) NOT NULL,
    status VARCHAR(30) NOT NULL,
    sql_preview TEXT,
    error_message TEXT,
    created_by VARCHAR(100),
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_std_dataset_table_create_log_dataset
    ON tb_standard_dataset_table_create_log(dataset_type_id, created_at DESC);
