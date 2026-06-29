-- THERMOps PostgreSQL Schema v0.1
-- Reference: docs/md/THERMOps_DB_설계서.md

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- 기준정보
CREATE TABLE IF NOT EXISTS tb_site (
    site_id VARCHAR(50) PRIMARY KEY,
    site_name VARCHAR(100) NOT NULL,
    site_type VARCHAR(20) NOT NULL,
    parent_site_id VARCHAR(50),
    active_yn CHAR(1) NOT NULL DEFAULT 'Y',
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS tb_weather_area (
    weather_area_id VARCHAR(50) PRIMARY KEY,
    area_name VARCHAR(100) NOT NULL,
    latitude NUMERIC(10,6),
    longitude NUMERIC(10,6),
    provider VARCHAR(50),
    active_yn CHAR(1) NOT NULL DEFAULT 'Y',
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS tb_site_weather_mapping (
    mapping_id BIGSERIAL PRIMARY KEY,
    site_id VARCHAR(50) NOT NULL REFERENCES tb_site(site_id),
    weather_area_id VARCHAR(50) NOT NULL REFERENCES tb_weather_area(weather_area_id),
    priority_no INTEGER NOT NULL DEFAULT 1,
    valid_from DATE,
    valid_to DATE,
    active_yn CHAR(1) NOT NULL DEFAULT 'Y'
);

CREATE TABLE IF NOT EXISTS tb_common_code (
    code_group VARCHAR(50) NOT NULL,
    code VARCHAR(50) NOT NULL,
    code_name VARCHAR(100) NOT NULL,
    sort_order INTEGER,
    active_yn CHAR(1) NOT NULL DEFAULT 'Y',
    description VARCHAR(500),
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    PRIMARY KEY (code_group, code)
);

-- 연계/적재
CREATE TABLE IF NOT EXISTS tb_data_source (
    data_source_id VARCHAR(50) PRIMARY KEY,
    source_name VARCHAR(100) NOT NULL,
    source_type VARCHAR(20) NOT NULL,
    source_category VARCHAR(30) NOT NULL,
    connection_ref VARCHAR(200),
    connection_info JSONB,
    load_cycle VARCHAR(20),
    active_yn CHAR(1) NOT NULL DEFAULT 'Y',
    last_loaded_at TIMESTAMP,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS tb_data_mapping (
    mapping_id VARCHAR(50) PRIMARY KEY,
    source_id VARCHAR(50) NOT NULL REFERENCES tb_data_source(data_source_id),
    mapping_name VARCHAR(100) NOT NULL,
    target_table VARCHAR(100) NOT NULL,
    columns JSONB NOT NULL DEFAULT '[]',
    active_yn CHAR(1) NOT NULL DEFAULT 'Y',
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS tb_data_quality_run (
    run_id VARCHAR(80) PRIMARY KEY,
    source_id VARCHAR(50),
    check_type VARCHAR(50) NOT NULL,
    run_status VARCHAR(20) NOT NULL,
    result_summary JSONB,
    started_at TIMESTAMP NOT NULL DEFAULT NOW(),
    finished_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS tb_heat_demand_actual (
    actual_id BIGSERIAL PRIMARY KEY,
    site_id VARCHAR(50) NOT NULL REFERENCES tb_site(site_id),
    measured_at TIMESTAMP NOT NULL,
    heat_demand NUMERIC(18,6) NOT NULL,
    supply_temp NUMERIC(10,3),
    return_temp NUMERIC(10,3),
    flow_rate NUMERIC(18,6),
    quality_flag VARCHAR(20),
    source_system VARCHAR(100),
    loaded_at TIMESTAMP NOT NULL DEFAULT NOW(),
    CONSTRAINT uk_heat_actual UNIQUE(site_id, measured_at)
);

CREATE INDEX IF NOT EXISTS ix_heat_actual_site_time ON tb_heat_demand_actual(site_id, measured_at DESC);

CREATE TABLE IF NOT EXISTS tb_weather_observation (
    weather_id BIGSERIAL PRIMARY KEY,
    weather_area_id VARCHAR(50) NOT NULL REFERENCES tb_weather_area(weather_area_id),
    measured_at TIMESTAMP NOT NULL,
    data_type VARCHAR(20) NOT NULL,
    temperature NUMERIC(10,3),
    humidity NUMERIC(10,3),
    wind_speed NUMERIC(10,3),
    rainfall NUMERIC(10,3),
    apparent_temp NUMERIC(10,3),
    loaded_at TIMESTAMP NOT NULL DEFAULT NOW(),
    CONSTRAINT uk_weather_obs UNIQUE(weather_area_id, measured_at, data_type)
);

CREATE INDEX IF NOT EXISTS ix_weather_area_time ON tb_weather_observation(weather_area_id, measured_at DESC);

CREATE TABLE IF NOT EXISTS tb_calendar (
    calendar_date DATE PRIMARY KEY,
    day_of_week INTEGER NOT NULL,
    is_weekend CHAR(1) NOT NULL,
    is_holiday CHAR(1) NOT NULL,
    holiday_name VARCHAR(100),
    season VARCHAR(20),
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Feature/학습
CREATE TABLE IF NOT EXISTS tb_feature (
    feature_id VARCHAR(50) PRIMARY KEY,
    feature_name VARCHAR(100) NOT NULL,
    feature_group VARCHAR(50),
    feature_type VARCHAR(20) NOT NULL,
    calc_expression VARCHAR(500),
    status VARCHAR(20) NOT NULL DEFAULT 'ACTIVE',
    description VARCHAR(500),
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS tb_feature_set (
    feature_set_id VARCHAR(50) PRIMARY KEY,
    feature_set_name VARCHAR(100) NOT NULL,
    target_domain VARCHAR(30) NOT NULL,
    features JSONB NOT NULL DEFAULT '[]',
    apply_site_scope VARCHAR(20) DEFAULT 'ALL',
    description VARCHAR(500),
    active_yn CHAR(1) NOT NULL DEFAULT 'Y',
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS tb_dataset_version (
    dataset_version_id VARCHAR(80) PRIMARY KEY,
    dataset_type VARCHAR(30) NOT NULL,
    base_start_at TIMESTAMP,
    base_end_at TIMESTAMP,
    feature_config_hash VARCHAR(128),
    record_count INTEGER,
    created_by VARCHAR(50),
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS tb_feature_dataset (
    feature_id BIGSERIAL PRIMARY KEY,
    dataset_version_id VARCHAR(80) NOT NULL REFERENCES tb_dataset_version(dataset_version_id),
    site_id VARCHAR(50) NOT NULL REFERENCES tb_site(site_id),
    feature_at TIMESTAMP NOT NULL,
    target_heat_demand NUMERIC(18,6),
    temp NUMERIC(10,3),
    humidity NUMERIC(10,3),
    lag_24h_demand NUMERIC(18,6),
    lag_168h_demand NUMERIC(18,6),
    rolling_24h_avg NUMERIC(18,6),
    feature_json JSONB,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_feature_dataset ON tb_feature_dataset(dataset_version_id, site_id, feature_at);

CREATE TABLE IF NOT EXISTS tb_training_config (
    config_id VARCHAR(50) PRIMARY KEY,
    config_name VARCHAR(100) NOT NULL,
    feature_set_id VARCHAR(50) REFERENCES tb_feature_set(feature_set_id),
    algorithm VARCHAR(50) NOT NULL,
    train_period_months INTEGER DEFAULT 24,
    validation_period_months INTEGER DEFAULT 3,
    hyperparams JSONB,
    active_yn CHAR(1) NOT NULL DEFAULT 'Y',
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS tb_training_job (
    job_id VARCHAR(80) PRIMARY KEY,
    config_id VARCHAR(50) REFERENCES tb_training_config(config_id),
    pipeline_run_id VARCHAR(80),
    status VARCHAR(20) NOT NULL,
    site_ids JSONB,
    train_start_at DATE,
    train_end_at DATE,
    validation_start_at DATE,
    validation_end_at DATE,
    mlflow_run_id VARCHAR(80),
    registered_model_name VARCHAR(100),
    registered_model_version VARCHAR(20),
    metrics JSONB,
    started_at TIMESTAMP,
    ended_at TIMESTAMP,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- 모델/MLOps
CREATE TABLE IF NOT EXISTS tb_model_experiment (
    experiment_id VARCHAR(80) PRIMARY KEY,
    mlflow_run_id VARCHAR(80),
    dataset_version_id VARCHAR(80) REFERENCES tb_dataset_version(dataset_version_id),
    algorithm VARCHAR(50) NOT NULL,
    parameter_json JSONB,
    metric_json JSONB,
    trained_at TIMESTAMP NOT NULL,
    created_by VARCHAR(50)
);

CREATE TABLE IF NOT EXISTS tb_model_version (
    model_version_id VARCHAR(80) PRIMARY KEY,
    model_name VARCHAR(100) NOT NULL,
    version_no VARCHAR(20) NOT NULL,
    experiment_id VARCHAR(80) REFERENCES tb_model_experiment(experiment_id),
    mlflow_model_uri VARCHAR(500),
    artifact_uri VARCHAR(500),
    model_stage VARCHAR(20) NOT NULL,
    metric_summary_json JSONB,
    registered_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- 예측
CREATE TABLE IF NOT EXISTS tb_prediction_job (
    prediction_job_id VARCHAR(80) PRIMARY KEY,
    pipeline_run_id VARCHAR(80),
    model_version_id VARCHAR(80) REFERENCES tb_model_version(model_version_id),
    prediction_horizon VARCHAR(20) NOT NULL,
    target_start_at TIMESTAMP NOT NULL,
    target_end_at TIMESTAMP NOT NULL,
    site_ids JSONB,
    job_status VARCHAR(20) NOT NULL,
    started_at TIMESTAMP,
    finished_at TIMESTAMP,
    result_summary JSONB,
    error_message TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS tb_heat_demand_prediction (
    prediction_id BIGSERIAL PRIMARY KEY,
    prediction_job_id VARCHAR(80) NOT NULL REFERENCES tb_prediction_job(prediction_job_id),
    site_id VARCHAR(50) NOT NULL REFERENCES tb_site(site_id),
    target_at TIMESTAMP NOT NULL,
    predicted_demand NUMERIC(18,6) NOT NULL,
    lower_bound NUMERIC(18,6),
    upper_bound NUMERIC(18,6),
    model_version_id VARCHAR(80) NOT NULL REFERENCES tb_model_version(model_version_id),
    feature_set_id VARCHAR(50),
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    CONSTRAINT uk_heat_prediction UNIQUE(prediction_job_id, site_id, target_at)
);

CREATE UNIQUE INDEX IF NOT EXISTS uk_heat_pred_site_model_time
    ON tb_heat_demand_prediction(site_id, target_at, model_version_id);

CREATE INDEX IF NOT EXISTS ix_heat_prediction_site_time ON tb_heat_demand_prediction(site_id, target_at DESC);

CREATE TABLE IF NOT EXISTS tb_prediction_actual_match (
    match_id BIGSERIAL PRIMARY KEY,
    prediction_id BIGINT NOT NULL REFERENCES tb_heat_demand_prediction(prediction_id),
    site_id VARCHAR(50) NOT NULL REFERENCES tb_site(site_id),
    target_at TIMESTAMP NOT NULL,
    model_version_id VARCHAR(80) NOT NULL REFERENCES tb_model_version(model_version_id),
    prediction_job_id VARCHAR(80),
    predicted_demand NUMERIC(18,6) NOT NULL,
    actual_demand NUMERIC(18,6) NOT NULL,
    error NUMERIC(18,6),
    abs_error NUMERIC(18,6),
    squared_error NUMERIC(18,6),
    ape NUMERIC(18,6),
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    CONSTRAINT uk_pred_actual_match_prediction UNIQUE(prediction_id)
);

CREATE UNIQUE INDEX IF NOT EXISTS uk_pred_actual_match_site_time_model
    ON tb_prediction_actual_match(site_id, target_at, model_version_id);

CREATE INDEX IF NOT EXISTS ix_pred_actual_match_model_time
    ON tb_prediction_actual_match(model_version_id, target_at DESC);

-- 모니터링
CREATE TABLE IF NOT EXISTS tb_model_performance_metric (
    metric_id BIGSERIAL PRIMARY KEY,
    site_id VARCHAR(50) NOT NULL REFERENCES tb_site(site_id),
    model_version_id VARCHAR(80) NOT NULL REFERENCES tb_model_version(model_version_id),
    eval_start_at TIMESTAMP NOT NULL,
    eval_end_at TIMESTAMP NOT NULL,
    mae NUMERIC(18,6),
    rmse NUMERIC(18,6),
    mape NUMERIC(18,6),
    sample_count INTEGER,
    metric_json JSONB,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_perf_metric ON tb_model_performance_metric(site_id, model_version_id, eval_end_at DESC);

CREATE TABLE IF NOT EXISTS tb_drift_report (
    drift_report_id VARCHAR(80) PRIMARY KEY,
    dataset_version_id VARCHAR(80) REFERENCES tb_dataset_version(dataset_version_id),
    model_version_id VARCHAR(80) REFERENCES tb_model_version(model_version_id),
    feature_set_id VARCHAR(50),
    site_id VARCHAR(50),
    base_period VARCHAR(100),
    current_period VARCHAR(100),
    baseline_start_at TIMESTAMP,
    baseline_end_at TIMESTAMP,
    current_start_at TIMESTAMP,
    current_end_at TIMESTAMP,
    drift_type VARCHAR(20),
    drift_status VARCHAR(20) NOT NULL,
    drift_score NUMERIC(10,6),
    drift_score_json JSONB,
    recommendation TEXT,
    source_type VARCHAR(20),
    report_uri VARCHAR(500),
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS tb_retraining_candidate (
    candidate_id VARCHAR(50) PRIMARY KEY,
    reason VARCHAR(500) NOT NULL,
    reason_summary VARCHAR(500),
    model_name VARCHAR(100),
    model_version VARCHAR(20),
    model_version_id VARCHAR(80),
    feature_set_id VARCHAR(50),
    site_id VARCHAR(50),
    reason_type VARCHAR(50),
    severity VARCHAR(20),
    risk_level VARCHAR(20),
    drift_report_id VARCHAR(80),
    metric_snapshot_json JSONB,
    source_type VARCHAR(20),
    status VARCHAR(20) NOT NULL DEFAULT 'PENDING',
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS tb_pipeline_run (
    pipeline_run_id VARCHAR(80) PRIMARY KEY,
    pipeline_id VARCHAR(50) NOT NULL,
    pipeline_name VARCHAR(100),
    pipeline_type VARCHAR(30) NOT NULL,
    orchestrator VARCHAR(30) NOT NULL DEFAULT 'AIRFLOW',
    orchestrator_run_id VARCHAR(120),
    run_status VARCHAR(20) NOT NULL,
    started_at TIMESTAMP NOT NULL,
    finished_at TIMESTAMP,
    message TEXT,
    result_summary JSONB
);

CREATE INDEX IF NOT EXISTS ix_pipeline_run ON tb_pipeline_run(pipeline_type, run_status, started_at DESC);

CREATE TABLE IF NOT EXISTS tb_system_config (
    config_key VARCHAR(100) PRIMARY KEY,
    config_name VARCHAR(200),
    config_value TEXT,
    config_type VARCHAR(20),
    scope VARCHAR(50),
    description VARCHAR(500),
    editable_yn CHAR(1) NOT NULL DEFAULT 'Y',
    updated_by VARCHAR(50),
    updated_at TIMESTAMP
);

-- Airflow uses separate database (created in 00_airflow_db.sql)
