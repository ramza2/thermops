-- R10-S1 Prediction Entity / Location / Weather Mapping

CREATE TABLE IF NOT EXISTS tb_prediction_entity (
    entity_id VARCHAR(50) PRIMARY KEY,
    entity_code VARCHAR(100) NOT NULL UNIQUE,
    entity_name VARCHAR(200) NOT NULL,
    entity_type VARCHAR(50) NOT NULL DEFAULT 'SITE',
    business_domain VARCHAR(100),
    description TEXT,
    active_yn BOOLEAN NOT NULL DEFAULT TRUE,
    archived_at TIMESTAMP,
    metadata_json JSONB,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_prediction_entity_code ON tb_prediction_entity(entity_code);
CREATE INDEX IF NOT EXISTS ix_prediction_entity_type ON tb_prediction_entity(entity_type);
CREATE INDEX IF NOT EXISTS ix_prediction_entity_active ON tb_prediction_entity(active_yn);

CREATE TABLE IF NOT EXISTS tb_prediction_entity_location (
    location_id VARCHAR(50) PRIMARY KEY,
    entity_id VARCHAR(50) NOT NULL REFERENCES tb_prediction_entity(entity_id) ON DELETE CASCADE,
    address TEXT,
    latitude NUMERIC(12, 8),
    longitude NUMERIC(12, 8),
    location_source VARCHAR(50) DEFAULT 'MANUAL',
    valid_from DATE,
    valid_to DATE,
    active_yn BOOLEAN NOT NULL DEFAULT TRUE,
    metadata_json JSONB,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_prediction_entity_location_entity
    ON tb_prediction_entity_location(entity_id, active_yn);

CREATE TABLE IF NOT EXISTS tb_weather_forecast_grid (
    forecast_grid_id VARCHAR(50) PRIMARY KEY,
    grid_system VARCHAR(50) NOT NULL DEFAULT 'KMA_DFS',
    nx INTEGER NOT NULL,
    ny INTEGER NOT NULL,
    grid_name VARCHAR(200),
    latitude NUMERIC(12, 8),
    longitude NUMERIC(12, 8),
    active_yn BOOLEAN NOT NULL DEFAULT TRUE,
    metadata_json JSONB,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP,
    UNIQUE(grid_system, nx, ny)
);

CREATE INDEX IF NOT EXISTS ix_weather_forecast_grid_nx_ny
    ON tb_weather_forecast_grid(grid_system, nx, ny);

CREATE TABLE IF NOT EXISTS tb_weather_observation_station (
    station_id VARCHAR(50) PRIMARY KEY,
    station_code VARCHAR(50) NOT NULL UNIQUE,
    station_name VARCHAR(200) NOT NULL,
    station_type VARCHAR(30) NOT NULL DEFAULT 'ASOS',
    latitude NUMERIC(12, 8),
    longitude NUMERIC(12, 8),
    address TEXT,
    active_yn BOOLEAN NOT NULL DEFAULT TRUE,
    metadata_json JSONB,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_weather_obs_station_code ON tb_weather_observation_station(station_code);

CREATE TABLE IF NOT EXISTS tb_prediction_entity_weather_mapping (
    mapping_id VARCHAR(50) PRIMARY KEY,
    entity_id VARCHAR(50) NOT NULL REFERENCES tb_prediction_entity(entity_id) ON DELETE CASCADE,
    forecast_grid_id VARCHAR(50) REFERENCES tb_weather_forecast_grid(forecast_grid_id),
    station_id VARCHAR(50) REFERENCES tb_weather_observation_station(station_id),
    mapping_type VARCHAR(30) NOT NULL DEFAULT 'BOTH',
    mapping_method VARCHAR(50) DEFAULT 'MANUAL',
    distance_km NUMERIC(10, 3),
    priority INTEGER NOT NULL DEFAULT 1,
    valid_from DATE,
    valid_to DATE,
    active_yn BOOLEAN NOT NULL DEFAULT TRUE,
    archived_at TIMESTAMP,
    metadata_json JSONB,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP,
    CHECK (forecast_grid_id IS NOT NULL OR station_id IS NOT NULL)
);

CREATE INDEX IF NOT EXISTS ix_pe_weather_mapping_entity
    ON tb_prediction_entity_weather_mapping(entity_id, active_yn);
CREATE INDEX IF NOT EXISTS ix_pe_weather_mapping_grid
    ON tb_prediction_entity_weather_mapping(forecast_grid_id);
CREATE INDEX IF NOT EXISTS ix_pe_weather_mapping_station
    ON tb_prediction_entity_weather_mapping(station_id);
