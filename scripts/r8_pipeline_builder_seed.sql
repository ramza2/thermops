INSERT INTO tb_pipeline_template (
    template_id, template_code, template_name, description, pipeline_type,
    airflow_dag_id, template_version, node_schema_json, edge_schema_json,
    default_config_json, status, active_yn
) VALUES
(
    'PT-FULL-OPERATION', 'FULL_OPERATION_PIPELINE', '전체 운영 파이프라인',
    '데이터 적재부터 Drift 점검까지 전체 운영 흐름', 'FULL_OPERATION',
    'thermops_full_pipeline_dag', '1.0',
    '{"nodes":[{"node_id":"DATA_SOURCE","label":"데이터소스","component_type":"DATA_SOURCE","required":true,"order":1,"config_fields":["data_source_id","mapping_id"]},{"node_id":"DATA_QUALITY","label":"데이터 품질 점검","component_type":"DATA_QUALITY","required":true,"order":2,"config_fields":["quality_rule_set","fail_on_error"]},{"node_id":"FEATURE_BUILD","label":"Feature Build","component_type":"FEATURE_BUILD","required":true,"order":3,"config_fields":["feature_set_id","dataset_type_id"]},{"node_id":"MODEL_TRAINING","label":"모델 학습","component_type":"MODEL_TRAINING","required":false,"order":4,"config_fields":["algorithm","config_id","train_start_date","train_end_date"]},{"node_id":"MODEL_SELECTION","label":"모델 선택","component_type":"MODEL_SELECTION","required":false,"order":5,"config_fields":["model_name","registry_stage"]},{"node_id":"BATCH_PREDICTION","label":"배치 예측","component_type":"BATCH_PREDICTION","required":true,"order":6,"config_fields":["site_ids","predict_start_date","predict_end_date"]},{"node_id":"PERFORMANCE_EVAL","label":"성능 평가","component_type":"PERFORMANCE_EVAL","required":true,"order":7,"config_fields":["metric","threshold"]},{"node_id":"DRIFT_CHECK","label":"Drift 점검","component_type":"DRIFT_CHECK","required":false,"order":8,"config_fields":["baseline_period","recent_period","drift_threshold"]}]}'::jsonb,
    '{"edges":[{"from":"DATA_SOURCE","to":"DATA_QUALITY"},{"from":"DATA_QUALITY","to":"FEATURE_BUILD"},{"from":"FEATURE_BUILD","to":"MODEL_TRAINING"},{"from":"MODEL_TRAINING","to":"MODEL_SELECTION"},{"from":"MODEL_SELECTION","to":"BATCH_PREDICTION"},{"from":"BATCH_PREDICTION","to":"PERFORMANCE_EVAL"},{"from":"PERFORMANCE_EVAL","to":"DRIFT_CHECK"}]}'::jsonb,
    '{"node_config":{"DATA_QUALITY":{"fail_on_error":false},"PERFORMANCE_EVAL":{"metric":"MAPE"}}}'::jsonb,
    'ACTIVE', 'Y'
),
(
    'PT-FEATURE-BUILD', 'FEATURE_BUILD_PIPELINE', 'Feature Build 파이프라인',
    '데이터소스부터 Feature Build·품질 검증까지', 'FEATURE_BUILD',
    'feature_build_dag', '1.0',
    '{"nodes":[{"node_id":"DATA_SOURCE","label":"데이터소스","component_type":"DATA_SOURCE","required":true,"order":1,"config_fields":["data_source_id"]},{"node_id":"DATA_MAPPING","label":"데이터 매핑","component_type":"DATA_MAPPING","required":true,"order":2,"config_fields":["mapping_id"]},{"node_id":"STANDARD_DATASET","label":"표준 데이터셋","component_type":"STANDARD_DATASET","required":true,"order":3,"config_fields":["dataset_type_id"]},{"node_id":"FEATURE_SET","label":"Feature Set","component_type":"FEATURE_SET","required":true,"order":4,"config_fields":["feature_set_id"]},{"node_id":"FEATURE_BUILD","label":"Feature Build","component_type":"FEATURE_BUILD","required":true,"order":5,"config_fields":["feature_set_id"]},{"node_id":"FEATURE_QUALITY","label":"Feature 품질","component_type":"FEATURE_QUALITY","required":false,"order":6,"config_fields":["feature_set_id"]}]}'::jsonb,
    '{"edges":[{"from":"DATA_SOURCE","to":"DATA_MAPPING"},{"from":"DATA_MAPPING","to":"STANDARD_DATASET"},{"from":"STANDARD_DATASET","to":"FEATURE_SET"},{"from":"FEATURE_SET","to":"FEATURE_BUILD"},{"from":"FEATURE_BUILD","to":"FEATURE_QUALITY"}]}'::jsonb,
    NULL, 'ACTIVE', 'Y'
),
(
    'PT-BATCH-PREDICTION', 'BATCH_PREDICTION_PIPELINE', '배치 예측 파이프라인',
    '모델 선택부터 예측·성능 평가·모니터링까지', 'BATCH_PREDICTION',
    'batch_prediction_dag', '1.0',
    '{"nodes":[{"node_id":"MODEL_SELECTION","label":"모델 선택","component_type":"MODEL_SELECTION","required":true,"order":1,"config_fields":["model_name","registry_stage"]},{"node_id":"FEATURE_SET","label":"Feature Set","component_type":"FEATURE_SET","required":true,"order":2,"config_fields":["feature_set_id"]},{"node_id":"BATCH_PREDICTION","label":"배치 예측","component_type":"BATCH_PREDICTION","required":true,"order":3,"config_fields":["site_ids","predict_start_date","predict_end_date"]},{"node_id":"PERFORMANCE_EVAL","label":"성능 평가","component_type":"PERFORMANCE_EVAL","required":true,"order":4,"config_fields":["metric","threshold"]},{"node_id":"MONITORING","label":"모니터링","component_type":"MONITORING","required":false,"order":5,"config_fields":["model_name"]}]}'::jsonb,
    '{"edges":[{"from":"MODEL_SELECTION","to":"FEATURE_SET"},{"from":"FEATURE_SET","to":"BATCH_PREDICTION"},{"from":"BATCH_PREDICTION","to":"PERFORMANCE_EVAL"},{"from":"PERFORMANCE_EVAL","to":"MONITORING"}]}'::jsonb,
    NULL, 'ACTIVE', 'Y'
),
(
    'PT-RETRAINING', 'RETRAINING_PIPELINE', '재학습 파이프라인',
    'Drift 점검부터 재학습·모델 등록까지 (후속 단계)', 'RETRAINING',
    'retraining_dag', '1.0',
    '{"nodes":[{"node_id":"DRIFT_CHECK","label":"Drift 점검","component_type":"DRIFT_CHECK","required":true,"order":1,"config_fields":["drift_threshold"]},{"node_id":"RETRAINING_CANDIDATE","label":"재학습 후보","component_type":"RETRAINING_CANDIDATE","required":true,"order":2,"config_fields":["candidate_policy"]},{"node_id":"APPROVAL","label":"승인","component_type":"APPROVAL","required":true,"order":3,"config_fields":["approval_required"]},{"node_id":"MODEL_TRAINING","label":"모델 학습","component_type":"MODEL_TRAINING","required":true,"order":4,"config_fields":["config_id","algorithm"]},{"node_id":"MODEL_REGISTRY","label":"모델 Registry","component_type":"MODEL_REGISTRY","required":true,"order":5,"config_fields":["registry_stage"]}]}'::jsonb,
    '{"edges":[{"from":"DRIFT_CHECK","to":"RETRAINING_CANDIDATE"},{"from":"RETRAINING_CANDIDATE","to":"APPROVAL"},{"from":"APPROVAL","to":"MODEL_TRAINING"},{"from":"MODEL_TRAINING","to":"MODEL_REGISTRY"}]}'::jsonb,
    NULL, 'PLANNED', 'Y'
)
ON CONFLICT (template_id) DO NOTHING;
