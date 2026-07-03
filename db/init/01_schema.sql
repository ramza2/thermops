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

CREATE TABLE IF NOT EXISTS tb_feature_column_role (
    role_id VARCHAR(50) PRIMARY KEY,
    mapping_id VARCHAR(50) REFERENCES tb_data_mapping(mapping_id),
    data_source_id VARCHAR(50) REFERENCES tb_data_source(data_source_id),
    source_table VARCHAR(100),
    target_table VARCHAR(100),
    source_column VARCHAR(100) NOT NULL,
    target_column VARCHAR(100),
    data_type VARCHAR(50),
    column_role VARCHAR(50) NOT NULL,
    inferred_role VARCHAR(50),
    inference_confidence NUMERIC(5,2),
    role_source VARCHAR(20) NOT NULL DEFAULT 'MANUAL',
    description TEXT,
    active_yn CHAR(1) NOT NULL DEFAULT 'Y',
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_feature_column_role_mapping_source
    ON tb_feature_column_role(mapping_id, source_column)
    WHERE mapping_id IS NOT NULL AND active_yn = 'Y';

CREATE INDEX IF NOT EXISTS ix_feature_column_role_mapping
    ON tb_feature_column_role(mapping_id)
    WHERE active_yn = 'Y';

CREATE INDEX IF NOT EXISTS ix_feature_column_role_target_table
    ON tb_feature_column_role(target_table)
    WHERE active_yn = 'Y';

-- Standard dataset type catalog (R7)
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
    physical_table_schema VARCHAR(63) NOT NULL DEFAULT 'public',
    managed_table_yn CHAR(1) NOT NULL DEFAULT 'N',
    table_create_status VARCHAR(30) NOT NULL DEFAULT 'NOT_CREATED',
    table_create_sql_preview TEXT,
    table_create_error TEXT,
    physical_table_created_at TIMESTAMP,
    physical_table_created_by VARCHAR(100),
    build_supported_yn CHAR(1) NOT NULL DEFAULT 'N',
    recipe_supported_yn CHAR(1) NOT NULL DEFAULT 'N',
    mapping_supported_yn CHAR(1) NOT NULL DEFAULT 'Y',
    status VARCHAR(30) NOT NULL DEFAULT 'ACTIVE',
    owner VARCHAR(100),
    active_yn CHAR(1) NOT NULL DEFAULT 'Y',
    archived_at TIMESTAMP,
    archive_reason TEXT,
    business_domain VARCHAR(100),
    tags_json JSONB,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS tb_standard_dataset_column (
    column_id VARCHAR(50) PRIMARY KEY,
    dataset_type_id VARCHAR(50) NOT NULL REFERENCES tb_standard_dataset_type(dataset_type_id),
    column_name VARCHAR(120) NOT NULL,
    display_name VARCHAR(200),
    data_type VARCHAR(80) NOT NULL,
    data_length INTEGER,
    numeric_precision INTEGER,
    numeric_scale INTEGER,
    nullable_yn CHAR(1) NOT NULL DEFAULT 'Y',
    required_yn CHAR(1) NOT NULL DEFAULT 'N',
    primary_key_yn CHAR(1) NOT NULL DEFAULT 'N',
    unique_yn CHAR(1) NOT NULL DEFAULT 'N',
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

-- Feature Recipe Builder (R5)
CREATE TABLE IF NOT EXISTS tb_feature_recipe (
    recipe_id VARCHAR(50) PRIMARY KEY,
    feature_name VARCHAR(100),
    display_name VARCHAR(200) NOT NULL,
    description TEXT,
    domain VARCHAR(50),
    task_type VARCHAR(50),
    calc_mode VARCHAR(20) NOT NULL DEFAULT 'TEMPLATE',
    recipe_type VARCHAR(50) NOT NULL,
    mapping_id VARCHAR(50),
    data_source_id VARCHAR(50),
    source_table VARCHAR(100),
    target_table VARCHAR(100),
    source_columns JSONB NOT NULL DEFAULT '[]',
    entity_keys JSONB,
    time_key VARCHAR(100),
    target_column VARCHAR(100),
    params JSONB NOT NULL DEFAULT '{}',
    output_feature_names JSONB,
    output_data_type VARCHAR(50),
    unit VARCHAR(50),
    null_handling VARCHAR(50),
    leakage_policy VARCHAR(50),
    validation_summary JSONB,
    preview_summary JSONB,
    lineage_preview JSONB,
    quality_preview JSONB,
    status VARCHAR(30) NOT NULL DEFAULT 'DRAFT',
    version INTEGER NOT NULL DEFAULT 1,
    owner VARCHAR(100),
    active_yn CHAR(1) NOT NULL DEFAULT 'Y',
    published_at TIMESTAMP,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS tb_feature_recipe_version (
    version_id VARCHAR(50) PRIMARY KEY,
    recipe_id VARCHAR(50) NOT NULL REFERENCES tb_feature_recipe(recipe_id),
    version_no INTEGER NOT NULL,
    recipe_snapshot JSONB NOT NULL,
    change_reason TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_feature_recipe_published_feature_name
    ON tb_feature_recipe(feature_name)
    WHERE active_yn = 'Y' AND status = 'PUBLISHED' AND feature_name IS NOT NULL;

CREATE INDEX IF NOT EXISTS ix_feature_recipe_status ON tb_feature_recipe(status) WHERE active_yn = 'Y';
CREATE INDEX IF NOT EXISTS ix_feature_recipe_mapping ON tb_feature_recipe(mapping_id) WHERE active_yn = 'Y';
CREATE INDEX IF NOT EXISTS ix_feature_recipe_type ON tb_feature_recipe(recipe_type) WHERE active_yn = 'Y';

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

CREATE TABLE IF NOT EXISTS tb_feature_lineage (
    lineage_id BIGSERIAL PRIMARY KEY,
    dataset_version_id VARCHAR(80) NOT NULL REFERENCES tb_dataset_version(dataset_version_id),
    feature_build_job_id VARCHAR(80),
    feature_set_id VARCHAR(50) NOT NULL,
    feature_name VARCHAR(100) NOT NULL,
    registry_version VARCHAR(20) NOT NULL DEFAULT '1.0',
    calc_method VARCHAR(20) NOT NULL DEFAULT 'CODE',
    calc_expression TEXT,
    source_tables JSONB,
    source_columns JSONB,
    partition_keys JSONB,
    time_key VARCHAR(50),
    lookback_hours INTEGER,
    requires_shift BOOLEAN,
    leakage_safe BOOLEAN,
    build_start_at TIMESTAMP,
    build_end_at TIMESTAMP,
    site_filter VARCHAR(50),
    lineage_json JSONB,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_feature_lineage_dsv ON tb_feature_lineage(dataset_version_id);
CREATE INDEX IF NOT EXISTS ix_feature_lineage_job ON tb_feature_lineage(feature_build_job_id);
-- dataset_version_id = DSV-{feature_set_id}-{timestamp} 이므로 Feature Set별 유일. 동일 DSV 내 Feature당 1행.
CREATE UNIQUE INDEX IF NOT EXISTS ux_feature_lineage_dsv_feature ON tb_feature_lineage(dataset_version_id, feature_name);

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

CREATE INDEX IF NOT EXISTS ix_heat_prediction_model_time ON tb_heat_demand_prediction(model_version_id, target_at DESC);

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
    training_job_id VARCHAR(80),
    new_model_version_id VARCHAR(80),
    mlflow_run_id VARCHAR(80),
    trained_at TIMESTAMP,
    train_result_summary JSONB,
    error_message TEXT,
    retraining_dag_run_id VARCHAR(120),
    retraining_requested_at TIMESTAMP,
    retraining_started_at TIMESTAMP,
    retraining_finished_at TIMESTAMP,
    execution_mode VARCHAR(20),
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

-- Pipeline Builder (R8)
CREATE TABLE IF NOT EXISTS tb_pipeline_template (
    template_id VARCHAR(50) PRIMARY KEY,
    template_code VARCHAR(80) NOT NULL UNIQUE,
    template_name VARCHAR(200) NOT NULL,
    description TEXT,
    pipeline_type VARCHAR(80) NOT NULL,
    airflow_dag_id VARCHAR(200),
    template_version VARCHAR(30) NOT NULL DEFAULT '1.0',
    node_schema_json JSONB NOT NULL,
    edge_schema_json JSONB NOT NULL,
    default_config_json JSONB,
    status VARCHAR(30) NOT NULL DEFAULT 'ACTIVE',
    active_yn CHAR(1) NOT NULL DEFAULT 'Y',
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS tb_pipeline_definition (
    pipeline_id VARCHAR(50) PRIMARY KEY,
    template_id VARCHAR(50) NOT NULL REFERENCES tb_pipeline_template(template_id),
    pipeline_name VARCHAR(200) NOT NULL,
    description TEXT,
    pipeline_type VARCHAR(80) NOT NULL,
    airflow_dag_id VARCHAR(200),
    node_config_json JSONB NOT NULL DEFAULT '{}',
    edge_config_json JSONB,
    runtime_params_json JSONB,
    schedule_config_json JSONB,
    validation_result_json JSONB,
    status VARCHAR(30) NOT NULL DEFAULT 'DRAFT',
    last_validated_at TIMESTAMP,
    last_run_id VARCHAR(80),
    active_yn CHAR(1) NOT NULL DEFAULT 'Y',
    created_by VARCHAR(100),
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS tb_pipeline_definition_version (
    version_id VARCHAR(50) PRIMARY KEY,
    pipeline_id VARCHAR(50) NOT NULL REFERENCES tb_pipeline_definition(pipeline_id),
    version_no INTEGER NOT NULL,
    snapshot_json JSONB NOT NULL,
    change_summary TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_pipeline_definition_template
    ON tb_pipeline_definition(template_id)
    WHERE active_yn = 'Y';

CREATE INDEX IF NOT EXISTS ix_pipeline_definition_status
    ON tb_pipeline_definition(status)
    WHERE active_yn = 'Y';

CREATE UNIQUE INDEX IF NOT EXISTS ux_pipeline_definition_version
    ON tb_pipeline_definition_version(pipeline_id, version_no);

-- Pipeline Definition 실행 이력 연결 (R9)
CREATE TABLE IF NOT EXISTS tb_pipeline_run_link (
    link_id VARCHAR(50) PRIMARY KEY,
    pipeline_id VARCHAR(50) NOT NULL REFERENCES tb_pipeline_definition(pipeline_id),
    template_id VARCHAR(50) NOT NULL REFERENCES tb_pipeline_template(template_id),
    pipeline_run_id VARCHAR(80) NOT NULL,
    airflow_dag_id VARCHAR(200),
    airflow_run_id VARCHAR(250),
    run_source VARCHAR(50) NOT NULL DEFAULT 'PIPELINE_DEFINITION',
    run_status VARCHAR(50) NOT NULL DEFAULT 'REQUESTED',
    runtime_params_snapshot JSONB,
    node_config_snapshot JSONB,
    validation_snapshot JSONB,
    trigger_response_json JSONB,
    error_message TEXT,
    requested_by VARCHAR(100),
    requested_at TIMESTAMP NOT NULL DEFAULT NOW(),
    started_at TIMESTAMP,
    finished_at TIMESTAMP,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_pipeline_run_link_pipeline
    ON tb_pipeline_run_link(pipeline_id, requested_at DESC);

CREATE INDEX IF NOT EXISTS ix_pipeline_run_link_template
    ON tb_pipeline_run_link(template_id, requested_at DESC);

CREATE INDEX IF NOT EXISTS ix_pipeline_run_link_run_id
    ON tb_pipeline_run_link(pipeline_run_id);

CREATE INDEX IF NOT EXISTS ix_pipeline_run_link_airflow
    ON tb_pipeline_run_link(airflow_dag_id, airflow_run_id);

CREATE INDEX IF NOT EXISTS ix_pipeline_run_link_status
    ON tb_pipeline_run_link(run_status, requested_at DESC);

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
