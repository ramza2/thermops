-- THERMOps Sample Seed Data

-- Sites (5 branches)
INSERT INTO tb_site (site_id, site_name, site_type, active_yn) VALUES
('SITE-001', '중앙지사', 'BRANCH', 'Y'),
('SITE-002', '강남지사', 'BRANCH', 'Y'),
('SITE-003', '분당지사', 'BRANCH', 'Y'),
('SITE-004', '고양지사', 'BRANCH', 'Y'),
('SITE-005', '대전지사', 'BRANCH', 'Y')
ON CONFLICT DO NOTHING;

-- Weather areas
INSERT INTO tb_weather_area (weather_area_id, area_name, latitude, longitude, provider) VALUES
('WA-001', '서울중앙', 37.5665, 126.9780, 'KMA'),
('WA-002', '경기남부', 37.2636, 127.0286, 'KMA'),
('WA-003', '경기북부', 37.6584, 126.8320, 'KMA'),
('WA-004', '대전권', 36.3504, 127.3845, 'KMA')
ON CONFLICT DO NOTHING;

INSERT INTO tb_site_weather_mapping (site_id, weather_area_id, priority_no) VALUES
('SITE-001', 'WA-001', 1),
('SITE-002', 'WA-001', 1),
('SITE-003', 'WA-002', 1),
('SITE-004', 'WA-003', 1),
('SITE-005', 'WA-004', 1)
ON CONFLICT DO NOTHING;

-- Common codes
INSERT INTO tb_common_code (code_group, code, code_name, sort_order) VALUES
('SOURCE_TYPE', 'CSV', 'CSV/파일', 1),
('SOURCE_TYPE', 'DB', 'DB 연계', 2),
('SOURCE_TYPE', 'API', 'API 연계', 3),
('MODEL_STAGE', 'CANDIDATE', '후보 모델', 1),
('MODEL_STAGE', 'CHAMPION', '운영 모델', 2),
('MODEL_STAGE', 'ARCHIVED', '보관 모델', 3),
('RUN_STATUS', 'READY', '대기', 1),
('RUN_STATUS', 'RUNNING', '실행중', 2),
('RUN_STATUS', 'SUCCESS', '성공', 3),
('RUN_STATUS', 'FAILED', '실패', 4),
('PREDICTION_HORIZON', 'D_PLUS_1', '익일 예측', 1),
('PREDICTION_HORIZON', 'D_PLUS_7', '7일 예측', 2),
('DRIFT_STATUS', 'NORMAL', '정상', 1),
('DRIFT_STATUS', 'WARNING', '주의', 2),
('DRIFT_STATUS', 'DRIFT', '드리프트 감지', 3)
ON CONFLICT DO NOTHING;

-- Data sources
INSERT INTO tb_data_source (data_source_id, source_name, source_type, source_category, connection_ref, connection_info, load_cycle, active_yn, last_loaded_at) VALUES
('DS-000001', '열수요 실적 DB', 'DB', 'HEAT', 'heat_demand_conn', '{"db_type":"postgresql","host":"10.0.0.10","database":"heat_ops","table":"tb_heat_demand_raw"}', 'HOURLY', 'Y', '2026-06-24 02:00:00'),
('DS-000002', '기상 API', 'API', 'WEATHER', 'kma_weather_api', '{"endpoint":"https://api.weather.example/v1","auth":"api_key"}', 'HOURLY', 'Y', '2026-06-24 01:30:00'),
('DS-000003', '달력 CSV', 'CSV', 'CALENDAR', '/data/calendar_2026.csv', '{"path":"/data/calendar_2026.csv"}', 'DAILY', 'Y', '2026-06-01 00:00:00'),
('DS-000004', '운영 로그 DB', 'DB', 'OPERATION', 'operation_conn', '{"db_type":"postgresql","host":"10.0.0.11","table":"tb_supply_log"}', 'DAILY', 'Y', '2026-06-23 22:00:00')
ON CONFLICT DO NOTHING;

-- Data mappings
INSERT INTO tb_data_mapping (mapping_id, source_id, mapping_name, target_table, columns) VALUES
('MAP-000001', 'DS-000001', '열수요 실적 표준 매핑', 'heat_demand_actual', '[
  {"source_column":"BRANCH_CD","target_column":"site_id","required_yn":true},
  {"source_column":"MEASURE_DTM","target_column":"measured_at","transform_rule":"to_datetime(YYYYMMDDHH24MI)","required_yn":true},
  {"source_column":"DEMAND_VAL","target_column":"heat_demand","transform_rule":"unit:Gcal","required_yn":true}
]')
ON CONFLICT DO NOTHING;

-- Features
INSERT INTO tb_feature (feature_id, feature_name, feature_group, feature_type, calc_expression, status) VALUES
('FEAT-001', 'lag_24h_demand', '열수요 이력', 'DERIVED', '24시간 전 수요', 'ACTIVE'),
('FEAT-002', 'lag_168h_demand', '열수요 이력', 'DERIVED', '168시간 전 수요', 'ACTIVE'),
('FEAT-003', 'temperature', '기상', 'RAW', '외기온도(°C)', 'ACTIVE'),
('FEAT-004', 'humidity', '기상', 'RAW', '습도(%)', 'ACTIVE'),
('FEAT-005', 'hour_of_day', '달력', 'DERIVED', '시간대(0-23)', 'ACTIVE'),
('FEAT-006', 'day_of_week', '달력', 'DERIVED', '요일(0-6)', 'ACTIVE'),
('FEAT-007', 'supply_temp', '운영', 'RAW', '공급온도(°C)', 'ACTIVE'),
('FEAT-008', 'is_holiday', '달력', 'DERIVED', '공휴일 여부', 'INACTIVE')
ON CONFLICT DO NOTHING;

-- Feature sets
INSERT INTO tb_feature_set (feature_set_id, feature_set_name, target_domain, features, apply_site_scope, description) VALUES
('FS-000001', '기본 열수요 예측 Feature Set', 'HEAT_DEMAND', '["temperature","humidity","day_of_week","is_holiday","lag_24h","lag_168h","rolling_mean_24h"]', 'ALL', '기상, 달력, 과거 수요 기반 기본 입력값 구성')
ON CONFLICT DO NOTHING;

-- Training config
INSERT INTO tb_training_config (config_id, config_name, feature_set_id, algorithm, train_period_months, validation_period_months, hyperparams) VALUES
('TRC-000001', 'LightGBM 기본 학습 설정', 'FS-000001', 'LightGBM', 24, 3, '{"n_estimators":100,"learning_rate":0.05,"max_depth":6}'),
('TRC-TPL-LAG-ROLL', 'Lag/Rolling LightGBM 학습', 'FS-TPL-LAG-ROLL', 'lightgbm', 1, 1, '{"validation_ratio":0.2,"n_estimators":80,"learning_rate":0.05,"max_depth":6}'),
('TRC-TPL-BASELINE', 'Baseline Lag24h 학습', 'FS-TPL-LAG-ROLL', 'baseline', 1, 1, '{"validation_ratio":0.2}')
ON CONFLICT DO NOTHING;

-- Dataset version
INSERT INTO tb_dataset_version (dataset_version_id, dataset_type, base_start_at, base_end_at, record_count, created_by) VALUES
('DSV-20260601-TRAIN', 'TRAIN', '2024-01-01', '2026-03-31', 87600, 'pipeline'),
('DSV-20260601-VAL', 'VALIDATION', '2026-04-01', '2026-05-31', 1464, 'pipeline')
ON CONFLICT DO NOTHING;

-- Model experiment & versions
INSERT INTO tb_model_experiment (experiment_id, mlflow_run_id, dataset_version_id, algorithm, parameter_json, metric_json, trained_at, created_by) VALUES
('EXP-001', 'run_abc123', 'DSV-20260601-TRAIN', 'LightGBM', '{"n_estimators":100}', '{"mae":15.23,"rmse":21.87,"mape":4.82}', '2026-06-20 10:27:14', 'admin'),
('EXP-002', 'run_def456', 'DSV-20260601-TRAIN', 'XGBoost', '{"n_estimators":100}', '{"mae":18.1,"rmse":25.4,"mape":5.23}', '2026-06-18 14:00:00', 'admin')
ON CONFLICT DO NOTHING;

INSERT INTO tb_model_version (model_version_id, model_name, version_no, experiment_id, mlflow_model_uri, model_stage, metric_summary_json, registered_at) VALUES
('MV-heat_demand_lgbm-12', 'heat_demand_lgbm', '12', 'EXP-001', 'models:/heat_demand_lgbm/12', 'CHAMPION', '{"mae":15.23,"rmse":21.87,"mape":4.82}', '2026-06-20 10:30:00'),
('MV-heat_demand_lgbm-10', 'heat_demand_lgbm', '10', 'EXP-001', 'models:/heat_demand_lgbm/10', 'ARCHIVED', '{"mae":16.5,"rmse":23.1,"mape":5.1}', '2026-05-15 09:00:00'),
('MV-heat_demand_xgb-07', 'heat_demand_xgb', '07', 'EXP-002', 'models:/heat_demand_xgb/07', 'CANDIDATE', '{"mae":18.1,"rmse":25.4,"mape":5.23}', '2026-06-18 14:30:00')
ON CONFLICT DO NOTHING;

-- Pipeline runs
INSERT INTO tb_pipeline_run (pipeline_run_id, pipeline_id, pipeline_name, pipeline_type, orchestrator_run_id, run_status, started_at, finished_at, message) VALUES
('AIRFLOW-RUN-000001', 'batch_prediction_dag', 'batch_prediction_dag', 'PREDICTION', 'dag_run_001', 'SUCCESS', '2026-06-24 05:00:00', '2026-06-24 05:15:00', '정상 완료'),
('AIRFLOW-RUN-000002', 'model_training_dag', 'model_training_dag', 'TRAINING', 'dag_run_002', 'RUNNING', '2026-06-24 10:00:00', NULL, '학습 진행 중'),
('AIRFLOW-RUN-000003', 'monitoring_dag', 'monitoring_dag', 'MONITORING', 'dag_run_003', 'FAILED', '2026-06-24 08:00:00', '2026-06-24 08:03:00', '드리프트 리포트 생성 실패'),
('AIRFLOW-RUN-000004', 'data_ingestion_dag', 'data_ingestion_dag', 'INGESTION', 'dag_run_004', 'SUCCESS', '2026-06-23 23:00:00', '2026-06-23 23:08:00', '열수요/기상 적재 완료'),
('AIRFLOW-RUN-000005', 'feature_build_dag', 'feature_build_dag', 'FEATURE', 'dag_run_005', 'SUCCESS', '2026-06-23 22:00:00', '2026-06-23 22:12:00', 'Feature 생성 완료')
ON CONFLICT DO NOTHING;

-- Training jobs
INSERT INTO tb_training_job (job_id, config_id, pipeline_run_id, status, site_ids, train_start_at, train_end_at, validation_start_at, validation_end_at, mlflow_run_id, registered_model_name, registered_model_version, metrics, started_at, ended_at) VALUES
('TRJ-20260624-000001', 'TRC-000001', 'AIRFLOW-RUN-000002', 'RUNNING', '["SITE-001","SITE-002"]', '2024-01-01', '2026-03-31', '2026-04-01', '2026-05-31', NULL, NULL, NULL, NULL, '2026-06-24 10:00:00', NULL),
('TRJ-20260620-000001', 'TRC-000001', 'AIRFLOW-RUN-000001', 'SUCCESS', '["SITE-001"]', '2024-01-01', '2026-03-31', '2026-04-01', '2026-05-31', 'run_abc123', 'heat_demand_lgbm', '12', '{"mae":15.23,"rmse":21.87,"mape":4.82}', '2026-06-20 10:00:00', '2026-06-20 10:27:14')
ON CONFLICT DO NOTHING;

-- Prediction job & results
INSERT INTO tb_prediction_job (prediction_job_id, pipeline_run_id, model_version_id, prediction_horizon, target_start_at, target_end_at, site_ids, job_status, created_at, finished_at) VALUES
('PRJ-20260624-000001', 'AIRFLOW-RUN-000001', 'MV-heat_demand_lgbm-12', 'D_PLUS_1', '2026-06-25 00:00:00', '2026-06-26 00:00:00', '["SITE-001"]', 'SUCCESS', '2026-06-24 05:00:00', '2026-06-24 05:15:00')
ON CONFLICT DO NOTHING;

-- Sample heat demand (24 hours for SITE-001)
INSERT INTO tb_heat_demand_actual (site_id, measured_at, heat_demand, supply_temp, return_temp, quality_flag, source_system)
SELECT 'SITE-001', ts, 120 + 60 * sin(extract(hour from ts)::float / 24 * 2 * pi()) + random() * 10,
       85 + random() * 5, 55 + random() * 3, 'NORMAL', 'HEAT_OPS'
FROM generate_series('2026-06-23 00:00:00'::timestamp, '2026-06-24 23:00:00'::timestamp, '1 hour') AS ts
ON CONFLICT DO NOTHING;

-- Sample predictions
INSERT INTO tb_heat_demand_prediction (prediction_job_id, site_id, target_at, predicted_demand, model_version_id)
SELECT 'PRJ-20260624-000001', 'SITE-001', ts, 118 + 55 * sin(extract(hour from ts)::float / 24 * 2 * pi()), 'MV-heat_demand_lgbm-12'
FROM generate_series('2026-06-25 00:00:00'::timestamp, '2026-06-25 23:00:00'::timestamp, '1 hour') AS ts
ON CONFLICT DO NOTHING;

-- Performance metrics
INSERT INTO tb_model_performance_metric (site_id, model_version_id, eval_start_at, eval_end_at, mae, rmse, mape, sample_count) VALUES
('SITE-001', 'MV-heat_demand_lgbm-12', '2026-06-01', '2026-06-23', 14.2, 20.6, 4.71, 552),
('SITE-002', 'MV-heat_demand_lgbm-12', '2026-06-01', '2026-06-23', 18.1, 25.4, 5.23, 552),
('SITE-003', 'MV-heat_demand_lgbm-12', '2026-06-01', '2026-06-23', 12.8, 18.9, 3.95, 552),
('SITE-004', 'MV-heat_demand_lgbm-12', '2026-06-01', '2026-06-23', 19.5, 27.2, 6.12, 552),
('SITE-005', 'MV-heat_demand_lgbm-12', '2026-06-01', '2026-06-23', 16.3, 22.8, 5.05, 552)
ON CONFLICT DO NOTHING;

-- Drift reports
INSERT INTO tb_drift_report (drift_report_id, dataset_version_id, model_version_id, base_period, current_period, drift_status, drift_score_json) VALUES
('DRIFT-20260624-001', 'DSV-20260601-TRAIN', 'MV-heat_demand_lgbm-12', '2024-01 ~ 2026-03', '2026-06-01 ~ 2026-06-23', 'WARNING', '{"temperature":0.412,"lag_24h_demand":0.287,"humidity":0.198}'),
('DRIFT-20260623-001', 'DSV-20260601-TRAIN', 'MV-heat_demand_lgbm-12', '2024-01 ~ 2026-03', '2026-05-01 ~ 2026-05-31', 'NORMAL', '{"temperature":0.156,"lag_24h_demand":0.112}')
ON CONFLICT DO NOTHING;

-- Retraining candidates
INSERT INTO tb_retraining_candidate (candidate_id, reason, model_name, model_version, site_id, risk_level, status) VALUES
('RTC-001', 'MAPE 임계치 초과 (6.2%)', 'heat_demand_lgbm', '12', 'SITE-002', 'HIGH', 'REVIEW'),
('RTC-002', '드리프트 감지 (temperature)', 'heat_demand_lgbm', '12', NULL, 'MEDIUM', 'REVIEW'),
('RTC-003', 'MAPE 임계치 초과 (6.8%)', 'heat_demand_xgb', '07', 'SITE-004', 'HIGH', 'REQUESTED')
ON CONFLICT DO NOTHING;

-- Data quality runs
INSERT INTO tb_data_quality_run (run_id, source_id, check_type, run_status, result_summary, started_at, finished_at) VALUES
('DQR-20260624-001', 'DS-000001', 'FULL', 'SUCCESS', '{"missing_rate":0.02,"duplicate_count":0,"outlier_count":3}', '2026-06-24 02:05:00', '2026-06-24 02:08:00'),
('DQR-20260624-002', 'DS-000002', 'FULL', 'SUCCESS', '{"missing_rate":0.01,"duplicate_count":0,"outlier_count":0}', '2026-06-24 01:35:00', '2026-06-24 01:37:00'),
('DQR-20260623-001', 'DS-000004', 'FULL', 'FAILED', '{"missing_rate":0.12,"errors":["connection timeout"]}', '2026-06-23 22:05:00', '2026-06-23 22:10:00')
ON CONFLICT DO NOTHING;

-- Weather sample
INSERT INTO tb_weather_observation (weather_area_id, measured_at, data_type, temperature, humidity, wind_speed)
SELECT 'WA-001', ts, 'OBSERVED', -5 + 15 * sin(extract(hour from ts)::float / 24 * 2 * pi()) + random() * 3,
       50 + random() * 30, 2 + random() * 5
FROM generate_series('2026-06-23 00:00:00'::timestamp, '2026-06-24 23:00:00'::timestamp, '1 hour') AS ts
ON CONFLICT DO NOTHING;

-- System config
INSERT INTO tb_system_config (config_key, config_name, config_value, config_type, scope, description, editable_yn) VALUES
('default_model_name', '기본 모델명', 'heat_demand_lightgbm', 'STRING', 'GLOBAL', 'Champion 미지정 시 사용할 기본 모델명', 'Y'),
('mape_warning_threshold', 'MAPE 경고 임계치', '8.0', 'NUMBER', 'GLOBAL', '운영 MAPE 경고 알림 임계치(%)', 'Y'),
('drift_warning_threshold', '드리프트 경고 임계치', '0.40', 'NUMBER', 'GLOBAL', 'Feature 드리프트 경고 점수 임계치', 'Y'),
('retraining_mape_threshold', '재학습 MAPE 임계치', '10.0', 'NUMBER', 'GLOBAL', '재학습 후보 산출 MAPE 임계치(%)', 'Y'),
('batch_prediction_default_horizon', '배치 예측 기본 범위', '24', 'NUMBER', 'GLOBAL', '배치 예측 기본 시간 범위(시간)', 'Y'),
('system_version', '시스템 버전', '0.1.0', 'STRING', 'GLOBAL', 'THERMOps 릴리스 버전', 'N')
ON CONFLICT (config_key) DO NOTHING;

-- CSV sample data sources (실제 파일 적재 1단계)
INSERT INTO tb_data_source (data_source_id, source_name, source_type, source_category, connection_ref, connection_info, load_cycle, active_yn) VALUES
('DS-CSV-001', '열수요 CSV 샘플', 'CSV', 'HEAT_DEMAND', 'heat_demand_sample.csv',
 '{"file_path":"data/samples/heat_demand_sample.csv","encoding":"utf-8","delimiter":","}', 'HOURLY', 'Y'),
('DS-CSV-002', '기상 CSV 샘플', 'CSV', 'WEATHER', 'weather_observation_sample.csv',
 '{"file_path":"data/samples/weather_observation_sample.csv","encoding":"utf-8","delimiter":","}', 'HOURLY', 'Y')
ON CONFLICT DO NOTHING;

INSERT INTO tb_data_mapping (mapping_id, source_id, mapping_name, target_table, columns) VALUES
('MAP-CSV-001', 'DS-CSV-001', '열수요 CSV 표준 매핑', 'heat_demand_actual', '[
  {"source_column":"site_id","target_column":"site_id","required_yn":true},
  {"source_column":"measured_at","target_column":"measured_at","required_yn":true},
  {"source_column":"heat_demand","target_column":"heat_demand","required_yn":true},
  {"source_column":"supply_temp","target_column":"supply_temp","required_yn":false}
]'),
('MAP-CSV-002', 'DS-CSV-002', '기상 CSV 표준 매핑', 'weather_observation', '[
  {"source_column":"weather_area_id","target_column":"weather_area_id","required_yn":true},
  {"source_column":"measured_at","target_column":"measured_at","required_yn":true},
  {"source_column":"data_type","target_column":"data_type","required_yn":false},
  {"source_column":"temperature","target_column":"temperature","required_yn":false},
  {"source_column":"humidity","target_column":"humidity","required_yn":false},
  {"source_column":"rainfall","target_column":"rainfall","required_yn":false},
  {"source_column":"wind_speed","target_column":"wind_speed","required_yn":false}
]')
ON CONFLICT DO NOTHING;

-- Calendar (샘플 CSV 기간 + 여유)
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

-- Feature registry (P0-3)
INSERT INTO tb_feature (feature_id, feature_name, feature_group, feature_type, calc_expression, status) VALUES
('FEAT-101', 'month', '시간', 'DERIVED', '관측 월', 'ACTIVE'),
('FEAT-102', 'hour', '시간', 'DERIVED', '관측 시각', 'ACTIVE'),
('FEAT-103', 'month_sin', '시간', 'DERIVED', '월 주기 sin', 'ACTIVE'),
('FEAT-104', 'month_cos', '시간', 'DERIVED', '월 주기 cos', 'ACTIVE'),
('FEAT-105', 'hour_sin', '시간', 'DERIVED', '시간 주기 sin', 'ACTIVE'),
('FEAT-106', 'hour_cos', '시간', 'DERIVED', '시간 주기 cos', 'ACTIVE'),
('FEAT-107', 'is_weekend', '달력', 'DERIVED', '주말 여부', 'ACTIVE'),
('FEAT-108', 'season_winter', '달력', 'DERIVED', '겨울 시즌', 'ACTIVE'),
('FEAT-109', 'season_summer', '달력', 'DERIVED', '여름 시즌', 'ACTIVE'),
('FEAT-110', 'rainfall', '기상', 'RAW', '강수량', 'ACTIVE'),
('FEAT-111', 'wind_speed', '기상', 'RAW', '풍속', 'ACTIVE'),
('FEAT-112', 'temperature_diff_24h', '기상', 'DERIVED', '전일 온도차', 'ACTIVE'),
('FEAT-113', 'demand_lag_24h', '열수요 이력', 'DERIVED', '24h lag', 'ACTIVE'),
('FEAT-114', 'demand_lag_168h', '열수요 이력', 'DERIVED', '168h lag', 'ACTIVE'),
('FEAT-115', 'demand_ma_24h', '열수요 이력', 'DERIVED', '24h 이동평균', 'ACTIVE'),
('FEAT-116', 'demand_ma_168h', '열수요 이력', 'DERIVED', '168h 이동평균', 'ACTIVE'),
('FEAT-117', 'temperature_lag_24h', '기상', 'DERIVED', '기온 24h lag', 'ACTIVE'),
('FEAT-118', 'humidity_lag_24h', '기상', 'DERIVED', '습도 24h lag', 'ACTIVE'),
('FEAT-119', 'temperature_ma_24h', '기상', 'DERIVED', '기온 24h MA', 'ACTIVE'),
('FEAT-120', 'heating_degree_days', '쾌적도', 'DERIVED', '난방도일', 'ACTIVE'),
('FEAT-121', 'cooling_degree_days', '쾌적도', 'DERIVED', '냉방도일', 'ACTIVE'),
('FEAT-122', 'comfort_distance', '쾌적도', 'DERIVED', '쾌적 거리', 'ACTIVE')
ON CONFLICT DO NOTHING;

-- Feature Set templates (논문 반영 메모 §4)
INSERT INTO tb_feature_set (feature_set_id, feature_set_name, target_domain, features, apply_site_scope, description) VALUES
('FS-TPL-MINIMAL', 'Minimal Weather Feature Set', 'HEAT_DEMAND',
 '["temperature","hour","day_of_week","month"]', 'ALL', '최소 기상·시간 Feature'),
('FS-TPL-BEHAVIOR', 'Behavior Pattern Feature Set', 'HEAT_DEMAND',
 '["temperature","hour","day_of_week","month","is_weekend","is_holiday"]', 'ALL', '행동 패턴 Feature'),
('FS-TPL-WEATHER-EXT', 'Weather Extended Feature Set', 'HEAT_DEMAND',
 '["temperature","humidity","rainfall","wind_speed","hour","day_of_week","month","is_weekend","is_holiday"]', 'ALL', '기상 확장 Feature'),
('FS-TPL-LAG-ROLL', 'Lag/Rolling Feature Set', 'HEAT_DEMAND',
 '["temperature","humidity","rainfall","wind_speed","hour","day_of_week","month","is_weekend","is_holiday","demand_lag_24h","demand_lag_168h","demand_ma_24h","demand_ma_168h","temperature_lag_24h","humidity_lag_24h","temperature_ma_24h"]', 'ALL', 'Lag·이동평균 Feature'),
('FS-TPL-COMFORT', 'Comfort Index Feature Set', 'HEAT_DEMAND',
 '["temperature","humidity","rainfall","wind_speed","hour","day_of_week","month","is_weekend","is_holiday","demand_lag_24h","demand_lag_168h","demand_ma_24h","demand_ma_168h","temperature_lag_24h","humidity_lag_24h","temperature_ma_24h","heating_degree_days","cooling_degree_days","comfort_distance"]', 'ALL', '쾌적도 Feature'),
('FS-TPL-TWO-STAGE', 'Two-Stage Ready Feature Set', 'HEAT_DEMAND',
 '["month","day_of_week","hour","month_sin","month_cos","hour_sin","hour_cos","is_weekend","is_holiday","season_winter","season_summer","temperature","humidity","rainfall","wind_speed","temperature_diff_24h","demand_lag_24h","demand_lag_168h","demand_ma_24h","demand_ma_168h","temperature_lag_24h","humidity_lag_24h","temperature_ma_24h","heating_degree_days","cooling_degree_days","comfort_distance"]', 'ALL', '2-Stage 준비 풀 Feature')
ON CONFLICT DO NOTHING;
