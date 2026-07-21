export type VisualPipelineStatus = "DRAFT" | "VALIDATED" | "ACTIVE" | "ARCHIVED";

export interface VisualPipelineGraphViewport {
  x: number;
  y: number;
  zoom: number;
}

/** R11-S5-1 config validation cache on node.data.config.validation */
export type VisualPipelineConfigValidationStatus =
  | "NOT_VALIDATED"
  | "VALID"
  | "INVALID"
  | "STALE";

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
