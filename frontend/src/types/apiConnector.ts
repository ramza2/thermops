export interface ApiConnectorOperation {
  operation_id: string;
  data_source_id: string;
  operation_name: string;
  operation_description?: string | null;
  http_method: string;
  endpoint_path: string;
  full_url_preview?: string | null;
  request_content_type?: string;
  response_format: string;
  response_item_path?: string | null;
  result_array_mode?: string;
  target_table?: string | null;
  standard_dataset_id?: string | null;
  active_yn: boolean;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface ApiConnectorOperationDetail extends ApiConnectorOperation {
  params?: ApiConnectorParam[];
  pagination?: ApiConnectorPagination | null;
  transform_config?: ApiConnectorTransformConfig | null;
}

export interface ApiConnectorParam {
  param_id?: string;
  operation_id?: string;
  param_name: string;
  display_name?: string | null;
  param_location: string;
  param_type: string;
  required_yn: boolean;
  default_value?: string | null;
  example_value?: string | null;
  allowed_values_json?: unknown;
  value_source: string;
  secret_key_ref?: string | null;
  encode_yn: boolean;
  sort_order: number;
  active_yn?: boolean;
}

export interface ApiConnectorCredential {
  credential_id: string;
  data_source_id: string;
  credential_name: string;
  credential_type: string;
  key_location: string;
  key_name: string;
  secret_value_masked?: string | null;
  has_secret: boolean;
  encoding_policy: string;
  active_yn?: boolean;
}

export interface ApiConnectorPagination {
  pagination_id?: string;
  operation_id?: string;
  pagination_type: string;
  page_param_name?: string | null;
  size_param_name?: string | null;
  page_start?: number;
  page_size?: number;
  max_pages?: number;
  total_count_path?: string | null;
  next_link_path?: string | null;
  stop_condition?: string;
  active_yn?: boolean;
}

export interface ApiConnectorRequestPreview {
  operation_id: string;
  masked_url: string;
  query_params_masked: Record<string, unknown>;
  headers_masked: Record<string, unknown>;
  body_masked: Record<string, unknown>;
  actual_call_ready: boolean;
  encoding_policy?: string | null;
  warnings?: string[];
  service_key_hint?: string;
}

export interface ApiConnectorTestCallResult {
  success: boolean;
  message?: string;
  item_count: number;
  sample_items?: Record<string, unknown>[];
  http_status?: number;
  duration_ms?: number;
  call_log_id?: string;
  snapshot_id?: string | null;
}

export interface ApiConnectorResponsePreview {
  operation_id: string;
  item_count: number;
  sample_items: Record<string, unknown>[];
  snapshot_id?: string | null;
}

export interface ApiConnectorLoadPreview {
  target_table: string;
  preview_rows: Record<string, unknown>[];
  item_count: number;
  preview_count: number;
  mapping_applied: boolean;
  api_item_count?: number;
  raw_item_count?: number;
  transformed_row_count?: number;
  transform_applied?: boolean;
  transform_summary?: Record<string, unknown> | null;
  unmapped_codes?: Record<string, unknown>[];
  warnings?: string[];
  sample_rows?: Record<string, unknown>[];
  snapshot_id?: string | null;
  write_mode?: string;
  write_policy_summary?: Record<string, unknown>;
  dedup_summary_id?: string;
  estimated_insert_count?: number;
  estimated_update_count?: number;
  estimated_skip_count?: number;
  duplicate_within_batch_count?: number;
  existing_match_count?: number;
  sample_conflicts?: Record<string, unknown>[];
}

export interface ApiConnectorLoadRun {
  load_run_id: string;
  operation_id: string;
  data_source_id?: string;
  target_table?: string;
  run_status: string;
  inserted_count: number;
  skipped_count?: number;
  updated_count?: number;
  unchanged_count?: number;
  skipped_duplicate_count?: number;
  write_mode?: string;
  dedup_summary_id?: string;
  error_count?: number;
  started_at?: string;
  finished_at?: string;
  error_message?: string | null;
  result_summary?: Record<string, unknown> | null;
  request_params_masked?: Record<string, unknown>;
}

export interface ApiConnectorWritePolicy {
  write_policy_id?: string;
  operation_id: string;
  target_table?: string | null;
  write_mode: string;
  conflict_key_columns_json?: string[];
  update_columns_json?: string[];
  exclude_update_columns_json?: string[];
  null_update_policy?: string;
  duplicate_within_batch_policy?: string;
  no_conflict_key_policy?: string;
  warnings?: string[];
}

export interface ApiConnectorCallLog {
  call_log_id: string;
  operation_id: string;
  data_source_id?: string;
  called_at: string;
  request_url_masked?: string;
  request_params_masked?: Record<string, unknown>;
  success_yn: boolean;
  response_item_count: number;
  http_status?: number;
  duration_ms?: number;
  error_message?: string | null;
  raw_response_snapshot_id?: string | null;
}

export interface ApiConnectorSnapshot {
  snapshot_id: string;
  operation_id: string;
  captured_at?: string;
  response_format: string;
  item_count: number;
  sample_only_yn: boolean;
  normalized_items_json?: Record<string, unknown>[] | null;
  raw_response_preview?: string;
}

export interface ColumnMatchRow {
  source_field: string;
  target_column: string | null;
  status: "matched" | "no_target" | "unmapped_target";
}

export const WIZARD_STEP_TITLES = [
  "기본 정보",
  "인증 정보",
  "요청 파라미터",
  "페이징 방식",
  "응답 데이터 경로",
  "변환 설정",
  "적재 대상",
  "테스트 호출",
  "검토 및 저장",
] as const;

export interface ApiConnectorTransformConfig {
  transform_config_id?: string;
  operation_id?: string;
  transform_type: string;
  transform_name?: string | null;
  source_system?: string;
  external_code_group?: string;
  external_code_field?: string;
  external_name_field?: string;
  date_field?: string;
  date_format?: string;
  hour_column_prefix?: string;
  hour_column_suffix?: string;
  hour_start?: number;
  hour_end?: number;
  value_output_field?: string;
  measured_at_output_field?: string;
  entity_id_output_field?: string;
  entity_code_output_field?: string;
  external_code_output_field?: string;
  external_name_output_field?: string;
  timestamp_policy?: string;
  hour_24_policy?: string;
  unmapped_policy?: string;
  null_value_policy?: string;
  numeric_parse_policy?: string;
  active_yn?: boolean;
  policy_warnings?: string[];
  station_code_field?: string;
  observed_at_field?: string;
  value_field_mappings_json?: Record<string, string> | null;
  special_day_name_field?: string;
  special_day_type_field?: string | null;
  default_special_day_type?: string;
  public_holiday_field?: string;
  calendar_mode?: string;
  calendar_year?: number | null;
  calendar_month?: number | null;
  hour_generation_yn?: boolean;
  station_unmapped_policy?: string;
  store_raw_json?: boolean;
  metadata_json?: Record<string, unknown> | null;
}

export interface ApiConnectorTransformPreview {
  operation_id: string;
  target_table?: string | null;
  raw_item_count: number;
  transformed_row_count: number;
  sample_rows: Record<string, unknown>[];
  unmapped_codes?: Record<string, unknown>[];
  warnings?: string[];
  transform_summary?: Record<string, unknown>;
  blocked?: boolean;
  block_reason?: string | null;
}

export const PARAM_QUICK_ADD: { param_name: string; display_name: string; param_type: string; value_source?: string }[] = [
  { param_name: "serviceKey", display_name: "serviceKey", param_type: "SECRET", value_source: "SECRET_REF" },
  { param_name: "pageNo", display_name: "페이지 번호", param_type: "INTEGER" },
  { param_name: "numOfRows", display_name: "행 수", param_type: "INTEGER" },
  { param_name: "dataType", display_name: "데이터 유형", param_type: "STRING" },
  { param_name: "_type", display_name: "응답 형식", param_type: "STRING" },
  { param_name: "base_date", display_name: "기준일", param_type: "DATE" },
  { param_name: "base_time", display_name: "기준시각", param_type: "STRING" },
  { param_name: "nx", display_name: "격자 X", param_type: "INTEGER" },
  { param_name: "ny", display_name: "격자 Y", param_type: "INTEGER" },
  { param_name: "solYear", display_name: "양력 연도", param_type: "INTEGER" },
  { param_name: "solMonth", display_name: "양력 월", param_type: "INTEGER" },
];
