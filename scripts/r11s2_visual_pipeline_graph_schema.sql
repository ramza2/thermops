-- R11-S2 Visual Pipeline graph storage (tb_pipeline_* extension)
-- No tb_visual_pipeline_* tables.

-- 1) Definition columns
ALTER TABLE tb_pipeline_definition
    ADD COLUMN IF NOT EXISTS pipeline_kind VARCHAR(50) NOT NULL DEFAULT 'MLOPS_FLOW';

ALTER TABLE tb_pipeline_definition
    ADD COLUMN IF NOT EXISTS current_graph_json JSONB;

ALTER TABLE tb_pipeline_definition
    ADD COLUMN IF NOT EXISTS current_sync_status VARCHAR(30) NOT NULL DEFAULT 'NOT_COMPILED';

UPDATE tb_pipeline_definition
SET pipeline_kind = 'MLOPS_FLOW'
WHERE pipeline_kind IS NULL OR TRIM(pipeline_kind) = '';

UPDATE tb_pipeline_definition
SET current_sync_status = 'NOT_COMPILED'
WHERE current_sync_status IS NULL OR TRIM(current_sync_status) = '';

CREATE INDEX IF NOT EXISTS ix_pipeline_definition_kind
    ON tb_pipeline_definition(pipeline_kind);

-- 2) Skeleton template for Visual Pipeline Studio (FK only; empty graph schema)
INSERT INTO tb_pipeline_template (
    template_id,
    template_code,
    template_name,
    description,
    pipeline_type,
    airflow_dag_id,
    template_version,
    node_schema_json,
    edge_schema_json,
    default_config_json,
    status,
    active_yn,
    created_at,
    updated_at
) VALUES (
    'PT-VISUAL-DATA-LOAD',
    'VISUAL_DATA_LOAD',
    'Visual Data Load Pipeline',
    'Visual Pipeline Studio 데이터 적재 파이프라인용 skeleton template (FK/생성용). 고정 노드 강제 아님.',
    'DATA_LOAD',
    NULL,
    '1.0',
    '{"nodes":[]}'::jsonb,
    '{"edges":[]}'::jsonb,
    NULL,
    'ACTIVE',
    'Y',
    NOW(),
    NOW()
)
ON CONFLICT (template_id) DO UPDATE SET
    template_code = EXCLUDED.template_code,
    template_name = EXCLUDED.template_name,
    description = EXCLUDED.description,
    pipeline_type = EXCLUDED.pipeline_type,
    node_schema_json = EXCLUDED.node_schema_json,
    edge_schema_json = EXCLUDED.edge_schema_json,
    status = EXCLUDED.status,
    active_yn = EXCLUDED.active_yn,
    updated_at = NOW();
