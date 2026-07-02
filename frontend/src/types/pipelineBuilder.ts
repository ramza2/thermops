export interface PipelineNodeSchema {
  node_id: string;
  label: string;
  component_type: string;
  required: boolean;
  order: number;
  config_fields: string[];
  config?: Record<string, unknown>;
  config_state?: string;
  error_count?: number;
  warning_count?: number;
}

export interface PipelineEdgeSchema {
  from: string;
  to: string;
}

export interface PipelineFlow {
  nodes: PipelineNodeSchema[];
  edges: PipelineEdgeSchema[];
}

export interface PipelineTemplate {
  template_id: string;
  template_code: string;
  template_name: string;
  description?: string | null;
  pipeline_type: string;
  airflow_dag_id?: string | null;
  template_version: string;
  status: string;
  active: boolean;
  node_schema?: { nodes: PipelineNodeSchema[] };
  edge_schema?: { edges: PipelineEdgeSchema[] };
  default_config?: Record<string, unknown>;
  flow?: PipelineFlow;
}

export interface PipelineDefinition {
  pipeline_id: string;
  template_id: string;
  template_code?: string;
  template_name?: string;
  pipeline_name: string;
  description?: string | null;
  pipeline_type: string;
  airflow_dag_id?: string | null;
  node_config: Record<string, Record<string, unknown>>;
  schedule_config?: Record<string, unknown> | null;
  validation_result?: PipelineValidationResult | null;
  status: string;
  last_validated_at?: string | null;
  last_run_id?: string | null;
  flow?: PipelineFlow;
}

export interface PipelineValidationResult {
  valid: boolean;
  errors: PipelineValidationIssue[];
  warnings: PipelineValidationIssue[];
  required_missing_nodes: string[];
  runtime_params_preview?: Record<string, unknown>;
}

export interface PipelineValidationIssue {
  node_id?: string;
  code?: string;
  message: string;
}

export interface PipelineNodeOptions {
  component_type: string;
  fields: Record<string, { value: string; label: string }[]>;
}

export interface PipelineRuntimePreview {
  pipeline_id: string;
  airflow_dag_id?: string | null;
  template_code?: string;
  runtime_params: Record<string, unknown>;
  note?: string;
}

export interface PipelineDefinitionCreateRequest {
  template_id: string;
  pipeline_name: string;
  description?: string;
  node_config?: Record<string, Record<string, unknown>>;
  schedule_config?: Record<string, unknown>;
}

export const R8_PIPELINE_NOTE =
  "R8에서는 Flow Chart 시각화·노드 설정·실행 파라미터 저장만 지원합니다. Airflow DAG 동적 생성 및 실제 실행 연결은 후속 단계입니다.";
