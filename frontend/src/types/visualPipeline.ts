export type VisualPipelineStatus = "DRAFT" | "VALIDATED" | "ACTIVE" | "ARCHIVED";

export interface VisualPipelineGraphViewport {
  x: number;
  y: number;
  zoom: number;
}

/** R11-S5-1 config validation cache on node.data.config.validation */
export type VisualPipelineConfigValidationStatus =
  | "NOT_VALIDATED"
  | "OK"
  | "WARNING"
  | "ERROR"
  | "STALE"
  /** @deprecated use OK */
  | "VALID"
  /** @deprecated use ERROR */
  | "INVALID";

export interface VisualPipelineNodeConfigValidation {
  status: VisualPipelineConfigValidationStatus;
  last_validated_at?: string | null;
  issue_count?: number;
}

export type VisualPipelineNodeConfigValues = Record<string, unknown>;

/** R11-S5-0 node.data.config shape (legacy flat objects normalized on load/save). */
export interface VisualPipelineNodeConfig {
  schema_version?: string | null;
  values: VisualPipelineNodeConfigValues;
  validation?: VisualPipelineNodeConfigValidation;
}

export interface VisualPipelineConfigFieldOptionSource {
  type: "api" | "static";
  endpoint?: string;
  options?: Array<string | { value: string; label: string }>;
}

export interface VisualPipelineConfigFieldSchema {
  name: string;
  type: string;
  field_type?: string;
  ui_component?: string;
  required?: boolean;
  required_if?: string;
  default?: unknown;
  description?: string;
  options?: string[];
  advanced?: boolean;
  readonly?: boolean;
  secret?: boolean;
  store_in_graph?: boolean;
  option_source?: VisualPipelineConfigFieldOptionSource;
}

export interface VisualPipelineConfigSection {
  id: string;
  title: string;
  fields: string[];
}

export interface VisualPipelineComponentConfigSchema {
  component_type: string;
  schema_version: string;
  fields: VisualPipelineConfigFieldSchema[];
  sections?: VisualPipelineConfigSection[];
}

export interface VisualPipelineNodeData {
  label?: string;
  component_type?: string;
  config?: VisualPipelineNodeConfig | Record<string, unknown>;
  [key: string]: unknown;
}

export interface VisualPipelineGraphNode {
  id: string;
  type: string;
  position: { x: number; y: number };
  data?: VisualPipelineNodeData | Record<string, unknown>;
}

export interface VisualPipelineGraphEdge {
  id?: string;
  source: string;
  target: string;
  sourceHandle?: string;
  targetHandle?: string;
  label?: string;
  data?: {
    source_port?: string;
    target_port?: string;
    data_type?: string;
    [key: string]: unknown;
  };
}

export interface VisualPipelineGraph {
  nodes: VisualPipelineGraphNode[];
  edges: VisualPipelineGraphEdge[];
  viewport: VisualPipelineGraphViewport;
}

export interface VisualPipelineSummary {
  pipeline_id: string;
  pipeline_name: string;
  description?: string | null;
  template_id: string;
  pipeline_kind: string;
  pipeline_type?: string;
  status: VisualPipelineStatus;
  current_sync_status: string;
  node_count: number;
  edge_count: number;
  created_at?: string | null;
  updated_at?: string | null;
  has_graph?: boolean;
}

export interface VisualPipelineDetail extends VisualPipelineSummary {
  graph: VisualPipelineGraph;
  created_by?: string | null;
  component_contract_version?: string;
}

export interface VisualPipelineListResponse {
  items: VisualPipelineSummary[];
  total: number;
  limit: number;
  offset: number;
}

export interface VisualPipelineVersion {
  version_id: string;
  pipeline_id: string;
  version_no: number;
  change_summary?: string | null;
  created_at?: string | null;
  node_count: number;
  edge_count: number;
  has_graph?: boolean;
}

export interface VisualPipelineVersionListResponse {
  items: VisualPipelineVersion[];
  total: number;
}

export interface ComponentPort {
  port_id: string;
  data_type: string;
  required?: boolean;
  description?: string;
}

export interface ComponentCatalogItem {
  component_type: string;
  display_name: string;
  category: string;
  status: "ACTIVE" | "DISABLED" | "EXPERIMENTAL";
  description?: string;
  disabled_reason?: string | null;
  input_ports: ComponentPort[];
  output_ports: ComponentPort[];
  config_schema?: Array<{ field_id: string; field_type: string; required?: boolean }>;
}

export interface ComponentCatalogResponse {
  items: ComponentCatalogItem[];
  component_contract_version?: string;
}

export interface ConnectionRule {
  rule_id: string;
  from_component_type: string;
  from_port_id: string;
  to_component_type: string;
  to_port_id: string;
  allowed: boolean;
  reason?: string;
}

export interface ConnectionRulesResponse {
  items: ConnectionRule[];
}

export type GraphTemplateId = "blank" | "rest-upsert" | "cron-full";

export type ValidationSeverity = "OK" | "INFO" | "WARNING" | "ERROR";
export type ValidationLevel = "BASIC" | "STRICT";
export type ValidationIssueSeverity = "ERROR" | "WARNING" | "INFO";

export interface VisualPipelineValidationIssue {
  severity: ValidationIssueSeverity;
  code: string;
  message: string;
  hint?: string;
  phase?: string;
  field_key?: string;
  component_type?: string;
  node_id?: string;
  edge_id?: string;
  source_node_id?: string;
  target_node_id?: string;
  source_component_type?: string;
  target_component_type?: string;
  source_port?: string;
  target_port?: string;
  source_handle?: string;
  target_handle?: string;
  source_data_type?: string;
  target_data_type?: string;
  data_type?: string;
}

export interface VisualPipelineValidationSummary {
  node_count: number;
  edge_count: number;
  error_count: number;
  warning_count: number;
  info_count: number;
}

export interface VisualPipelineValidationResponse {
  valid: boolean;
  severity: ValidationSeverity;
  validation_level: ValidationLevel;
  pipeline_id?: string;
  summary: VisualPipelineValidationSummary;
  issues: VisualPipelineValidationIssue[];
  normalized_graph?: VisualPipelineGraph;
}

export interface VisualPipelineValidationRequest {
  graph: VisualPipelineGraph;
  pipeline_id?: string;
  validation_level?: ValidationLevel;
}

/** R11-S6 Compile Preview / Persist response (flat envelope). */
export type VisualPipelineCompileStatus = "SUCCESS" | "FAILED" | "PARTIAL";

export interface VisualPipelineCompileIssue {
  severity: string;
  code: string;
  message: string;
  phase?: string;
  hint?: string;
  field_key?: string;
  component_type?: string;
  node_id?: string;
  details?: unknown;
}

export interface VisualPipelineCompileStep {
  step_id: string;
  type: string;
  component_type?: string;
  node_id?: string;
  adapter?: string;
  config?: Record<string, unknown>;
  inputs?: Array<Record<string, unknown>>;
  outputs?: Array<Record<string, unknown>>;
}

export interface VisualPipelineCompileSchedule {
  enabled?: boolean;
  component_type?: string;
  node_id?: string;
  adapter?: string;
  schedule_type?: string;
  cron_expression?: string | null;
  timezone?: string | null;
  active_yn?: boolean;
  activation?: string;
  binds_to_node_id?: string | null;
  [key: string]: unknown;
}

export interface VisualPipelineCompileMetadata {
  source_node_id?: string;
  transform_node_id?: string | null;
  load_node_id?: string;
  schedule_node_id?: string | null;
  has_transform?: boolean;
  has_schedule?: boolean;
  pattern?: string;
  generated_by?: string;
  graph_node_count?: number;
  graph_edge_count?: number;
  [key: string]: unknown;
}

export interface VisualPipelineCompiledArtifact {
  version?: string;
  kind?: string;
  steps?: VisualPipelineCompileStep[];
  schedule?: VisualPipelineCompileSchedule | null;
  write_policy?: Record<string, unknown>;
  lineage?: Array<Record<string, unknown>>;
  metadata?: VisualPipelineCompileMetadata;
}

export interface VisualPipelineCompileResponse {
  pipeline_id: string;
  compile_result_id?: string | null;
  compile_status: VisualPipelineCompileStatus | string;
  validation_level?: string;
  graph_version_hash?: string | null;
  config_hash?: string | null;
  compiled_at?: string | null;
  compile_version?: string;
  compiled_artifact?: VisualPipelineCompiledArtifact | null;
  issues?: VisualPipelineCompileIssue[];
  persisted: boolean;
  error_message?: string | null;
  source?: string | null;
}

/** R11-S6-6 Materialization response (flat envelope). */
export type VisualPipelineMaterializationStatus = "SUCCESS" | "FAILED" | "PARTIAL";

export interface VisualPipelineMaterializationIssue {
  severity: string;
  code: string;
  message: string;
  [key: string]: unknown;
}

export interface VisualPipelineMaterializationResponse {
  materialization_result_id?: string | null;
  pipeline_id: string;
  compile_result_id?: string | null;
  materialization_status: VisualPipelineMaterializationStatus | string;
  graph_version_hash?: string | null;
  materialization_version?: string | null;
  materialized_at?: string | null;
  objects?: Record<string, unknown>;
  created?: Record<string, unknown>;
  updated?: Record<string, unknown>;
  skipped?: unknown[];
  issues?: VisualPipelineMaterializationIssue[];
  warnings?: unknown[];
  activation?: string;
  run_created?: boolean;
  error_message?: string | null;
  persisted: boolean;
}

/** R11-S7-4 Manual Run (Background polling). */
export type VisualPipelineRunStatus =
  | "PENDING"
  | "RUNNING"
  | "SUCCESS"
  | "FAILED"
  | "PARTIAL"
  | "CANCELLED";

export interface VisualPipelineRunRequest {
  materialization_result_id?: string | null;
  compile_result_id?: string | null;
  mode?: "MANUAL";
  dry_run?: boolean;
  idempotency_key?: string | null;
  params?: {
    request_params_override?: Record<string, unknown>;
    max_pages?: number;
    limit?: number;
  };
}

export interface VisualPipelineRunIssue {
  severity?: string;
  code?: string;
  message?: string;
  phase?: string;
  step_id?: string | null;
  node_id?: string | null;
  details?: Record<string, unknown>;
  [key: string]: unknown;
}

export interface VisualPipelineRunResponse {
  visual_run_id: string;
  pipeline_id: string;
  mode: "MANUAL" | "SCHEDULED" | string;
  execution_mode: "BACKGROUND" | "SYNC" | string;
  run_status: VisualPipelineRunStatus | string;
  compile_result_id?: string | null;
  materialization_result_id?: string | null;
  graph_version_hash?: string | null;
  load_run_id?: string | null;
  activation_id?: string | null;
  r10_schedule_id?: string | null;
  scheduled_for?: string | null;
  triggered_at?: string | null;
  started_at?: string | null;
  finished_at?: string | null;
  created_at?: string | null;
  result?: Record<string, unknown> | null;
  issues?: VisualPipelineRunIssue[];
  issues_count?: number;
  poll_url?: string | null;
  schedule_active_changed?: boolean;
  current_sync_status_changed?: boolean;
  error_message?: string | null;
  persisted?: boolean;
  /** S8-2 additive */
  dedup_key?: string | null;
  claimed_at?: string | null;
  claimed_by?: string | null;
  locked_until?: string | null;
  heartbeat_at?: string | null;
  attempt_count?: number | null;
  /** S8-4 additive */
  retry_of_run_id?: string | null;
  retry_attempt?: number | null;
  retry_reason?: string | null;
  retry_mode?: string | null;
}

export interface VisualPipelineRunEvent {
  event_id: string;
  visual_run_id: string;
  pipeline_id: string;
  event_type: string;
  step_key?: string | null;
  step_name?: string | null;
  progress_percent?: number | null;
  message?: string | null;
  metadata_json?: Record<string, unknown>;
  created_at?: string | null;
}

export interface VisualPipelineRunEventListResponse {
  items: VisualPipelineRunEvent[];
  limit: number;
  offset: number;
  total: number;
}

export interface VisualPipelineRunProgressStep {
  step_key: string;
  step_name?: string | null;
  status: "pending" | "running" | "completed" | string;
}

export interface VisualPipelineRunProgress {
  visual_run_id: string;
  pipeline_id: string;
  run_status: string;
  current_step_key?: string | null;
  current_step_name?: string | null;
  progress_percent?: number | null;
  is_terminal: boolean;
  last_event_at?: string | null;
  steps: VisualPipelineRunProgressStep[];
  event_count: number;
}

export interface VisualPipelineRunSummary {
  visual_run_id: string;
  pipeline_id: string;
  mode?: string;
  execution_mode?: string;
  run_status: VisualPipelineRunStatus | string;
  compile_result_id?: string | null;
  materialization_result_id?: string | null;
  graph_version_hash?: string | null;
  load_run_id?: string | null;
  activation_id?: string | null;
  r10_schedule_id?: string | null;
  scheduled_for?: string | null;
  triggered_at?: string | null;
  started_at?: string | null;
  finished_at?: string | null;
  created_at?: string | null;
  claimed_by?: string | null;
  claimed_at?: string | null;
  locked_until?: string | null;
  heartbeat_at?: string | null;
  attempt_count?: number | null;
  error_message?: string | null;
  issues_count?: number;
  result_summary?: Record<string, unknown> | null;
  /** S8-4 additive */
  retry_of_run_id?: string | null;
  retry_attempt?: number | null;
  retry_reason?: string | null;
  retry_mode?: string | null;
}

export interface VisualPipelineRunListParams {
  status?: string;
  run_status?: string;
  mode?: string;
  activation_id?: string;
  retry_of_run_id?: string;
  created_from?: string;
  created_to?: string;
  scheduled_from?: string;
  scheduled_to?: string;
  limit?: number;
  offset?: number;
}

export interface VisualPipelineRunRetryRequest {
  reason: string;
  confirm_visual_run_id: string;
  retry_mode?: "SAME_SNAPSHOT";
}

export interface VisualPipelineRunRetryResponse {
  original_visual_run_id: string;
  retry_visual_run_id: string;
  pipeline_id: string;
  retry_attempt: number;
  retry_mode: string;
  run_status: "PENDING" | string;
  reason: string;
  poll_url?: string;
}

export interface VisualPipelineRunListResponse {
  items: VisualPipelineRunSummary[];
  limit?: number;
  offset?: number;
  total?: number;
}

/** R11-S7-8 Schedule Activation. */
export type VisualPipelineScheduleActivationStatus =
  | "ACTIVE"
  | "INACTIVE"
  | "PAUSED"
  | "ERROR"
  | string;

export interface VisualPipelineScheduleActivationResponse {
  activation_id: string;
  pipeline_id: string;
  materialization_result_id?: string | null;
  compile_result_id?: string | null;
  r10_schedule_id: string;
  activation_status: VisualPipelineScheduleActivationStatus;
  cron_expression?: string | null;
  timezone?: string | null;
  activated_at?: string | null;
  deactivated_at?: string | null;
  paused_at?: string | null;
  resumed_at?: string | null;
  next_due_at?: string | null;
  last_triggered_at?: string | null;
  last_due_at?: string | null;
  last_skip_at?: string | null;
  last_skip_reason?: string | null;
  trigger_count?: number;
  missed_count?: number;
  metadata?: Record<string, unknown> | null;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface VisualPipelineScheduleActivationListResponse {
  items: VisualPipelineScheduleActivationResponse[];
  total?: number;
}
