-- THERMOps Operational Seed (R9-S2-0)
-- 범용 MLOps 플랫폼 초기 설치: 시스템 구동에 필요한 최소 코드·설정만 포함
-- 데이터소스·매핑·표준 데이터셋·Feature Set·모델·Pipeline Definition 등은 사용자 등록

-- Common codes (상태·유형 enum)
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

-- System config (플랫폼 기본값 — 도메인·모델명은 사용자가 등록)
INSERT INTO tb_system_config (config_key, config_name, config_value, config_type, scope, description, editable_yn) VALUES
('default_model_name', '기본 모델명', '', 'STRING', 'GLOBAL', 'Champion 미지정 시 사용할 기본 모델명 (비어 있으면 미사용)', 'Y'),
('mape_warning_threshold', 'MAPE 경고 임계치', '8.0', 'NUMBER', 'GLOBAL', '운영 MAPE 경고 알림 임계치(%)', 'Y'),
('drift_warning_threshold', '드리프트 경고 임계치', '0.40', 'NUMBER', 'GLOBAL', 'Feature 드리프트 경고 점수 임계치', 'Y'),
('retraining_mape_threshold', '재학습 MAPE 임계치', '10.0', 'NUMBER', 'GLOBAL', '재학습 후보 산출 MAPE 임계치(%)', 'Y'),
('batch_prediction_default_horizon', '배치 예측 기본 범위', '24', 'NUMBER', 'GLOBAL', '배치 예측 기본 시간 범위(시간)', 'Y'),
('system_version', '시스템 버전', '0.1.0', 'STRING', 'GLOBAL', 'THERMOps 릴리스 버전', 'N')
ON CONFLICT (config_key) DO NOTHING;
