-- THERMOps PostgreSQL Schema v0.1
-- Reference: docs/md/THERMOps_DB_설계서.md
--
-- CREATE TABLE IF NOT EXISTS 는 동시 세션(예: apply_dev_migrations)과 경합 시
-- pg_type_typname_nsp_index unique_violation 이 날 수 있다.
-- docker-entrypoint 는 SQL 오류 시 init 실패로 Postgres가 종료되므로,
-- 각 CREATE TABLE 을 DO 블록으로 감싸 duplicate_table/unique_violation 을 무시한다.
-- 파일 끝 tb_schema_init_ready 는 migration 경합 방지용 완료 마커이다.

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- 기준정보
DO $thermops_ct$
BEGIN
    CREATE TABLE IF NOT EXISTS tb_site (
    site_id VARCHAR(50) PRIMARY KEY,
    site_name VARCHAR(100) NOT NULL,
    site_type VARCHAR(20) NOT NULL,
    parent_site_id VARCHAR(50),
    active_yn CHAR(1) NOT NULL DEFAULT 'Y',
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP
);
EXCEPTION
    WHEN duplicate_table THEN NULL;
    WHEN unique_violation THEN NULL;
END $thermops_ct$;

DO $thermops_ct$
BEGIN
    CREATE TABLE IF NOT EXISTS tb_weather_area (
    weather_area_id VARCHAR(50) PRIMARY KEY,
    area_name VARCHAR(100) NOT NULL,
    latitude NUMERIC(10,6),
    longitude NUMERIC(10,6),
    provider VARCHAR(50),
    active_yn CHAR(1) NOT NULL DEFAULT 'Y',
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);
EXCEPTION
    WHEN duplicate_table THEN NULL;
    WHEN unique_violation THEN NULL;
END $thermops_ct$;

DO $thermops_ct$
BEGIN
    CREATE TABLE IF NOT EXISTS tb_site_weather_mapping (
    mapping_id BIGSERIAL PRIMARY KEY,
    site_id VARCHAR(50) NOT NULL REFERENCES tb_site(site_id),
    weather_area_id VARCHAR(50) NOT NULL REFERENCES tb_weather_area(weather_area_id),
    priority_no INTEGER NOT NULL DEFAULT 1,
    valid_from DATE,
    valid_to DATE,
    active_yn CHAR(1) NOT NULL DEFAULT 'Y'
);
EXCEPTION
    WHEN duplicate_table THEN NULL;
    WHEN unique_violation THEN NULL;
END $thermops_ct$;

DO $thermops_ct$
BEGIN
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
EXCEPTION
    WHEN duplicate_table THEN NULL;
    WHEN unique_violation THEN NULL;
END $thermops_ct$;

-- 연계/적재
DO $thermops_ct$
BEGIN
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
EXCEPTION
    WHEN duplicate_table THEN NULL;
    WHEN unique_violation THEN NULL;
END $thermops_ct$;

DO $thermops_ct$
BEGIN
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
EXCEPTION
    WHEN duplicate_table THEN NULL;
    WHEN unique_violation THEN NULL;
END $thermops_ct$;

DO $thermops_ct$
BEGIN
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
EXCEPTION
    WHEN duplicate_table THEN NULL;
    WHEN unique_violation THEN NULL;
END $thermops_ct$;

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
DO $thermops_ct$
BEGIN
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
EXCEPTION
    WHEN duplicate_table THEN NULL;
    WHEN unique_violation THEN NULL;
END $thermops_ct$;

DO $thermops_ct$
BEGIN
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
EXCEPTION
    WHEN duplicate_table THEN NULL;
    WHEN unique_violation THEN NULL;
END $thermops_ct$;

CREATE UNIQUE INDEX IF NOT EXISTS ux_standard_dataset_column_active
    ON tb_standard_dataset_column(dataset_type_id, column_name)
    WHERE active_yn = 'Y';

CREATE INDEX IF NOT EXISTS ix_standard_dataset_type_target_table
    ON tb_standard_dataset_type(target_table)
    WHERE active_yn = 'Y';

DO $thermops_ct$
BEGIN
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
EXCEPTION
    WHEN duplicate_table THEN NULL;
    WHEN unique_violation THEN NULL;
END $thermops_ct$;

CREATE INDEX IF NOT EXISTS ix_std_dataset_table_create_log_dataset
    ON tb_standard_dataset_table_create_log(dataset_type_id, created_at DESC);

-- Feature Recipe Builder (R5)
DO $thermops_ct$
BEGIN
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
EXCEPTION
    WHEN duplicate_table THEN NULL;
    WHEN unique_violation THEN NULL;
END $thermops_ct$;

DO $thermops_ct$
BEGIN
    CREATE TABLE IF NOT EXISTS tb_feature_recipe_version (
    version_id VARCHAR(50) PRIMARY KEY,
    recipe_id VARCHAR(50) NOT NULL REFERENCES tb_feature_recipe(recipe_id),
    version_no INTEGER NOT NULL,
    recipe_snapshot JSONB NOT NULL,
    change_reason TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);
EXCEPTION
    WHEN duplicate_table THEN NULL;
    WHEN unique_violation THEN NULL;
END $thermops_ct$;

CREATE UNIQUE INDEX IF NOT EXISTS ux_feature_recipe_published_feature_name
    ON tb_feature_recipe(feature_name)
    WHERE active_yn = 'Y' AND status = 'PUBLISHED' AND feature_name IS NOT NULL;

CREATE INDEX IF NOT EXISTS ix_feature_recipe_status ON tb_feature_recipe(status) WHERE active_yn = 'Y';
CREATE INDEX IF NOT EXISTS ix_feature_recipe_mapping ON tb_feature_recipe(mapping_id) WHERE active_yn = 'Y';
CREATE INDEX IF NOT EXISTS ix_feature_recipe_type ON tb_feature_recipe(recipe_type) WHERE active_yn = 'Y';

DO $thermops_ct$
BEGIN
    CREATE TABLE IF NOT EXISTS tb_data_quality_run (
    run_id VARCHAR(80) PRIMARY KEY,
    source_id VARCHAR(50),
    check_type VARCHAR(50) NOT NULL,
    run_status VARCHAR(20) NOT NULL,
    result_summary JSONB,
    started_at TIMESTAMP NOT NULL DEFAULT NOW(),
    finished_at TIMESTAMP
);
EXCEPTION
    WHEN duplicate_table THEN NULL;
    WHEN unique_violation THEN NULL;
END $thermops_ct$;

DO $thermops_ct$
BEGIN
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
EXCEPTION
    WHEN duplicate_table THEN NULL;
    WHEN unique_violation THEN NULL;
END $thermops_ct$;

CREATE INDEX IF NOT EXISTS ix_heat_actual_site_time ON tb_heat_demand_actual(site_id, measured_at DESC);

DO $thermops_ct$
BEGIN
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
EXCEPTION
    WHEN duplicate_table THEN NULL;
    WHEN unique_violation THEN NULL;
END $thermops_ct$;

CREATE INDEX IF NOT EXISTS ix_weather_area_time ON tb_weather_observation(weather_area_id, measured_at DESC);

DO $thermops_ct$
BEGIN
    CREATE TABLE IF NOT EXISTS tb_calendar (
    calendar_date DATE PRIMARY KEY,
    day_of_week INTEGER NOT NULL,
    is_weekend CHAR(1) NOT NULL,
    is_holiday CHAR(1) NOT NULL,
    holiday_name VARCHAR(100),
    season VARCHAR(20),
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);
EXCEPTION
    WHEN duplicate_table THEN NULL;
    WHEN unique_violation THEN NULL;
END $thermops_ct$;

-- Feature/학습
DO $thermops_ct$
BEGIN
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
EXCEPTION
    WHEN duplicate_table THEN NULL;
    WHEN unique_violation THEN NULL;
END $thermops_ct$;

DO $thermops_ct$
BEGIN
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
EXCEPTION
    WHEN duplicate_table THEN NULL;
    WHEN unique_violation THEN NULL;
END $thermops_ct$;

DO $thermops_ct$
BEGIN
    CREATE TABLE IF NOT EXISTS tb_dataset_version (
    dataset_version_id VARCHAR(80) PRIMARY KEY,
    dataset_type VARCHAR(30) NOT NULL,
    feature_set_id VARCHAR(50),
    base_start_at TIMESTAMP,
    base_end_at TIMESTAMP,
    feature_config_hash VARCHAR(128),
    record_count INTEGER,
    feature_count INTEGER,
    dataset_version_role VARCHAR(30) NOT NULL DEFAULT 'CANDIDATE',
    dataset_version_status VARCHAR(30) NOT NULL DEFAULT 'BUILD_SUCCESS',
    build_scope VARCHAR(30) NOT NULL DEFAULT 'UNKNOWN',
    is_primary BOOLEAN NOT NULL DEFAULT FALSE,
    is_training_ready BOOLEAN NOT NULL DEFAULT FALSE,
    is_serving_ready BOOLEAN NOT NULL DEFAULT FALSE,
    quality_score NUMERIC(10,4),
    coverage_ratio NUMERIC(10,6),
    null_ratio NUMERIC(10,6),
    build_started_at TIMESTAMP,
    build_finished_at TIMESTAMP,
    archived_at TIMESTAMP,
    archived_reason TEXT,
    selection_policy_note TEXT,
    metadata_json JSONB,
    created_by VARCHAR(50),
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);
EXCEPTION
    WHEN duplicate_table THEN NULL;
    WHEN unique_violation THEN NULL;
END $thermops_ct$;

CREATE INDEX IF NOT EXISTS ix_dataset_version_feature_set ON tb_dataset_version(feature_set_id);
CREATE INDEX IF NOT EXISTS ix_dataset_version_role ON tb_dataset_version(feature_set_id, dataset_version_role);
CREATE INDEX IF NOT EXISTS ix_dataset_version_status ON tb_dataset_version(feature_set_id, dataset_version_status);
CREATE UNIQUE INDEX IF NOT EXISTS ux_dataset_version_primary
    ON tb_dataset_version(feature_set_id)
    WHERE is_primary = TRUE AND archived_at IS NULL;

DO $thermops_ct$
BEGIN
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
EXCEPTION
    WHEN duplicate_table THEN NULL;
    WHEN unique_violation THEN NULL;
END $thermops_ct$;

CREATE INDEX IF NOT EXISTS ix_feature_dataset ON tb_feature_dataset(dataset_version_id, site_id, feature_at);

DO $thermops_ct$
BEGIN
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
EXCEPTION
    WHEN duplicate_table THEN NULL;
    WHEN unique_violation THEN NULL;
END $thermops_ct$;

CREATE INDEX IF NOT EXISTS ix_feature_lineage_dsv ON tb_feature_lineage(dataset_version_id);
CREATE INDEX IF NOT EXISTS ix_feature_lineage_job ON tb_feature_lineage(feature_build_job_id);
-- dataset_version_id = DSV-{feature_set_id}-{timestamp} 이므로 Feature Set별 유일. 동일 DSV 내 Feature당 1행.
CREATE UNIQUE INDEX IF NOT EXISTS ux_feature_lineage_dsv_feature ON tb_feature_lineage(dataset_version_id, feature_name);

DO $thermops_ct$
BEGIN
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
EXCEPTION
    WHEN duplicate_table THEN NULL;
    WHEN unique_violation THEN NULL;
END $thermops_ct$;

DO $thermops_ct$
BEGIN
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
EXCEPTION
    WHEN duplicate_table THEN NULL;
    WHEN unique_violation THEN NULL;
END $thermops_ct$;

-- 모델/MLOps
DO $thermops_ct$
BEGIN
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
EXCEPTION
    WHEN duplicate_table THEN NULL;
    WHEN unique_violation THEN NULL;
END $thermops_ct$;

DO $thermops_ct$
BEGIN
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
EXCEPTION
    WHEN duplicate_table THEN NULL;
    WHEN unique_violation THEN NULL;
END $thermops_ct$;

-- 예측
DO $thermops_ct$
BEGIN
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
EXCEPTION
    WHEN duplicate_table THEN NULL;
    WHEN unique_violation THEN NULL;
END $thermops_ct$;

DO $thermops_ct$
BEGIN
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
EXCEPTION
    WHEN duplicate_table THEN NULL;
    WHEN unique_violation THEN NULL;
END $thermops_ct$;

CREATE INDEX IF NOT EXISTS ix_heat_prediction_model_time ON tb_heat_demand_prediction(model_version_id, target_at DESC);

CREATE INDEX IF NOT EXISTS ix_heat_prediction_site_time ON tb_heat_demand_prediction(site_id, target_at DESC);

DO $thermops_ct$
BEGIN
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
EXCEPTION
    WHEN duplicate_table THEN NULL;
    WHEN unique_violation THEN NULL;
END $thermops_ct$;

CREATE UNIQUE INDEX IF NOT EXISTS uk_pred_actual_match_site_time_model
    ON tb_prediction_actual_match(site_id, target_at, model_version_id);

CREATE INDEX IF NOT EXISTS ix_pred_actual_match_model_time
    ON tb_prediction_actual_match(model_version_id, target_at DESC);

-- 모니터링
DO $thermops_ct$
BEGIN
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
EXCEPTION
    WHEN duplicate_table THEN NULL;
    WHEN unique_violation THEN NULL;
END $thermops_ct$;

CREATE INDEX IF NOT EXISTS ix_perf_metric ON tb_model_performance_metric(site_id, model_version_id, eval_end_at DESC);

DO $thermops_ct$
BEGIN
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
EXCEPTION
    WHEN duplicate_table THEN NULL;
    WHEN unique_violation THEN NULL;
END $thermops_ct$;

DO $thermops_ct$
BEGIN
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
EXCEPTION
    WHEN duplicate_table THEN NULL;
    WHEN unique_violation THEN NULL;
END $thermops_ct$;

DO $thermops_ct$
BEGIN
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
EXCEPTION
    WHEN duplicate_table THEN NULL;
    WHEN unique_violation THEN NULL;
END $thermops_ct$;

CREATE INDEX IF NOT EXISTS ix_pipeline_run ON tb_pipeline_run(pipeline_type, run_status, started_at DESC);

-- Pipeline Builder (R8)
DO $thermops_ct$
BEGIN
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
EXCEPTION
    WHEN duplicate_table THEN NULL;
    WHEN unique_violation THEN NULL;
END $thermops_ct$;

DO $thermops_ct$
BEGIN
    CREATE TABLE IF NOT EXISTS tb_pipeline_definition (
    pipeline_id VARCHAR(50) PRIMARY KEY,
    template_id VARCHAR(50) NOT NULL REFERENCES tb_pipeline_template(template_id),
    pipeline_name VARCHAR(200) NOT NULL,
    description TEXT,
    pipeline_type VARCHAR(80) NOT NULL,
    pipeline_kind VARCHAR(50) NOT NULL DEFAULT 'MLOPS_FLOW',
    airflow_dag_id VARCHAR(200),
    node_config_json JSONB NOT NULL DEFAULT '{}',
    edge_config_json JSONB,
    runtime_params_json JSONB,
    schedule_config_json JSONB,
    validation_result_json JSONB,
    current_graph_json JSONB,
    current_sync_status VARCHAR(30) NOT NULL DEFAULT 'NOT_COMPILED',
    status VARCHAR(30) NOT NULL DEFAULT 'DRAFT',
    last_validated_at TIMESTAMP,
    last_run_id VARCHAR(80),
    active_yn CHAR(1) NOT NULL DEFAULT 'Y',
    created_by VARCHAR(100),
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP
);
EXCEPTION
    WHEN duplicate_table THEN NULL;
    WHEN unique_violation THEN NULL;
END $thermops_ct$;

DO $thermops_ct$
BEGIN
    CREATE TABLE IF NOT EXISTS tb_pipeline_definition_version (
    version_id VARCHAR(50) PRIMARY KEY,
    pipeline_id VARCHAR(50) NOT NULL REFERENCES tb_pipeline_definition(pipeline_id),
    version_no INTEGER NOT NULL,
    snapshot_json JSONB NOT NULL,
    change_summary TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);
EXCEPTION
    WHEN duplicate_table THEN NULL;
    WHEN unique_violation THEN NULL;
END $thermops_ct$;

CREATE INDEX IF NOT EXISTS ix_pipeline_definition_template
    ON tb_pipeline_definition(template_id)
    WHERE active_yn = 'Y';

CREATE INDEX IF NOT EXISTS ix_pipeline_definition_status
    ON tb_pipeline_definition(status)
    WHERE active_yn = 'Y';

CREATE INDEX IF NOT EXISTS ix_pipeline_definition_kind
    ON tb_pipeline_definition(pipeline_kind);

CREATE UNIQUE INDEX IF NOT EXISTS ux_pipeline_definition_version
    ON tb_pipeline_definition_version(pipeline_id, version_no);

-- R11-S6-2 Visual Pipeline Compile Result (Option C)
DO $thermops_ct$
BEGIN
    CREATE TABLE IF NOT EXISTS tb_visual_pipeline_compile_result (
    compile_result_id VARCHAR(50) PRIMARY KEY,
    pipeline_id VARCHAR(50) NOT NULL REFERENCES tb_pipeline_definition(pipeline_id),
    compile_status VARCHAR(30) NOT NULL,
    validation_level VARCHAR(20) NOT NULL DEFAULT 'STRICT',
    graph_version_hash VARCHAR(100),
    config_hash VARCHAR(100),
    compile_version VARCHAR(30) NOT NULL DEFAULT 'R11-S6-2',
    compiled_artifact_json JSONB,
    issues_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    error_message TEXT,
    source VARCHAR(40) NOT NULL DEFAULT 'COMPILE_API',
    created_by VARCHAR(100),
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);
EXCEPTION
    WHEN duplicate_table THEN NULL;
    WHEN unique_violation THEN NULL;
END $thermops_ct$;

CREATE INDEX IF NOT EXISTS ix_vp_compile_result_pipeline_created
    ON tb_visual_pipeline_compile_result(pipeline_id, created_at DESC);

CREATE INDEX IF NOT EXISTS ix_vp_compile_result_pipeline_status_created
    ON tb_visual_pipeline_compile_result(pipeline_id, compile_status, created_at DESC);

CREATE INDEX IF NOT EXISTS ix_vp_compile_result_graph_hash
    ON tb_visual_pipeline_compile_result(graph_version_hash);

-- R11-S6-4 Visual Pipeline Materialization Result
DO $thermops_ct$
BEGIN
    CREATE TABLE IF NOT EXISTS tb_visual_pipeline_materialization_result (
    materialization_result_id VARCHAR(50) PRIMARY KEY,
    pipeline_id VARCHAR(50) NOT NULL REFERENCES tb_pipeline_definition(pipeline_id),
    compile_result_id VARCHAR(50) NOT NULL,
    materialization_status VARCHAR(30) NOT NULL,
    graph_version_hash VARCHAR(100),
    materialization_version VARCHAR(30) NOT NULL DEFAULT 'R11-S6-4',
    objects_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    updated_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    skipped_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    issues_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    warnings_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    activation VARCHAR(40) NOT NULL DEFAULT 'NOT_REQUESTED',
    run_created BOOLEAN NOT NULL DEFAULT FALSE,
    error_message TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);
EXCEPTION
    WHEN duplicate_table THEN NULL;
    WHEN unique_violation THEN NULL;
END $thermops_ct$;

CREATE INDEX IF NOT EXISTS ix_vp_materialization_pipeline_created
    ON tb_visual_pipeline_materialization_result(pipeline_id, created_at DESC);

CREATE INDEX IF NOT EXISTS ix_vp_materialization_compile_result
    ON tb_visual_pipeline_materialization_result(compile_result_id);

-- R11-S7-1 Visual Pipeline Manual Run mapping
DO $thermops_ct$
BEGIN
    CREATE TABLE IF NOT EXISTS tb_visual_pipeline_run (
    visual_run_id VARCHAR(50) PRIMARY KEY,
    pipeline_id VARCHAR(50) NOT NULL REFERENCES tb_pipeline_definition(pipeline_id),
    compile_result_id VARCHAR(50) NOT NULL,
    materialization_result_id VARCHAR(50) NOT NULL,
    graph_version_hash VARCHAR(100),
    load_run_id VARCHAR(50),
    mode VARCHAR(30) NOT NULL DEFAULT 'MANUAL',
    execution_mode VARCHAR(30) NOT NULL DEFAULT 'SYNC',
    run_status VARCHAR(30) NOT NULL,
    request_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    result_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    issues_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    error_message TEXT,
    claimed_at TIMESTAMP,
    claimed_by VARCHAR(120),
    locked_until TIMESTAMP,
    heartbeat_at TIMESTAMP,
    attempt_count INTEGER NOT NULL DEFAULT 0,
    activation_id VARCHAR(40),
    r10_schedule_id VARCHAR(40),
    scheduled_for TIMESTAMP,
    triggered_at TIMESTAMP,
    dedup_key VARCHAR(160),
    started_at TIMESTAMP,
    finished_at TIMESTAMP,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);
EXCEPTION
    WHEN duplicate_table THEN NULL;
    WHEN unique_violation THEN NULL;
END $thermops_ct$;

CREATE INDEX IF NOT EXISTS ix_vp_run_pipeline_created
    ON tb_visual_pipeline_run(pipeline_id, created_at DESC);

CREATE INDEX IF NOT EXISTS ix_vp_run_pipeline_status
    ON tb_visual_pipeline_run(pipeline_id, run_status);

CREATE INDEX IF NOT EXISTS ix_vp_run_status_created
    ON tb_visual_pipeline_run(run_status, created_at);

CREATE INDEX IF NOT EXISTS ix_vp_run_status_locked_until
    ON tb_visual_pipeline_run(run_status, locked_until);

CREATE INDEX IF NOT EXISTS ix_vp_run_activation_scheduled_for
    ON tb_visual_pipeline_run(activation_id, scheduled_for);

CREATE UNIQUE INDEX IF NOT EXISTS ux_vp_run_dedup_key
    ON tb_visual_pipeline_run(dedup_key)
    WHERE dedup_key IS NOT NULL;

-- R11-S7-8 Visual Pipeline Schedule Activation
DO $thermops_ct$
BEGIN
    CREATE TABLE IF NOT EXISTS tb_visual_pipeline_schedule_activation (
    activation_id VARCHAR(40) PRIMARY KEY,
    pipeline_id VARCHAR(50) NOT NULL,
    materialization_result_id VARCHAR(40) NOT NULL,
    compile_result_id VARCHAR(40),
    r10_schedule_id VARCHAR(40) NOT NULL,
    activation_status VARCHAR(30) NOT NULL,
    cron_expression VARCHAR(120),
    timezone VARCHAR(80),
    activated_at TIMESTAMP,
    deactivated_at TIMESTAMP,
    paused_at TIMESTAMP,
    resumed_at TIMESTAMP,
    next_due_at TIMESTAMP,
    last_triggered_at TIMESTAMP,
    last_due_at TIMESTAMP,
    last_skip_at TIMESTAMP,
    last_skip_reason VARCHAR(80),
    trigger_count INTEGER NOT NULL DEFAULT 0,
    missed_count INTEGER NOT NULL DEFAULT 0,
    metadata_json JSONB,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);
EXCEPTION
    WHEN duplicate_table THEN NULL;
    WHEN unique_violation THEN NULL;
END $thermops_ct$;

CREATE INDEX IF NOT EXISTS ix_vp_schedule_activation_pipeline_status
    ON tb_visual_pipeline_schedule_activation(pipeline_id, activation_status);

CREATE INDEX IF NOT EXISTS ix_vp_schedule_activation_status_next_due
    ON tb_visual_pipeline_schedule_activation(activation_status, next_due_at);

CREATE INDEX IF NOT EXISTS ix_vp_schedule_activation_mat_result
    ON tb_visual_pipeline_schedule_activation(materialization_result_id);

CREATE INDEX IF NOT EXISTS ix_vp_schedule_activation_r10_schedule
    ON tb_visual_pipeline_schedule_activation(r10_schedule_id);

CREATE UNIQUE INDEX IF NOT EXISTS ux_vp_schedule_activation_pipeline_active
    ON tb_visual_pipeline_schedule_activation(pipeline_id)
    WHERE activation_status = 'ACTIVE';

-- R11-S7-13 Visual Pipeline Audit Log (no FK — independent ops history)
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

-- Pipeline Definition 실행 이력 연결 (R9)
DO $thermops_ct$
BEGIN
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
EXCEPTION
    WHEN duplicate_table THEN NULL;
    WHEN unique_violation THEN NULL;
END $thermops_ct$;

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

DO $thermops_ct$
BEGIN
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
EXCEPTION
    WHEN duplicate_table THEN NULL;
    WHEN unique_violation THEN NULL;
END $thermops_ct$;

-- Airflow uses separate database (created in 00_airflow_db.sql)

-- R10 Generic REST API Connector Builder
DO $thermops_ct$
BEGIN
    CREATE TABLE IF NOT EXISTS tb_api_connector_operation (
    operation_id VARCHAR(50) PRIMARY KEY,
    data_source_id VARCHAR(50) NOT NULL REFERENCES tb_data_source(data_source_id),
    operation_name VARCHAR(200) NOT NULL,
    operation_description TEXT,
    http_method VARCHAR(10) NOT NULL DEFAULT 'GET',
    endpoint_path TEXT NOT NULL,
    full_url_preview TEXT,
    request_content_type VARCHAR(50) NOT NULL DEFAULT 'QUERY',
    response_format VARCHAR(20) NOT NULL DEFAULT 'JSON',
    response_item_path TEXT,
    result_array_mode VARCHAR(30) NOT NULL DEFAULT 'AUTO',
    target_table VARCHAR(100),
    standard_dataset_id VARCHAR(50),
    active_yn BOOLEAN NOT NULL DEFAULT TRUE,
    archived_at TIMESTAMP,
    metadata_json JSONB,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP
);
EXCEPTION
    WHEN duplicate_table THEN NULL;
    WHEN unique_violation THEN NULL;
END $thermops_ct$;
CREATE INDEX IF NOT EXISTS ix_api_connector_op_source ON tb_api_connector_operation(data_source_id, active_yn);
DO $thermops_ct$
BEGIN
    CREATE TABLE IF NOT EXISTS tb_api_connector_param (
    param_id VARCHAR(50) PRIMARY KEY,
    operation_id VARCHAR(50) NOT NULL REFERENCES tb_api_connector_operation(operation_id) ON DELETE CASCADE,
    param_name VARCHAR(100) NOT NULL,
    display_name VARCHAR(200),
    param_location VARCHAR(20) NOT NULL DEFAULT 'QUERY',
    param_type VARCHAR(30) NOT NULL DEFAULT 'STRING',
    required_yn BOOLEAN NOT NULL DEFAULT FALSE,
    default_value TEXT,
    example_value TEXT,
    allowed_values_json JSONB,
    value_source VARCHAR(30) NOT NULL DEFAULT 'USER_INPUT',
    secret_key_ref VARCHAR(100),
    encode_yn BOOLEAN NOT NULL DEFAULT TRUE,
    sort_order INTEGER NOT NULL DEFAULT 0,
    active_yn BOOLEAN NOT NULL DEFAULT TRUE,
    metadata_json JSONB
);
EXCEPTION
    WHEN duplicate_table THEN NULL;
    WHEN unique_violation THEN NULL;
END $thermops_ct$;
CREATE INDEX IF NOT EXISTS ix_api_connector_param_op ON tb_api_connector_param(operation_id, sort_order);
DO $thermops_ct$
BEGIN
    CREATE TABLE IF NOT EXISTS tb_api_connector_credential (
    credential_id VARCHAR(50) PRIMARY KEY,
    data_source_id VARCHAR(50) NOT NULL REFERENCES tb_data_source(data_source_id) ON DELETE CASCADE,
    credential_name VARCHAR(200) NOT NULL DEFAULT 'default',
    credential_type VARCHAR(30) NOT NULL DEFAULT 'API_KEY',
    key_location VARCHAR(20) NOT NULL DEFAULT 'QUERY',
    key_name VARCHAR(100) NOT NULL DEFAULT 'serviceKey',
    secret_value_encrypted TEXT,
    secret_value_masked VARCHAR(200),
    encoding_policy VARCHAR(30) NOT NULL DEFAULT 'STORE_DECODED_ENCODE_ON_CALL',
    active_yn BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP
);
EXCEPTION
    WHEN duplicate_table THEN NULL;
    WHEN unique_violation THEN NULL;
END $thermops_ct$;
CREATE UNIQUE INDEX IF NOT EXISTS ux_api_connector_credential_source ON tb_api_connector_credential(data_source_id) WHERE active_yn = TRUE;
DO $thermops_ct$
BEGIN
    CREATE TABLE IF NOT EXISTS tb_api_connector_pagination (
    pagination_id VARCHAR(50) PRIMARY KEY,
    operation_id VARCHAR(50) NOT NULL UNIQUE REFERENCES tb_api_connector_operation(operation_id) ON DELETE CASCADE,
    pagination_type VARCHAR(30) NOT NULL DEFAULT 'NONE',
    page_param_name VARCHAR(100),
    size_param_name VARCHAR(100),
    page_start INTEGER NOT NULL DEFAULT 1,
    page_size INTEGER NOT NULL DEFAULT 100,
    max_pages INTEGER NOT NULL DEFAULT 1,
    total_count_path TEXT,
    next_link_path TEXT,
    stop_condition VARCHAR(50) NOT NULL DEFAULT 'EMPTY_ITEMS',
    active_yn BOOLEAN NOT NULL DEFAULT TRUE
);
EXCEPTION
    WHEN duplicate_table THEN NULL;
    WHEN unique_violation THEN NULL;
END $thermops_ct$;
DO $thermops_ct$
BEGIN
    CREATE TABLE IF NOT EXISTS tb_api_connector_call_log (
    call_log_id VARCHAR(50) PRIMARY KEY,
    operation_id VARCHAR(50) NOT NULL REFERENCES tb_api_connector_operation(operation_id),
    data_source_id VARCHAR(50) NOT NULL REFERENCES tb_data_source(data_source_id),
    called_at TIMESTAMP NOT NULL DEFAULT NOW(),
    called_by VARCHAR(100),
    request_url_masked TEXT,
    request_params_masked JSONB,
    http_status INTEGER,
    success_yn BOOLEAN NOT NULL DEFAULT FALSE,
    response_format VARCHAR(20),
    response_item_count INTEGER NOT NULL DEFAULT 0,
    duration_ms INTEGER,
    error_message TEXT,
    raw_response_snapshot_id VARCHAR(50),
    metadata_json JSONB
);
EXCEPTION
    WHEN duplicate_table THEN NULL;
    WHEN unique_violation THEN NULL;
END $thermops_ct$;
CREATE INDEX IF NOT EXISTS ix_api_connector_call_log_op ON tb_api_connector_call_log(operation_id, called_at DESC);
DO $thermops_ct$
BEGIN
    CREATE TABLE IF NOT EXISTS tb_api_connector_response_snapshot (
    snapshot_id VARCHAR(50) PRIMARY KEY,
    operation_id VARCHAR(50) NOT NULL REFERENCES tb_api_connector_operation(operation_id),
    call_log_id VARCHAR(50) REFERENCES tb_api_connector_call_log(call_log_id),
    captured_at TIMESTAMP NOT NULL DEFAULT NOW(),
    response_format VARCHAR(20) NOT NULL DEFAULT 'JSON',
    raw_response_text TEXT,
    normalized_items_json JSONB,
    item_count INTEGER NOT NULL DEFAULT 0,
    sample_only_yn BOOLEAN NOT NULL DEFAULT TRUE,
    metadata_json JSONB
);
EXCEPTION
    WHEN duplicate_table THEN NULL;
    WHEN unique_violation THEN NULL;
END $thermops_ct$;
CREATE INDEX IF NOT EXISTS ix_api_connector_snapshot_op ON tb_api_connector_response_snapshot(operation_id, captured_at DESC);
DO $thermops_ct$
BEGIN
    CREATE TABLE IF NOT EXISTS tb_api_connector_load_run (
    load_run_id VARCHAR(50) PRIMARY KEY,
    operation_id VARCHAR(50) NOT NULL REFERENCES tb_api_connector_operation(operation_id),
    data_source_id VARCHAR(50) NOT NULL REFERENCES tb_data_source(data_source_id),
    target_table VARCHAR(100),
    standard_dataset_id VARCHAR(50),
    started_at TIMESTAMP NOT NULL DEFAULT NOW(),
    finished_at TIMESTAMP,
    run_status VARCHAR(30) NOT NULL DEFAULT 'PENDING',
    request_params_snapshot JSONB,
    request_params_masked JSONB,
    inserted_count INTEGER NOT NULL DEFAULT 0,
    updated_count INTEGER NOT NULL DEFAULT 0,
    skipped_count INTEGER NOT NULL DEFAULT 0,
    error_count INTEGER NOT NULL DEFAULT 0,
    raw_snapshot_id VARCHAR(50),
    result_summary JSONB,
    error_message TEXT
);
EXCEPTION
    WHEN duplicate_table THEN NULL;
    WHEN unique_violation THEN NULL;
END $thermops_ct$;
CREATE INDEX IF NOT EXISTS ix_api_connector_load_run_op ON tb_api_connector_load_run(operation_id, started_at DESC);
-- R10-S1 Prediction Entity / Location / Weather Mapping

DO $thermops_ct$
BEGIN
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
EXCEPTION
    WHEN duplicate_table THEN NULL;
    WHEN unique_violation THEN NULL;
END $thermops_ct$;

CREATE INDEX IF NOT EXISTS ix_prediction_entity_code ON tb_prediction_entity(entity_code);
CREATE INDEX IF NOT EXISTS ix_prediction_entity_type ON tb_prediction_entity(entity_type);
CREATE INDEX IF NOT EXISTS ix_prediction_entity_active ON tb_prediction_entity(active_yn);

DO $thermops_ct$
BEGIN
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
EXCEPTION
    WHEN duplicate_table THEN NULL;
    WHEN unique_violation THEN NULL;
END $thermops_ct$;

CREATE INDEX IF NOT EXISTS ix_prediction_entity_location_entity
    ON tb_prediction_entity_location(entity_id, active_yn);

DO $thermops_ct$
BEGIN
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
EXCEPTION
    WHEN duplicate_table THEN NULL;
    WHEN unique_violation THEN NULL;
END $thermops_ct$;

CREATE INDEX IF NOT EXISTS ix_weather_forecast_grid_nx_ny
    ON tb_weather_forecast_grid(grid_system, nx, ny);

DO $thermops_ct$
BEGIN
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
EXCEPTION
    WHEN duplicate_table THEN NULL;
    WHEN unique_violation THEN NULL;
END $thermops_ct$;

CREATE INDEX IF NOT EXISTS ix_weather_obs_station_code ON tb_weather_observation_station(station_code);

DO $thermops_ct$
BEGIN
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
EXCEPTION
    WHEN duplicate_table THEN NULL;
    WHEN unique_violation THEN NULL;
END $thermops_ct$;

CREATE INDEX IF NOT EXISTS ix_pe_weather_mapping_entity
    ON tb_prediction_entity_weather_mapping(entity_id, active_yn);
CREATE INDEX IF NOT EXISTS ix_pe_weather_mapping_grid
    ON tb_prediction_entity_weather_mapping(forecast_grid_id);
CREATE INDEX IF NOT EXISTS ix_pe_weather_mapping_station
    ON tb_prediction_entity_weather_mapping(station_id);
-- R10-S2 External Code / Common Code Mapping

DO $thermops_ct$
BEGIN
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
EXCEPTION
    WHEN duplicate_table THEN NULL;
    WHEN unique_violation THEN NULL;
END $thermops_ct$;

CREATE INDEX IF NOT EXISTS ix_ext_code_mapping_lookup
    ON tb_external_code_mapping(source_system, external_code_group, external_code);
CREATE INDEX IF NOT EXISTS ix_ext_code_mapping_target
    ON tb_external_code_mapping(target_type, target_id);
CREATE INDEX IF NOT EXISTS ix_ext_code_mapping_status
    ON tb_external_code_mapping(mapping_status);
CREATE INDEX IF NOT EXISTS ix_ext_code_mapping_active
    ON tb_external_code_mapping(active_yn, mapping_status);

DO $thermops_ct$
BEGIN
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
EXCEPTION
    WHEN duplicate_table THEN NULL;
    WHEN unique_violation THEN NULL;
END $thermops_ct$;

CREATE INDEX IF NOT EXISTS ix_unmapped_ext_code_lookup
    ON tb_unmapped_external_code(source_system, external_code_group, external_code);
CREATE INDEX IF NOT EXISTS ix_unmapped_ext_code_review
    ON tb_unmapped_external_code(review_status);
CREATE INDEX IF NOT EXISTS ix_unmapped_ext_code_last_seen
    ON tb_unmapped_external_code(last_seen_at DESC);

-- R10-S5 Forecast On-demand Input Provider

DO $thermops_ct$
BEGIN
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
EXCEPTION
    WHEN duplicate_table THEN NULL;
    WHEN unique_violation THEN NULL;
END $thermops_ct$;

DO $thermops_ct$
BEGIN
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
EXCEPTION
    WHEN duplicate_table THEN NULL;
    WHEN unique_violation THEN NULL;
END $thermops_ct$;

DO $thermops_ct$
BEGIN
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
EXCEPTION
    WHEN duplicate_table THEN NULL;
    WHEN unique_violation THEN NULL;
END $thermops_ct$;

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

-- R10-S6 Data Load Scheduler

DO $thermops_ct$
BEGIN
    CREATE TABLE IF NOT EXISTS tb_data_load_schedule (
    schedule_id VARCHAR(50) PRIMARY KEY,
    schedule_name VARCHAR(200) NOT NULL,
    schedule_description TEXT,
    operation_id VARCHAR(50) NOT NULL,
    data_source_id VARCHAR(50),
    schedule_type VARCHAR(30) NOT NULL DEFAULT 'MANUAL',
    cron_expression VARCHAR(120),
    timezone VARCHAR(50) NOT NULL DEFAULT 'Asia/Seoul',
    start_at TIMESTAMP,
    end_at TIMESTAMP,
    active_yn BOOLEAN NOT NULL DEFAULT TRUE,
    run_policy VARCHAR(30) NOT NULL DEFAULT 'LOAD_RUN',
    load_window_type VARCHAR(30) NOT NULL DEFAULT 'NONE',
    window_offset_minutes INTEGER,
    runtime_params_template JSONB,
    max_pages_override INTEGER,
    retry_enabled_yn BOOLEAN NOT NULL DEFAULT FALSE,
    max_retry_count INTEGER NOT NULL DEFAULT 0,
    retry_interval_minutes INTEGER NOT NULL DEFAULT 10,
    on_failure_policy VARCHAR(30) NOT NULL DEFAULT 'STOP',
    last_run_at TIMESTAMP,
    last_success_at TIMESTAMP,
    last_failure_at TIMESTAMP,
    next_run_at TIMESTAMP,
    last_run_status VARCHAR(30),
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP,
    metadata_json JSONB
);
EXCEPTION
    WHEN duplicate_table THEN NULL;
    WHEN unique_violation THEN NULL;
END $thermops_ct$;

DO $thermops_ct$
BEGIN
    CREATE TABLE IF NOT EXISTS tb_data_load_schedule_run (
    schedule_run_id VARCHAR(50) PRIMARY KEY,
    schedule_id VARCHAR(50) NOT NULL,
    operation_id VARCHAR(50) NOT NULL,
    api_load_run_id VARCHAR(50),
    run_source VARCHAR(30) NOT NULL DEFAULT 'SCHEDULED_LOAD',
    scheduled_for TIMESTAMP,
    started_at TIMESTAMP NOT NULL,
    finished_at TIMESTAMP,
    run_status VARCHAR(30) NOT NULL DEFAULT 'RUNNING',
    attempt_no INTEGER NOT NULL DEFAULT 1,
    parent_schedule_run_id VARCHAR(50),
    runtime_params_snapshot JSONB,
    runtime_params_masked JSONB,
    request_summary JSONB,
    result_summary JSONB,
    inserted_count INTEGER NOT NULL DEFAULT 0,
    updated_count INTEGER NOT NULL DEFAULT 0,
    skipped_count INTEGER NOT NULL DEFAULT 0,
    error_count INTEGER NOT NULL DEFAULT 0,
    error_message TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    metadata_json JSONB
);
EXCEPTION
    WHEN duplicate_table THEN NULL;
    WHEN unique_violation THEN NULL;
END $thermops_ct$;

DO $thermops_ct$
BEGIN
    CREATE TABLE IF NOT EXISTS tb_data_load_schedule_event (
    event_id VARCHAR(50) PRIMARY KEY,
    schedule_id VARCHAR(50) NOT NULL,
    schedule_run_id VARCHAR(50),
    event_type VARCHAR(50) NOT NULL,
    event_message TEXT,
    event_payload_json JSONB,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);
EXCEPTION
    WHEN duplicate_table THEN NULL;
    WHEN unique_violation THEN NULL;
END $thermops_ct$;

CREATE INDEX IF NOT EXISTS ix_data_load_schedule_active_next
    ON tb_data_load_schedule(active_yn, next_run_at);
CREATE INDEX IF NOT EXISTS ix_data_load_schedule_operation
    ON tb_data_load_schedule(operation_id);
CREATE INDEX IF NOT EXISTS ix_data_load_schedule_run_schedule
    ON tb_data_load_schedule_run(schedule_id, started_at DESC);
CREATE INDEX IF NOT EXISTS ix_data_load_schedule_run_status
    ON tb_data_load_schedule_run(run_status);
CREATE INDEX IF NOT EXISTS ix_data_load_schedule_event_schedule
    ON tb_data_load_schedule_event(schedule_id, created_at DESC);

-- R10-S8 Upsert / Deduplicate
DO $thermops_ct$
BEGIN
    CREATE TABLE IF NOT EXISTS tb_api_connector_write_policy (
    write_policy_id VARCHAR(50) PRIMARY KEY,
    operation_id VARCHAR(50) NOT NULL REFERENCES tb_api_connector_operation(operation_id) ON DELETE CASCADE,
    target_table VARCHAR(100) NOT NULL,
    write_mode VARCHAR(30) NOT NULL DEFAULT 'INSERT_ONLY',
    conflict_key_columns_json JSONB,
    update_columns_json JSONB,
    exclude_update_columns_json JSONB,
    compare_columns_json JSONB,
    null_update_policy VARCHAR(30) NOT NULL DEFAULT 'KEEP_EXISTING',
    duplicate_within_batch_policy VARCHAR(30) NOT NULL DEFAULT 'KEEP_LAST',
    no_conflict_key_policy VARCHAR(30) NOT NULL DEFAULT 'WARN_INSERT_ONLY',
    active_yn BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP,
    metadata_json JSONB
);
EXCEPTION
    WHEN duplicate_table THEN NULL;
    WHEN unique_violation THEN NULL;
END $thermops_ct$;

CREATE UNIQUE INDEX IF NOT EXISTS ux_api_connector_write_policy_active
    ON tb_api_connector_write_policy(operation_id, target_table)
    WHERE active_yn = TRUE;

CREATE INDEX IF NOT EXISTS ix_api_connector_write_policy_op_target_active
    ON tb_api_connector_write_policy(operation_id, target_table, active_yn);

DO $thermops_ct$
BEGIN
    CREATE TABLE IF NOT EXISTS tb_api_connector_load_dedup_summary (
    summary_id VARCHAR(50) PRIMARY KEY,
    load_run_id VARCHAR(50) REFERENCES tb_api_connector_load_run(load_run_id) ON DELETE SET NULL,
    schedule_run_id VARCHAR(50) REFERENCES tb_data_load_schedule_run(schedule_run_id) ON DELETE SET NULL,
    operation_id VARCHAR(50) NOT NULL REFERENCES tb_api_connector_operation(operation_id) ON DELETE CASCADE,
    target_table VARCHAR(100),
    write_mode VARCHAR(30) NOT NULL DEFAULT 'INSERT_ONLY',
    input_row_count INTEGER NOT NULL DEFAULT 0,
    unique_input_row_count INTEGER NOT NULL DEFAULT 0,
    duplicate_within_batch_count INTEGER NOT NULL DEFAULT 0,
    existing_match_count INTEGER NOT NULL DEFAULT 0,
    inserted_count INTEGER NOT NULL DEFAULT 0,
    updated_count INTEGER NOT NULL DEFAULT 0,
    skipped_duplicate_count INTEGER NOT NULL DEFAULT 0,
    unchanged_count INTEGER NOT NULL DEFAULT 0,
    error_count INTEGER NOT NULL DEFAULT 0,
    conflict_key_columns_json JSONB,
    sample_conflicts_json JSONB,
    warnings_json JSONB,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    metadata_json JSONB
);
EXCEPTION
    WHEN duplicate_table THEN NULL;
    WHEN unique_violation THEN NULL;
END $thermops_ct$;

CREATE INDEX IF NOT EXISTS ix_api_connector_dedup_summary_load_run
    ON tb_api_connector_load_dedup_summary(load_run_id);

CREATE INDEX IF NOT EXISTS ix_api_connector_dedup_summary_op_created
    ON tb_api_connector_load_dedup_summary(operation_id, created_at DESC);

-- R10-S9 Alert / Notification
DO $thermops_ct$
BEGIN
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
EXCEPTION
    WHEN duplicate_table THEN NULL;
    WHEN unique_violation THEN NULL;
END $thermops_ct$;

DO $thermops_ct$
BEGIN
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
EXCEPTION
    WHEN duplicate_table THEN NULL;
    WHEN unique_violation THEN NULL;
END $thermops_ct$;

DO $thermops_ct$
BEGIN
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
EXCEPTION
    WHEN duplicate_table THEN NULL;
    WHEN unique_violation THEN NULL;
END $thermops_ct$;

CREATE INDEX IF NOT EXISTS ix_alert_rule_source_type_enabled
    ON tb_alert_rule(event_source, event_type, enabled_yn);

DO $thermops_ct$
BEGIN
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
EXCEPTION
    WHEN duplicate_table THEN NULL;
    WHEN unique_violation THEN NULL;
END $thermops_ct$;

CREATE INDEX IF NOT EXISTS ix_notification_event_source_type_occurred
    ON tb_notification_event(event_source, event_type, occurred_at DESC);

CREATE INDEX IF NOT EXISTS ix_notification_event_dedup_occurred
    ON tb_notification_event(dedup_key, occurred_at DESC);

DO $thermops_ct$
BEGIN
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
EXCEPTION
    WHEN duplicate_table THEN NULL;
    WHEN unique_violation THEN NULL;
END $thermops_ct$;

CREATE INDEX IF NOT EXISTS ix_incident_status_severity_last
    ON tb_incident(status, severity, last_occurred_at DESC);

CREATE INDEX IF NOT EXISTS ix_incident_dedup_status
    ON tb_incident(dedup_key, status);

DO $thermops_ct$
BEGIN
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
EXCEPTION
    WHEN duplicate_table THEN NULL;
    WHEN unique_violation THEN NULL;
END $thermops_ct$;

CREATE INDEX IF NOT EXISTS ix_notification_delivery_event
    ON tb_notification_delivery(event_id);

CREATE INDEX IF NOT EXISTS ix_notification_delivery_status_created
    ON tb_notification_delivery(delivery_status, created_at DESC);

-- R10-S10 Run Due Worker
DO $thermops_ct$
BEGIN
    CREATE TABLE IF NOT EXISTS tb_run_due_worker_instance (
    worker_instance_id VARCHAR(100) PRIMARY KEY,
    worker_name VARCHAR(200) NOT NULL,
    worker_mode VARCHAR(30) NOT NULL,
    host_name VARCHAR(200),
    process_id INTEGER,
    enabled_yn BOOLEAN NOT NULL DEFAULT TRUE,
    status VARCHAR(30) NOT NULL DEFAULT 'STARTING',
    poll_interval_seconds INTEGER NOT NULL DEFAULT 60,
    last_heartbeat_at TIMESTAMP,
    last_run_started_at TIMESTAMP,
    last_run_finished_at TIMESTAMP,
    last_run_status VARCHAR(30),
    consecutive_failure_count INTEGER NOT NULL DEFAULT 0,
    total_run_count INTEGER NOT NULL DEFAULT 0,
    total_success_count INTEGER NOT NULL DEFAULT 0,
    total_failure_count INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP,
    metadata_json JSONB
);
EXCEPTION
    WHEN duplicate_table THEN NULL;
    WHEN unique_violation THEN NULL;
END $thermops_ct$;

DO $thermops_ct$
BEGIN
    CREATE TABLE IF NOT EXISTS tb_run_due_worker_run (
    worker_run_id VARCHAR(50) PRIMARY KEY,
    worker_instance_id VARCHAR(100),
    worker_name VARCHAR(200),
    run_mode VARCHAR(30) NOT NULL,
    started_at TIMESTAMP NOT NULL,
    finished_at TIMESTAMP,
    run_status VARCHAR(30) NOT NULL DEFAULT 'RUNNING',
    due_schedule_count INTEGER NOT NULL DEFAULT 0,
    executed_schedule_count INTEGER NOT NULL DEFAULT 0,
    success_schedule_count INTEGER NOT NULL DEFAULT 0,
    failed_schedule_count INTEGER NOT NULL DEFAULT 0,
    skipped_schedule_count INTEGER NOT NULL DEFAULT 0,
    run_due_result_json JSONB,
    error_message TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    metadata_json JSONB
);
EXCEPTION
    WHEN duplicate_table THEN NULL;
    WHEN unique_violation THEN NULL;
END $thermops_ct$;

DO $thermops_ct$
BEGIN
    CREATE TABLE IF NOT EXISTS tb_run_due_worker_lock (
    lock_key VARCHAR(100) PRIMARY KEY,
    owner_instance_id VARCHAR(100) NOT NULL,
    acquired_at TIMESTAMP NOT NULL,
    expires_at TIMESTAMP NOT NULL,
    heartbeat_at TIMESTAMP NOT NULL,
    metadata_json JSONB
);
EXCEPTION
    WHEN duplicate_table THEN NULL;
    WHEN unique_violation THEN NULL;
END $thermops_ct$;

CREATE INDEX IF NOT EXISTS ix_run_due_worker_instance_status_hb
    ON tb_run_due_worker_instance(status, last_heartbeat_at);

CREATE INDEX IF NOT EXISTS ix_run_due_worker_run_instance_started
    ON tb_run_due_worker_run(worker_instance_id, started_at DESC);

CREATE INDEX IF NOT EXISTS ix_run_due_worker_run_status_started
    ON tb_run_due_worker_run(run_status, started_at DESC);

CREATE INDEX IF NOT EXISTS ix_run_due_worker_lock_expires
    ON tb_run_due_worker_lock(expires_at);

-- THERMOps schema init completion marker
-- apply_dev_migrations.py waits for this relation to avoid racing docker-entrypoint init.
DO $thermops_ct$
BEGIN
    CREATE TABLE IF NOT EXISTS tb_schema_init_ready (
        ready_yn BOOLEAN PRIMARY KEY DEFAULT TRUE,
        initialized_at TIMESTAMP NOT NULL DEFAULT NOW()
    );
EXCEPTION
    WHEN duplicate_table THEN NULL;
    WHEN unique_violation THEN NULL;
END $thermops_ct$;

INSERT INTO tb_schema_init_ready (ready_yn, initialized_at)
VALUES (TRUE, NOW())
ON CONFLICT (ready_yn) DO UPDATE SET initialized_at = EXCLUDED.initialized_at;
