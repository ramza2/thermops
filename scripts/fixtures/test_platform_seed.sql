-- THERMOps test platform seed (R9-S2-0) - NOT operational seed; loaded by scripts/test_fixtures.py

-- Sites & weather (CSV sample compatibility: SITE-001..005, WA-001..004)
INSERT INTO tb_site (site_id, site_name, site_type, active_yn) VALUES
('SITE-001', '중앙지사', 'BRANCH', 'Y'),
('SITE-002', '강남지사', 'BRANCH', 'Y'),
('SITE-003', '분당지사', 'BRANCH', 'Y'),
('SITE-004', '수원지사', 'BRANCH', 'Y'),
('SITE-005', '일산지사', 'BRANCH', 'Y')
ON CONFLICT (site_id) DO NOTHING;

INSERT INTO tb_weather_area (weather_area_id, area_name, latitude, longitude, provider) VALUES
('WA-001', '서울중앙', 37.5665, 126.9780, 'KMA'),
('WA-002', '경기남부', 37.2636, 127.0286, 'KMA'),
('WA-003', '경기서부', 37.4563, 126.7052, 'KMA'),
('WA-004', '경기북부', 37.6584, 126.8320, 'KMA')
ON CONFLICT (weather_area_id) DO NOTHING;

INSERT INTO tb_site_weather_mapping (site_id, weather_area_id, priority_no) VALUES
('SITE-001', 'WA-001', 1),
('SITE-002', 'WA-001', 1),
('SITE-003', 'WA-002', 1),
('SITE-004', 'WA-003', 1),
('SITE-005', 'WA-004', 1)
ON CONFLICT DO NOTHING;

-- Standard dataset types (test platform)
INSERT INTO tb_standard_dataset_type (
    dataset_type_id, dataset_type_code, dataset_type_name, description,
    domain, category, target_table,
    physical_table_yn, physical_table_exists_yn,
    build_supported_yn, recipe_supported_yn, mapping_supported_yn,
    status, owner, active_yn
) VALUES
('TEST-DST-HEAT', 'TEST_HEAT_DEMAND_ACTUAL', '열수요 실적 (테스트)', '지사별 열수요 실적 Fact 테이블',
 'HEAT_DEMAND', 'FACT', 'heat_demand_actual', 'Y', 'Y', 'Y', 'Y', 'Y', 'ACTIVE', 'TEST', 'Y'),
('TEST-DST-WEATHER', 'TEST_WEATHER_OBSERVATION', '기상 관측 (테스트)', '기상권역별 관측 Fact 테이블',
 'WEATHER', 'FACT', 'weather_observation', 'Y', 'Y', 'N', 'Y', 'Y', 'ACTIVE', 'TEST', 'Y'),
('TEST-DST-SITE-MASTER', 'TEST_SITE_MASTER', '지사/사업소 마스터 (테스트)', '지사·사업소 기준정보 마스터',
 'MASTER', 'MASTER', 'tb_site', 'Y', 'Y', 'N', 'N', 'Y', 'ACTIVE', 'TEST', 'Y'),
('TEST-DST-SWM', 'TEST_SITE_WEATHER_MAPPING', '지사-기상권역 매핑 (테스트)', '지사와 기상권역 연결 매핑',
 'MASTER', 'MAPPING', 'tb_site_weather_mapping', 'Y', 'Y', 'N', 'N', 'Y', 'ACTIVE', 'TEST', 'Y'),
('TEST-DST-COMMON-CODE', 'TEST_COMMON_CODE', '공통코드 (테스트)', '플랫폼 공통코드 마스터',
 'MASTER', 'CODE', 'tb_common_code', 'Y', 'Y', 'N', 'N', 'Y', 'ACTIVE', 'TEST', 'Y'),
('TEST-DST-FACILITY', 'TEST_FACILITY_MASTER', '설비 마스터 (테스트)', '설비 기준정보 (후속 단계)',
 'FACILITY', 'MASTER', 'tb_facility', 'Y', 'N', 'N', 'N', 'N', 'PLANNED', 'TEST', 'Y'),
('TEST-DST-FACILITY-SENSOR', 'TEST_FACILITY_SENSOR_OBSERVATION', '설비 센서 관측 (테스트)', '설비 센서 관측 Fact (후속 단계)',
 'FACILITY', 'SENSOR', 'tb_facility_sensor_observation', 'Y', 'N', 'N', 'N', 'N', 'PLANNED', 'TEST', 'Y'),
('TEST-DST-OPERATION-EVENT', 'TEST_OPERATION_EVENT', '운영 이벤트 (테스트)', '운영 이벤트/작업 이력 (후속 단계)',
 'OPERATION', 'EVENT', 'tb_operation_event', 'Y', 'N', 'N', 'N', 'N', 'PLANNED', 'TEST', 'Y')
ON CONFLICT (dataset_type_id) DO NOTHING;

INSERT INTO tb_standard_dataset_column (
    column_id, dataset_type_id, column_name, display_name, data_type,
    nullable_yn, required_yn, primary_key_yn, default_column_role, role_required_yn, sort_order, active_yn
) VALUES
('TEST-SDC-HEAT-SITE', 'TEST-DST-HEAT', 'site_id', '지사 ID', 'STRING', 'N', 'Y', 'N', 'ENTITY_KEY', 'Y', 1, 'Y'),
('TEST-SDC-HEAT-TIME', 'TEST-DST-HEAT', 'measured_at', '측정 시각', 'DATETIME', 'N', 'Y', 'N', 'TIME_KEY', 'Y', 2, 'Y'),
('TEST-SDC-HEAT-TGT', 'TEST-DST-HEAT', 'heat_demand', '열수요', 'NUMERIC', 'N', 'Y', 'N', 'TARGET', 'Y', 3, 'Y'),
('TEST-SDC-HEAT-SUP', 'TEST-DST-HEAT', 'supply_temp', '공급 온도', 'NUMERIC', 'Y', 'N', 'N', 'NUMERIC_INPUT', 'N', 4, 'Y'),
('TEST-SDC-WX-AREA', 'TEST-DST-WEATHER', 'weather_area_id', '기상권역 ID', 'STRING', 'N', 'Y', 'N', 'ENTITY_KEY', 'Y', 1, 'Y'),
('TEST-SDC-WX-TIME', 'TEST-DST-WEATHER', 'measured_at', '관측 시각', 'DATETIME', 'N', 'Y', 'N', 'TIME_KEY', 'Y', 2, 'Y'),
('TEST-SDC-WX-TYPE', 'TEST-DST-WEATHER', 'data_type', '관측 유형', 'STRING', 'Y', 'N', 'N', 'CATEGORICAL_INPUT', 'N', 3, 'Y'),
('TEST-SDC-WX-TEMP', 'TEST-DST-WEATHER', 'temperature', '기온', 'NUMERIC', 'Y', 'N', 'N', 'NUMERIC_INPUT', 'N', 4, 'Y'),
('TEST-SDC-WX-HUM', 'TEST-DST-WEATHER', 'humidity', '습도', 'NUMERIC', 'Y', 'N', 'N', 'NUMERIC_INPUT', 'N', 5, 'Y'),
('TEST-SDC-WX-RAIN', 'TEST-DST-WEATHER', 'rainfall', '강수량', 'NUMERIC', 'Y', 'N', 'N', 'NUMERIC_INPUT', 'N', 6, 'Y'),
('TEST-SDC-WX-WIND', 'TEST-DST-WEATHER', 'wind_speed', '풍속', 'NUMERIC', 'Y', 'N', 'N', 'NUMERIC_INPUT', 'N', 7, 'Y'),
('TEST-SDC-SITE-ID', 'TEST-DST-SITE-MASTER', 'site_id', '지사 ID', 'STRING', 'N', 'Y', 'Y', 'ENTITY_KEY', 'Y', 1, 'Y'),
('TEST-SDC-SITE-NAME', 'TEST-DST-SITE-MASTER', 'site_name', '지사명', 'STRING', 'Y', 'N', 'N', 'TEXT', 'N', 2, 'Y'),
('TEST-SDC-SITE-TYPE', 'TEST-DST-SITE-MASTER', 'site_type', '지사 유형', 'STRING', 'Y', 'N', 'N', 'CATEGORICAL_INPUT', 'N', 3, 'Y'),
('TEST-SDC-SITE-ACT', 'TEST-DST-SITE-MASTER', 'active_yn', '활성 여부', 'STRING', 'Y', 'N', 'N', 'BOOLEAN_INPUT', 'N', 4, 'Y'),
('TEST-SDC-SWM-SITE', 'TEST-DST-SWM', 'site_id', '지사 ID', 'STRING', 'N', 'Y', 'N', 'ENTITY_KEY', 'Y', 1, 'Y'),
('TEST-SDC-SWM-AREA', 'TEST-DST-SWM', 'weather_area_id', '기상권역 ID', 'STRING', 'N', 'Y', 'N', 'JOIN_KEY', 'Y', 2, 'Y'),
('TEST-SDC-SWM-ACT', 'TEST-DST-SWM', 'active_yn', '활성 여부', 'STRING', 'Y', 'N', 'N', 'BOOLEAN_INPUT', 'N', 3, 'Y'),
('TEST-SDC-CC-GROUP', 'TEST-DST-COMMON-CODE', 'code_group', '코드 그룹', 'STRING', 'N', 'Y', 'Y', 'CATEGORICAL_INPUT', 'Y', 1, 'Y'),
('TEST-SDC-CC-CODE', 'TEST-DST-COMMON-CODE', 'code', '코드', 'STRING', 'N', 'Y', 'Y', 'CATEGORICAL_INPUT', 'Y', 2, 'Y'),
('TEST-SDC-CC-NAME', 'TEST-DST-COMMON-CODE', 'code_name', '코드명', 'STRING', 'Y', 'N', 'N', 'TEXT', 'N', 3, 'Y'),
('TEST-SDC-CC-ACT', 'TEST-DST-COMMON-CODE', 'active_yn', '활성 여부', 'STRING', 'Y', 'N', 'N', 'BOOLEAN_INPUT', 'N', 4, 'Y'),
('TEST-SDC-FAC-ID', 'TEST-DST-FACILITY', 'facility_id', '설비 ID', 'STRING', 'N', 'Y', 'Y', 'ENTITY_KEY', 'Y', 1, 'Y'),
('TEST-SDC-FAC-NAME', 'TEST-DST-FACILITY', 'facility_name', '설비명', 'STRING', 'Y', 'N', 'N', 'TEXT', 'N', 2, 'Y'),
('TEST-SDC-FS-SITE', 'TEST-DST-FACILITY-SENSOR', 'site_id', '지사 ID', 'STRING', 'N', 'Y', 'N', 'ENTITY_KEY', 'Y', 1, 'Y'),
('TEST-SDC-FS-TIME', 'TEST-DST-FACILITY-SENSOR', 'measured_at', '측정 시각', 'DATETIME', 'N', 'Y', 'N', 'TIME_KEY', 'Y', 2, 'Y'),
('TEST-SDC-FS-VAL', 'TEST-DST-FACILITY-SENSOR', 'sensor_value', '센서값', 'NUMERIC', 'Y', 'N', 'N', 'MEASURE', 'N', 3, 'Y'),
('TEST-SDC-OE-SITE', 'TEST-DST-OPERATION-EVENT', 'site_id', '지사 ID', 'STRING', 'N', 'Y', 'N', 'ENTITY_KEY', 'Y', 1, 'Y'),
('TEST-SDC-OE-TIME', 'TEST-DST-OPERATION-EVENT', 'event_at', '이벤트 시각', 'DATETIME', 'N', 'Y', 'N', 'TIME_KEY', 'Y', 2, 'Y')
ON CONFLICT (column_id) DO NOTHING;

-- Calendar (2026-05-01 .. 2026-07-31)
INSERT INTO tb_calendar (calendar_date, day_of_week, is_weekend, is_holiday, holiday_name, season)
SELECT
  d::date,
  EXTRACT(DOW FROM d)::int,
  CASE WHEN EXTRACT(DOW FROM d) IN (0, 6) THEN 'Y' ELSE 'N' END,
  CASE WHEN d::date IN ('2026-05-05'::date, '2026-06-06'::date) THEN 'Y' ELSE 'N' END,
  CASE
    WHEN d::date = '2026-05-05'::date THEN '어린이날'
    WHEN d::date = '2026-06-06'::date THEN '현충일'
    ELSE NULL
  END,
  CASE
    WHEN EXTRACT(MONTH FROM d) IN (12, 1, 2) THEN 'WINTER'
    WHEN EXTRACT(MONTH FROM d) IN (6, 7, 8) THEN 'SUMMER'
    ELSE 'SHOULDER'
  END
FROM generate_series('2026-05-01'::date, '2026-07-31'::date, '1 day') AS d
ON CONFLICT (calendar_date) DO NOTHING;

-- Feature registry (TEST-FS-* sets)
INSERT INTO tb_feature (feature_id, feature_name, feature_group, feature_type, calc_expression, status) VALUES
('TEST-FEAT-TEMP', 'temperature', '기상', 'RAW', '외기온도(°C)', 'ACTIVE'),
('TEST-FEAT-HUM', 'humidity', '기상', 'RAW', '습도(%)', 'ACTIVE'),
('TEST-FEAT-RAIN', 'rainfall', '기상', 'RAW', '강수량', 'ACTIVE'),
('TEST-FEAT-WIND', 'wind_speed', '기상', 'RAW', '풍속', 'ACTIVE'),
('TEST-FEAT-MONTH', 'month', '시간', 'DERIVED', '관측 월', 'ACTIVE'),
('TEST-FEAT-HOUR', 'hour', '시간', 'DERIVED', '관측 시각', 'ACTIVE'),
('TEST-FEAT-DOW', 'day_of_week', '달력', 'DERIVED', '요일(0-6)', 'ACTIVE'),
('TEST-FEAT-WEEKEND', 'is_weekend', '달력', 'DERIVED', '주말 여부', 'ACTIVE'),
('TEST-FEAT-HOLIDAY', 'is_holiday', '달력', 'DERIVED', '공휴일 여부', 'ACTIVE'),
('TEST-FEAT-MSIN', 'month_sin', '시간', 'DERIVED', '월 주기 sin', 'ACTIVE'),
('TEST-FEAT-MCOS', 'month_cos', '시간', 'DERIVED', '월 주기 cos', 'ACTIVE'),
('TEST-FEAT-HSIN', 'hour_sin', '시간', 'DERIVED', '시간 주기 sin', 'ACTIVE'),
('TEST-FEAT-HCOS', 'hour_cos', '시간', 'DERIVED', '시간 주기 cos', 'ACTIVE'),
('TEST-FEAT-SWIN', 'season_winter', '달력', 'DERIVED', '겨울 시즌', 'ACTIVE'),
('TEST-FEAT-SSUM', 'season_summer', '달력', 'DERIVED', '여름 시즌', 'ACTIVE'),
('TEST-FEAT-TDIFF', 'temperature_diff_24h', '기상', 'DERIVED', '전일 온도차', 'ACTIVE'),
('TEST-FEAT-DL24', 'demand_lag_24h', '수요 이력', 'DERIVED', '24h lag', 'ACTIVE'),
('TEST-FEAT-DL168', 'demand_lag_168h', '수요 이력', 'DERIVED', '168h lag', 'ACTIVE'),
('TEST-FEAT-DMA24', 'demand_ma_24h', '수요 이력', 'DERIVED', '24h 이동평균', 'ACTIVE'),
('TEST-FEAT-DMA168', 'demand_ma_168h', '수요 이력', 'DERIVED', '168h 이동평균', 'ACTIVE'),
('TEST-FEAT-TL24', 'temperature_lag_24h', '기상', 'DERIVED', '기온 24h lag', 'ACTIVE'),
('TEST-FEAT-HL24', 'humidity_lag_24h', '기상', 'DERIVED', '습도 24h lag', 'ACTIVE'),
('TEST-FEAT-TMA24', 'temperature_ma_24h', '기상', 'DERIVED', '기온 24h MA', 'ACTIVE'),
('TEST-FEAT-HDD', 'heating_degree_days', '쾌적도', 'DERIVED', '난방도일', 'ACTIVE'),
('TEST-FEAT-CDD', 'cooling_degree_days', '쾌적도', 'DERIVED', '냉방도일', 'ACTIVE'),
('TEST-FEAT-COMF', 'comfort_distance', '쾌적도', 'DERIVED', '쾌적 거리', 'ACTIVE')
ON CONFLICT (feature_id) DO NOTHING;

-- Feature sets (same feature lists as legacy FS-TPL-*)
INSERT INTO tb_feature_set (feature_set_id, feature_set_name, target_domain, features, apply_site_scope, description) VALUES
('TEST-FS-MINIMAL', 'Minimal Weather Feature Set', 'HEAT_DEMAND',
 '["temperature","hour","day_of_week","month"]', 'ALL', '최소 기상·시간 Feature'),
('TEST-FS-LAG-ROLL', 'Lag/Rolling Feature Set', 'HEAT_DEMAND',
 '["temperature","humidity","rainfall","wind_speed","hour","day_of_week","month","is_weekend","is_holiday","demand_lag_24h","demand_lag_168h","demand_ma_24h","demand_ma_168h","temperature_lag_24h","humidity_lag_24h","temperature_ma_24h"]', 'ALL', 'Lag·이동평균 Feature'),
('TEST-FS-COMFORT', 'Comfort Index Feature Set', 'HEAT_DEMAND',
 '["temperature","humidity","rainfall","wind_speed","hour","day_of_week","month","is_weekend","is_holiday","demand_lag_24h","demand_lag_168h","demand_ma_24h","demand_ma_168h","temperature_lag_24h","humidity_lag_24h","temperature_ma_24h","heating_degree_days","cooling_degree_days","comfort_distance"]', 'ALL', '쾌적도 Feature'),
('TEST-FS-TWO-STAGE', 'Two-Stage Ready Feature Set', 'HEAT_DEMAND',
 '["month","day_of_week","hour","month_sin","month_cos","hour_sin","hour_cos","is_weekend","is_holiday","season_winter","season_summer","temperature","humidity","rainfall","wind_speed","temperature_diff_24h","demand_lag_24h","demand_lag_168h","demand_ma_24h","demand_ma_168h","temperature_lag_24h","humidity_lag_24h","temperature_ma_24h","heating_degree_days","cooling_degree_days","comfort_distance"]', 'ALL', '2-Stage 준비 풀 Feature'),
('FS-TPL-LAG-ROLL', 'Template Guard Feature Set', 'HEAT_DEMAND',
 '["temperature","humidity","hour","day_of_week","month","demand_lag_24h"]', 'ALL', 'FS-TPL-* 차단 테스트용 (fixture only)')
ON CONFLICT (feature_set_id) DO NOTHING;

-- Training configs
INSERT INTO tb_training_config (config_id, config_name, feature_set_id, algorithm, train_period_months, validation_period_months, hyperparams) VALUES
('TEST-TRC-LGBM', 'Lag/Rolling LightGBM 학습', 'TEST-FS-LAG-ROLL', 'lightgbm', 1, 1, '{"validation_ratio":0.2,"n_estimators":80,"learning_rate":0.05,"max_depth":6}'),
('TEST-TRC-CATBOOST', 'CatBoost 학습', 'TEST-FS-LAG-ROLL', 'catboost', 1, 1, '{"validation_ratio":0.2,"iterations":80,"learning_rate":0.05,"depth":6}'),
('TEST-TRC-TWO-STAGE', '2-Stage CatBoost 학습', 'TEST-FS-TWO-STAGE', 'two_stage_catboost', 1, 1, '{"validation_ratio":0.2,"iterations":80,"learning_rate":0.05,"depth":6}')
ON CONFLICT (config_id) DO NOTHING;

-- Pipeline templates (generic names; test IDs)
INSERT INTO tb_pipeline_template (
    template_id, template_code, template_name, description, pipeline_type,
    airflow_dag_id, template_version, node_schema_json, edge_schema_json,
    default_config_json, status, active_yn
) VALUES
(
    'TEST-PT-FULL', 'TEST_FULL_OPERATION_PIPELINE', 'Full operation pipeline',
    'End-to-end pipeline from ingestion through drift check', 'FULL_OPERATION',
    'thermops_full_pipeline_dag', '1.0',
    '{"nodes":[{"node_id":"DATA_SOURCE","label":"Data source","component_type":"DATA_SOURCE","required":true,"order":1,"config_fields":["data_source_id","mapping_id"]},{"node_id":"DATA_QUALITY","label":"Data quality","component_type":"DATA_QUALITY","required":true,"order":2,"config_fields":["quality_rule_set","fail_on_error"]},{"node_id":"FEATURE_BUILD","label":"Feature build","component_type":"FEATURE_BUILD","required":true,"order":3,"config_fields":["feature_set_id","dataset_type_id"]},{"node_id":"MODEL_TRAINING","label":"Model training","component_type":"MODEL_TRAINING","required":false,"order":4,"config_fields":["algorithm","config_id","train_start_date","train_end_date"]},{"node_id":"MODEL_SELECTION","label":"Model selection","component_type":"MODEL_SELECTION","required":false,"order":5,"config_fields":["model_name","registry_stage"]},{"node_id":"BATCH_PREDICTION","label":"Batch prediction","component_type":"BATCH_PREDICTION","required":true,"order":6,"config_fields":["site_ids","predict_start_date","predict_end_date"]},{"node_id":"PERFORMANCE_EVAL","label":"Performance eval","component_type":"PERFORMANCE_EVAL","required":true,"order":7,"config_fields":["metric","threshold"]},{"node_id":"DRIFT_CHECK","label":"Drift check","component_type":"DRIFT_CHECK","required":false,"order":8,"config_fields":["baseline_period","recent_period","drift_threshold"]}]}'::jsonb,
    '{"edges":[{"from":"DATA_SOURCE","to":"DATA_QUALITY"},{"from":"DATA_QUALITY","to":"FEATURE_BUILD"},{"from":"FEATURE_BUILD","to":"MODEL_TRAINING"},{"from":"MODEL_TRAINING","to":"MODEL_SELECTION"},{"from":"MODEL_SELECTION","to":"BATCH_PREDICTION"},{"from":"BATCH_PREDICTION","to":"PERFORMANCE_EVAL"},{"from":"PERFORMANCE_EVAL","to":"DRIFT_CHECK"}]}'::jsonb,
    '{"node_config":{"DATA_QUALITY":{"fail_on_error":false},"PERFORMANCE_EVAL":{"metric":"MAPE"}}}'::jsonb,
    'ACTIVE', 'Y'
),
(
    'TEST-PT-FEATURE-BUILD', 'TEST_FEATURE_BUILD_PIPELINE', 'Feature build pipeline',
    'Data source through feature build and quality validation', 'FEATURE_BUILD',
    'feature_build_dag', '1.0',
    '{"nodes":[{"node_id":"DATA_SOURCE","label":"Data source","component_type":"DATA_SOURCE","required":true,"order":1,"config_fields":["data_source_id"]},{"node_id":"DATA_MAPPING","label":"Data mapping","component_type":"DATA_MAPPING","required":true,"order":2,"config_fields":["mapping_id"]},{"node_id":"STANDARD_DATASET","label":"Standard dataset","component_type":"STANDARD_DATASET","required":true,"order":3,"config_fields":["dataset_type_id"]},{"node_id":"FEATURE_SET","label":"Feature set","component_type":"FEATURE_SET","required":true,"order":4,"config_fields":["feature_set_id"]},{"node_id":"FEATURE_BUILD","label":"Feature build","component_type":"FEATURE_BUILD","required":true,"order":5,"config_fields":["feature_set_id"]},{"node_id":"FEATURE_QUALITY","label":"Feature quality","component_type":"FEATURE_QUALITY","required":false,"order":6,"config_fields":["feature_set_id"]}]}'::jsonb,
    '{"edges":[{"from":"DATA_SOURCE","to":"DATA_MAPPING"},{"from":"DATA_MAPPING","to":"STANDARD_DATASET"},{"from":"STANDARD_DATASET","to":"FEATURE_SET"},{"from":"FEATURE_SET","to":"FEATURE_BUILD"},{"from":"FEATURE_BUILD","to":"FEATURE_QUALITY"}]}'::jsonb,
    NULL, 'ACTIVE', 'Y'
),
(
    'TEST-PT-BATCH', 'TEST_BATCH_PREDICTION_PIPELINE', 'Batch prediction pipeline',
    'Model selection through prediction, evaluation, and monitoring', 'BATCH_PREDICTION',
    'batch_prediction_dag', '1.0',
    '{"nodes":[{"node_id":"MODEL_SELECTION","label":"Model selection","component_type":"MODEL_SELECTION","required":true,"order":1,"config_fields":["model_name","registry_stage"]},{"node_id":"FEATURE_SET","label":"Feature set","component_type":"FEATURE_SET","required":true,"order":2,"config_fields":["feature_set_id"]},{"node_id":"BATCH_PREDICTION","label":"Batch prediction","component_type":"BATCH_PREDICTION","required":true,"order":3,"config_fields":["site_ids","predict_start_date","predict_end_date"]},{"node_id":"PERFORMANCE_EVAL","label":"Performance eval","component_type":"PERFORMANCE_EVAL","required":true,"order":4,"config_fields":["metric","threshold"]},{"node_id":"MONITORING","label":"Monitoring","component_type":"MONITORING","required":false,"order":5,"config_fields":["model_name"]}]}'::jsonb,
    '{"edges":[{"from":"MODEL_SELECTION","to":"FEATURE_SET"},{"from":"FEATURE_SET","to":"BATCH_PREDICTION"},{"from":"BATCH_PREDICTION","to":"PERFORMANCE_EVAL"},{"from":"PERFORMANCE_EVAL","to":"MONITORING"}]}'::jsonb,
    NULL, 'ACTIVE', 'Y'
),
(
    'TEST-PT-RETRAINING', 'TEST_RETRAINING_PIPELINE', 'Retraining pipeline',
    'Drift check through retraining and model registry (planned)', 'RETRAINING',
    'retraining_dag', '1.0',
    '{"nodes":[{"node_id":"DRIFT_CHECK","label":"Drift check","component_type":"DRIFT_CHECK","required":true,"order":1,"config_fields":["drift_threshold"]},{"node_id":"RETRAINING_CANDIDATE","label":"Retraining candidate","component_type":"RETRAINING_CANDIDATE","required":true,"order":2,"config_fields":["candidate_policy"]},{"node_id":"APPROVAL","label":"Approval","component_type":"APPROVAL","required":true,"order":3,"config_fields":["approval_required"]},{"node_id":"MODEL_TRAINING","label":"Model training","component_type":"MODEL_TRAINING","required":true,"order":4,"config_fields":["config_id","algorithm"]},{"node_id":"MODEL_REGISTRY","label":"Model registry","component_type":"MODEL_REGISTRY","required":true,"order":5,"config_fields":["registry_stage"]}]}'::jsonb,
    '{"edges":[{"from":"DRIFT_CHECK","to":"RETRAINING_CANDIDATE"},{"from":"RETRAINING_CANDIDATE","to":"APPROVAL"},{"from":"APPROVAL","to":"MODEL_TRAINING"},{"from":"MODEL_TRAINING","to":"MODEL_REGISTRY"}]}'::jsonb,
    NULL, 'PLANNED', 'Y'
)
ON CONFLICT (template_id) DO NOTHING;
