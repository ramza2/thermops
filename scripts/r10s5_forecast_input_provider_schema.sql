-- R10-S5 Forecast On-demand Input Provider

CREATE TABLE IF NOT EXISTS tb_forecast_provider_config (
    provider_config_id VARCHAR(50) PRIMARY KEY,
    provider_name VARCHAR(200) NOT NULL,
    provider_type VARCHAR(50) NOT NULL DEFAULT 'KMA_SHORT_FORECAST',
    source_operation_id VARCHAR(50),
    default_num_of_rows INTEGER NOT NULL DEFAULT 1000,
    default_data_type VARCHAR(20) NOT NULL DEFAULT 'JSON',
    base_time_policy VARCHAR(50) NOT NULL DEFAULT 'LATEST_AVAILABLE',
    delay_minutes INTEGER NOT NULL DEFAULT 60,
    active_yn BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP,
    metadata_json JSONB
);

CREATE TABLE IF NOT EXISTS tb_forecast_input_snapshot (
    snapshot_id VARCHAR(50) PRIMARY KEY,
    prediction_job_id VARCHAR(80),
    entity_id VARCHAR(50),
    nx INTEGER NOT NULL,
    ny INTEGER NOT NULL,
    source_system VARCHAR(100) NOT NULL DEFAULT 'KMA_SHORT_FORECAST_API',
    source_operation_id VARCHAR(50),
    request_base_date VARCHAR(8),
    request_base_time VARCHAR(4),
    forecast_base_at TIMESTAMP,
    requested_at TIMESTAMP NOT NULL,
    cache_key VARCHAR(300) NOT NULL,
    request_params_masked JSONB,
    raw_response_snapshot_id VARCHAR(50),
    raw_response_json JSONB,
    normalized_rows_json JSONB,
    row_count INTEGER NOT NULL DEFAULT 0,
    cache_hit_yn BOOLEAN NOT NULL DEFAULT FALSE,
    success_yn BOOLEAN NOT NULL DEFAULT FALSE,
    error_message TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    metadata_json JSONB
);

CREATE TABLE IF NOT EXISTS tb_prediction_weather_input (
    weather_input_id VARCHAR(50) PRIMARY KEY,
    prediction_job_id VARCHAR(80) NOT NULL,
    snapshot_id VARCHAR(50),
    entity_id VARCHAR(50),
    forecast_base_at TIMESTAMP,
    forecast_target_at TIMESTAMP NOT NULL,
    forecast_horizon_hours INTEGER,
    nx INTEGER,
    ny INTEGER,
    temperature NUMERIC(10, 2),
    humidity NUMERIC(10, 2),
    wind_speed NUMERIC(10, 2),
    precipitation NUMERIC(10, 2),
    precipitation_probability NUMERIC(10, 2),
    sky_condition VARCHAR(50),
    precipitation_type VARCHAR(50),
    raw_category_values_json JSONB,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_forecast_input_snapshot_cache_key
    ON tb_forecast_input_snapshot(cache_key);
CREATE INDEX IF NOT EXISTS ix_forecast_input_snapshot_prediction_job
    ON tb_forecast_input_snapshot(prediction_job_id);
CREATE INDEX IF NOT EXISTS ix_forecast_input_snapshot_entity
    ON tb_forecast_input_snapshot(entity_id);
CREATE INDEX IF NOT EXISTS ix_prediction_weather_input_job
    ON tb_prediction_weather_input(prediction_job_id);
CREATE INDEX IF NOT EXISTS ix_prediction_weather_input_entity_target
    ON tb_prediction_weather_input(entity_id, forecast_target_at);
CREATE INDEX IF NOT EXISTS ix_prediction_weather_input_snapshot
    ON tb_prediction_weather_input(snapshot_id);
