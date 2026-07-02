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
  "R9부터 Pipeline Definition을 기반으로 기존 Airflow DAG를 trigger할 수 있습니다. Airflow DAG 파일은 동적으로 생성되지 않으며, schedule_config는 저장만 됩니다.";

export type PipelineRunSource = "PIPELINE_DEFINITION" | "DIRECT_DAG" | "RETRY";

export interface PipelineRunRequest {
  requested_by?: string;
  run_label?: string;
  runtime_params_override?: Record<string, unknown>;
  dry_run?: boolean;
}

export interface PipelineRunResponse {
  pipeline_id: string;
  link_id?: string;
  pipeline_run_id: string;
  airflow_dag_id?: string;
  airflow_run_id?: string | null;
  run_status: string;
  run_source: PipelineRunSource;
  validation?: PipelineValidationResult;
  warnings?: PipelineValidationIssue[];
  runtime_params_snapshot?: Record<string, unknown>;
  airflow_conf?: Record<string, unknown>;
  dry_run?: boolean;
  error_message?: string;
  message?: string;
}

export interface PipelineRunLink {
  link_id: string;
  pipeline_id: string;
  template_id: string;
  pipeline_run_id: string;
  pipeline_name?: string;
  template_code?: string;
  template_name?: string;
  airflow_dag_id?: string | null;
  airflow_run_id?: string | null;
  run_source: PipelineRunSource;
  run_status: string;
  runtime_params_snapshot?: Record<string, unknown> | null;
  node_config_snapshot?: Record<string, unknown> | null;
  validation_snapshot?: Record<string, unknown> | null;
  error_message?: string | null;
  requested_by?: string | null;
  requested_at?: string | null;
  started_at?: string | null;
  finished_at?: string | null;
  duration_minutes?: number | null;
}
