-- R10-S4 ASOS / Calendar transform config extension

ALTER TABLE tb_api_connector_transform_config ADD COLUMN IF NOT EXISTS station_code_field VARCHAR(100) DEFAULT 'stnId';
ALTER TABLE tb_api_connector_transform_config ADD COLUMN IF NOT EXISTS observed_at_field VARCHAR(100) DEFAULT 'tm';
ALTER TABLE tb_api_connector_transform_config ADD COLUMN IF NOT EXISTS value_field_mappings_json JSONB;
ALTER TABLE tb_api_connector_transform_config ADD COLUMN IF NOT EXISTS special_day_name_field VARCHAR(100) DEFAULT 'dateName';
ALTER TABLE tb_api_connector_transform_config ADD COLUMN IF NOT EXISTS special_day_type_field VARCHAR(100);
ALTER TABLE tb_api_connector_transform_config ADD COLUMN IF NOT EXISTS default_special_day_type VARCHAR(50) DEFAULT 'PUBLIC_HOLIDAY';
ALTER TABLE tb_api_connector_transform_config ADD COLUMN IF NOT EXISTS public_holiday_field VARCHAR(100) DEFAULT 'isHoliday';
ALTER TABLE tb_api_connector_transform_config ADD COLUMN IF NOT EXISTS calendar_mode VARCHAR(50) DEFAULT 'FULL_CALENDAR_WITH_OVERLAY';
ALTER TABLE tb_api_connector_transform_config ADD COLUMN IF NOT EXISTS calendar_year INTEGER;
ALTER TABLE tb_api_connector_transform_config ADD COLUMN IF NOT EXISTS calendar_month INTEGER;
ALTER TABLE tb_api_connector_transform_config ADD COLUMN IF NOT EXISTS hour_generation_yn BOOLEAN DEFAULT FALSE;
ALTER TABLE tb_api_connector_transform_config ADD COLUMN IF NOT EXISTS station_unmapped_policy VARCHAR(50) DEFAULT 'WARN_ONLY';
ALTER TABLE tb_api_connector_transform_config ADD COLUMN IF NOT EXISTS store_raw_json BOOLEAN DEFAULT TRUE;
