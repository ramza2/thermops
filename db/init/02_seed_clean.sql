-- THERMOps Clean Seed (마스터·템플릿만, 결과성 데이터 없음)
-- Traefik clean deployment 및 사용자 가이드 실습용
-- Demo/결과 데이터는 db/init/02_seed.sql 또는 reset 후 별도 적재

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

-- CSV sample data sources (실습용 등록 정보만, 적재 데이터 없음)
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

-- Standard dataset types (R7)
\ir r7_standard_dataset_seed.sql

-- Column Role preset (Feature Recipe Builder R1)
INSERT INTO tb_feature_column_role (
    role_id, mapping_id, data_source_id, target_table,
    source_column, target_column, data_type, column_role,
    inferred_role, inference_confidence, role_source, active_yn
) VALUES
('FCR-CSV001-SITE', 'MAP-CSV-001', 'DS-CSV-001', 'heat_demand_actual',
 'site_id', 'site_id', 'STRING', 'ENTITY_KEY', 'ENTITY_KEY', 95.00, 'SEED', 'Y'),
('FCR-CSV001-TIME', 'MAP-CSV-001', 'DS-CSV-001', 'heat_demand_actual',
 'measured_at', 'measured_at', 'DATETIME', 'TIME_KEY', 'TIME_KEY', 95.00, 'SEED', 'Y'),
('FCR-CSV001-TGT', 'MAP-CSV-001', 'DS-CSV-001', 'heat_demand_actual',
 'heat_demand', 'heat_demand', 'NUMERIC', 'TARGET', 'TARGET', 90.00, 'SEED', 'Y'),
('FCR-CSV001-SUP', 'MAP-CSV-001', 'DS-CSV-001', 'heat_demand_actual',
 'supply_temp', 'supply_temp', 'NUMERIC', 'NUMERIC_INPUT', 'NUMERIC_INPUT', 80.00, 'SEED', 'Y'),
('FCR-CSV002-AREA', 'MAP-CSV-002', 'DS-CSV-002', 'weather_observation',
 'weather_area_id', 'weather_area_id', 'STRING', 'ENTITY_KEY', 'ENTITY_KEY', 95.00, 'SEED', 'Y'),
('FCR-CSV002-TIME', 'MAP-CSV-002', 'DS-CSV-002', 'weather_observation',
 'measured_at', 'measured_at', 'DATETIME', 'TIME_KEY', 'TIME_KEY', 95.00, 'SEED', 'Y'),
('FCR-CSV002-TEMP', 'MAP-CSV-002', 'DS-CSV-002', 'weather_observation',
 'temperature', 'temperature', 'NUMERIC', 'NUMERIC_INPUT', 'NUMERIC_INPUT', 85.00, 'SEED', 'Y'),
('FCR-CSV002-HUM', 'MAP-CSV-002', 'DS-CSV-002', 'weather_observation',
 'humidity', 'humidity', 'NUMERIC', 'NUMERIC_INPUT', 'NUMERIC_INPUT', 85.00, 'SEED', 'Y'),
('FCR-CSV002-RAIN', 'MAP-CSV-002', 'DS-CSV-002', 'weather_observation',
 'rainfall', 'rainfall', 'NUMERIC', 'NUMERIC_INPUT', 'NUMERIC_INPUT', 85.00, 'SEED', 'Y'),
('FCR-CSV002-WIND', 'MAP-CSV-002', 'DS-CSV-002', 'weather_observation',
 'wind_speed', 'wind_speed', 'NUMERIC', 'NUMERIC_INPUT', 'NUMERIC_INPUT', 85.00, 'SEED', 'Y'),
('FCR-CSV002-DTYPE', 'MAP-CSV-002', 'DS-CSV-002', 'weather_observation',
 'data_type', 'data_type', 'STRING', 'CATEGORICAL_INPUT', 'CATEGORICAL_INPUT', 75.00, 'SEED', 'Y')
ON CONFLICT (role_id) DO NOTHING;

-- Calendar (Feature 생성·실습용 기준 데이터)
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

-- Feature registry (템플릿 Feature Set용)
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
('FEAT-122', 'comfort_distance', '쾌적도', 'DERIVED', '쾌적 거리', 'ACTIVE'),
('FEAT-003', 'temperature', '기상', 'RAW', '외기온도(°C)', 'ACTIVE'),
('FEAT-004', 'humidity', '기상', 'RAW', '습도(%)', 'ACTIVE'),
('FEAT-005', 'hour_of_day', '달력', 'DERIVED', '시간대(0-23)', 'ACTIVE'),
('FEAT-006', 'day_of_week', '달력', 'DERIVED', '요일(0-6)', 'ACTIVE'),
('FEAT-008', 'is_holiday', '달력', 'DERIVED', '공휴일 여부', 'ACTIVE')
ON CONFLICT DO NOTHING;

-- Feature Set templates
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

-- Training config templates (LightGBM / CatBoost / 2-Stage CatBoost)
INSERT INTO tb_training_config (config_id, config_name, feature_set_id, algorithm, train_period_months, validation_period_months, hyperparams) VALUES
('TRC-TPL-LAG-ROLL', 'Lag/Rolling LightGBM 학습', 'FS-TPL-LAG-ROLL', 'lightgbm', 1, 1, '{"validation_ratio":0.2,"n_estimators":80,"learning_rate":0.05,"max_depth":6}'),
('TRC-TPL-BASELINE', 'Baseline Lag24h 학습', 'FS-TPL-LAG-ROLL', 'baseline', 1, 1, '{"validation_ratio":0.2}'),
('TRC-TPL-CATBOOST', 'CatBoost 학습', 'FS-TPL-LAG-ROLL', 'catboost', 1, 1, '{"validation_ratio":0.2,"iterations":80,"learning_rate":0.05,"depth":6}'),
('TRC-TPL-TWO-STAGE-CATBOOST', '2-Stage CatBoost 학습', 'FS-TPL-TWO-STAGE', 'two_stage_catboost', 1, 1, '{"validation_ratio":0.2,"iterations":80,"learning_rate":0.05,"depth":6}')
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
