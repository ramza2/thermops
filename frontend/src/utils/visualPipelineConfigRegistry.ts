/**
 * R11-S5-1 Visual Pipeline config schema registry (frontend local mirror of S1 catalog).
 * Field keys match backend component_catalog_service config_schema[].name.
 */
import type {
  VisualPipelineComponentConfigSchema,
  VisualPipelineConfigFieldSchema,
  VisualPipelineConfigSection,
  VisualPipelineNodeConfigValues,
} from "@/types/visualPipeline";

export const VISUAL_PIPELINE_CONFIG_SCHEMA_VERSION = "R11-S5-0";

export const MVP_CONFIG_COMPONENT_TYPES = [
  "VP_REST_API_SOURCE",
  "VP_TRANSFORM",
  "VP_UPSERT_LOAD",
  "VP_CRON_SCHEDULE",
] as const;

export type MvpConfigComponentType = (typeof MVP_CONFIG_COMPONENT_TYPES)[number];

function field(
  name: string,
  partial: Omit<VisualPipelineConfigFieldSchema, "name">,
): VisualPipelineConfigFieldSchema {
  return { name, ...partial };
}

const REST_FIELDS: VisualPipelineConfigFieldSchema[] = [
  field("data_source_id", {
    type: "string",
    field_type: "string",
    ui_component: "select",
    required: true,
    description: "데이터 소스 ID",
    option_source: { type: "api", endpoint: "/api/v1/data-sources" },
  }),
  field("operation_name", { type: "string", field_type: "string", ui_component: "text", required: true }),
  field("endpoint_path", {
    type: "string",
    field_type: "string",
    ui_component: "text",
    required: true,
    description: "API endpoint path",
  }),
  field("http_method", {
    type: "enum",
    field_type: "enum",
    ui_component: "select",
    required: true,
    default: "GET",
    options: ["GET", "POST"],
  }),
  field("request_params", {
    type: "object",
    field_type: "object",
    ui_component: "key_value_editor",
    required: false,
    advanced: true,
  }),
  field("pagination", {
    type: "object",
    field_type: "object",
    ui_component: "object_editor",
    required: false,
    advanced: true,
  }),
  field("response_item_path", { type: "string", field_type: "string", ui_component: "text", required: false }),
  field("credential_ref", {
    type: "reference",
    field_type: "reference",
    ui_component: "select",
    required: false,
    secret: true,
    store_in_graph: false,
    description: "credential 참조만 저장 (secret 원문 금지)",
  }),
];

const TRANSFORM_FIELDS: VisualPipelineConfigFieldSchema[] = [
  field("transform_type", {
    type: "enum",
    field_type: "enum",
    ui_component: "select",
    required: true,
    default: "WIDE_HOUR_TO_LONG",
    options: [
      "NONE",
      "WIDE_HOUR_TO_LONG",
      "ASOS_HOURLY_TO_CANONICAL",
      "CALENDAR_SPECIAL_DAY_TO_DATE",
      "CALENDAR_DATE_TO_HOUR",
    ],
  }),
  field("mapping_config", { type: "object", field_type: "object", ui_component: "object_editor", required: false }),
  field("unmapped_policy", {
    type: "enum",
    field_type: "enum",
    ui_component: "select",
    required: false,
    advanced: true,
    // Backend catalog has no enum values yet — FE overlay MVP for S5-3.
    options: ["KEEP", "DROP", "ERROR"],
  }),
  field("hour_policy", {
    type: "object",
    field_type: "object",
    ui_component: "object_editor",
    required: false,
    advanced: true,
  }),
  field("target_schema_preview", {
    type: "object",
    field_type: "object",
    ui_component: "readonly_json",
    required: false,
    readonly: true,
    store_in_graph: false,
  }),
];

const UPSERT_FIELDS: VisualPipelineConfigFieldSchema[] = [
  field("standard_dataset_id", {
    type: "string",
    field_type: "string",
    ui_component: "select",
    required: false,
    option_source: { type: "api", endpoint: "/api/v1/standard-datasets" },
  }),
  field("target_table", { type: "string", field_type: "string", ui_component: "text", required: true }),
  field("write_mode", {
    type: "enum",
    field_type: "enum",
    ui_component: "select",
    required: true,
    default: "INSERT_ONLY",
    options: ["INSERT_ONLY", "DEDUPLICATE", "UPSERT"],
  }),
  field("conflict_key_columns_json", {
    type: "array[string]",
    field_type: "array[string]",
    ui_component: "string_list",
    required: false,
    required_if: "write_mode in [DEDUPLICATE, UPSERT]",
  }),
  field("duplicate_within_batch_policy", {
    type: "enum",
    field_type: "enum",
    ui_component: "select",
    required: false,
    default: "KEEP_LAST",
    options: ["KEEP_FIRST", "KEEP_LAST", "ERROR"],
    advanced: true,
  }),
  field("null_update_policy", {
    type: "enum",
    field_type: "enum",
    ui_component: "select",
    required: false,
    default: "KEEP_EXISTING",
    options: ["KEEP_EXISTING", "OVERWRITE_WITH_NULL"],
    advanced: true,
  }),
  field("save_dedup_summary_yn", {
    type: "boolean",
    field_type: "boolean",
    ui_component: "checkbox",
    required: false,
    default: true,
    advanced: true,
  }),
];

const CRON_FIELDS: VisualPipelineConfigFieldSchema[] = [
  field("schedule_type", {
    type: "enum",
    field_type: "enum",
    ui_component: "select",
    required: true,
    default: "CRON",
    options: ["CRON"],
  }),
  field("cron_expression", { type: "string", field_type: "string", ui_component: "text", required: true }),
  field("timezone", {
    type: "string",
    field_type: "string",
    ui_component: "select",
    required: true,
    default: "Asia/Seoul",
    options: ["Asia/Seoul", "UTC", "Asia/Tokyo", "America/Los_Angeles"],
  }),
  field("start_at", { type: "datetime", field_type: "datetime", ui_component: "datetime", required: false, advanced: true }),
  field("end_at", { type: "datetime", field_type: "datetime", ui_component: "datetime", required: false, advanced: true }),
  field("active_yn", { type: "boolean", field_type: "boolean", ui_component: "checkbox", required: false, default: false }),
  field("retry_enabled_yn", {
    type: "boolean",
    field_type: "boolean",
    ui_component: "checkbox",
    required: false,
    default: false,
    advanced: true,
  }),
  field("max_retry_count", {
    type: "integer",
    field_type: "integer",
    ui_component: "number",
    required: false,
    default: 0,
    advanced: true,
  }),
  field("retry_interval_minutes", {
    type: "integer",
    field_type: "integer",
    ui_component: "number",
    required: false,
    default: 10,
    advanced: true,
  }),
];

const REST_SECTIONS: VisualPipelineConfigSection[] = [
  { id: "connection", title: "연결", fields: ["data_source_id", "operation_name", "credential_ref"] },
  { id: "request", title: "Request", fields: ["endpoint_path", "http_method", "request_params", "pagination"] },
  { id: "response", title: "Response", fields: ["response_item_path"] },
];

const TRANSFORM_SECTIONS: VisualPipelineConfigSection[] = [
  { id: "transform", title: "Transform", fields: ["transform_type", "mapping_config"] },
  { id: "policy", title: "Policy", fields: ["unmapped_policy", "hour_policy"] },
  { id: "preview", title: "Preview", fields: ["target_schema_preview"] },
];

const UPSERT_SECTIONS: VisualPipelineConfigSection[] = [
  { id: "target", title: "Target", fields: ["standard_dataset_id", "target_table"] },
  { id: "write_policy", title: "Write Policy", fields: ["write_mode", "conflict_key_columns_json"] },
  {
    id: "dedup",
    title: "Dedup",
    fields: ["duplicate_within_batch_policy", "null_update_policy", "save_dedup_summary_yn"],
  },
];

const CRON_SECTIONS: VisualPipelineConfigSection[] = [
  { id: "schedule", title: "Schedule", fields: ["schedule_type", "cron_expression", "timezone"] },
  { id: "window", title: "Window", fields: ["start_at", "end_at", "active_yn"] },
  { id: "retry", title: "Retry", fields: ["retry_enabled_yn", "max_retry_count", "retry_interval_minutes"] },
];

/** Placeholder / default values (store_in_graph !== false fields only). */
const PLACEHOLDER_VALUES: Record<MvpConfigComponentType, VisualPipelineNodeConfigValues> = {
  VP_REST_API_SOURCE: {
    data_source_id: "DS-SAMPLE",
    operation_name: "sample_fetch",
    endpoint_path: "/api/v1/sample",
    http_method: "GET",
    response_item_path: "$.items",
  },
  VP_TRANSFORM: {
    transform_type: "WIDE_HOUR_TO_LONG",
    mapping_config: {},
  },
  VP_UPSERT_LOAD: {
    standard_dataset_id: "SD-001",
    target_table: "tb_sample_fact",
    write_mode: "UPSERT",
    conflict_key_columns_json: ["entity_id", "measured_at"],
    duplicate_within_batch_policy: "KEEP_LAST",
    save_dedup_summary_yn: true,
  },
  VP_CRON_SCHEDULE: {
    schedule_type: "CRON",
    cron_expression: "0 6 * * *",
    timezone: "Asia/Seoul",
    active_yn: false,
  },
};

export const VISUAL_PIPELINE_CONFIG_SCHEMAS: Record<MvpConfigComponentType, VisualPipelineComponentConfigSchema> = {
  VP_REST_API_SOURCE: {
    component_type: "VP_REST_API_SOURCE",
    schema_version: VISUAL_PIPELINE_CONFIG_SCHEMA_VERSION,
    fields: REST_FIELDS,
    sections: REST_SECTIONS,
  },
  VP_TRANSFORM: {
    component_type: "VP_TRANSFORM",
    schema_version: VISUAL_PIPELINE_CONFIG_SCHEMA_VERSION,
    fields: TRANSFORM_FIELDS,
    sections: TRANSFORM_SECTIONS,
  },
  VP_UPSERT_LOAD: {
    component_type: "VP_UPSERT_LOAD",
    schema_version: VISUAL_PIPELINE_CONFIG_SCHEMA_VERSION,
    fields: UPSERT_FIELDS,
    sections: UPSERT_SECTIONS,
  },
  VP_CRON_SCHEDULE: {
    component_type: "VP_CRON_SCHEDULE",
    schema_version: VISUAL_PIPELINE_CONFIG_SCHEMA_VERSION,
    fields: CRON_FIELDS,
    sections: CRON_SECTIONS,
  },
};

export function isMvpConfigComponentType(componentType: string): componentType is MvpConfigComponentType {
  return (MVP_CONFIG_COMPONENT_TYPES as readonly string[]).includes(componentType);
}

export function getVisualPipelineConfigSchema(
  componentType: string,
): VisualPipelineComponentConfigSchema | null {
  if (!isMvpConfigComponentType(componentType)) return null;
  return VISUAL_PIPELINE_CONFIG_SCHEMAS[componentType];
}

export function getVisualPipelineConfigFields(componentType: string): VisualPipelineConfigFieldSchema[] {
  return getVisualPipelineConfigSchema(componentType)?.fields ?? [];
}

export function getConfigField(
  componentType: string,
  fieldName: string,
): VisualPipelineConfigFieldSchema | undefined {
  return getVisualPipelineConfigFields(componentType).find((f) => f.name === fieldName);
}

export function getConfigSections(componentType: string): VisualPipelineConfigSection[] {
  return getVisualPipelineConfigSchema(componentType)?.sections ?? [];
}

export function isSecretConfigField(componentType: string, fieldName: string): boolean {
  const f = getConfigField(componentType, fieldName);
  return Boolean(f?.secret);
}

export function shouldStoreFieldInGraph(field: VisualPipelineConfigFieldSchema): boolean {
  if (field.store_in_graph === false) return false;
  if (field.readonly) return false;
  return true;
}

export function getDefaultConfigValues(componentType: string): VisualPipelineNodeConfigValues {
  if (isMvpConfigComponentType(componentType)) {
    return { ...PLACEHOLDER_VALUES[componentType] };
  }
  const values: VisualPipelineNodeConfigValues = {};
  for (const f of getVisualPipelineConfigFields(componentType)) {
    if (!shouldStoreFieldInGraph(f)) continue;
    if (f.default !== undefined) values[f.name] = f.default;
  }
  return values;
}

export function getPlaceholderConfigValues(componentType: string): VisualPipelineNodeConfigValues {
  return getDefaultConfigValues(componentType);
}
