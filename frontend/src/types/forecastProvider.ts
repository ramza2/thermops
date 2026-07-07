export interface ForecastProviderConfig {
  provider_config_id?: string;
  provider_name?: string;
  provider_type?: string;
  source_operation_id?: string | null;
  default_num_of_rows?: number;
  default_data_type?: string;
  base_time_policy?: string;
  delay_minutes?: number;
  active_yn?: boolean;
}

export interface ForecastPreviewResult {
  entity_id: string;
  nx: number;
  ny: number;
  forecast_base_at?: string;
  target_start_at?: string | null;
  target_end_at?: string | null;
  row_count: number;
  matched_row_count: number;
  cache_hit: boolean;
  snapshot_id?: string;
  sample_rows?: Record<string, unknown>[];
  warnings?: string[];
  source_operation_id?: string;
}

export interface ForecastInputSummary {
  enabled?: boolean;
  entity_id?: string;
  nx?: number;
  ny?: number;
  source_operation_id?: string;
  forecast_base_at?: string;
  target_row_count?: number;
  matched_row_count?: number;
  saved_input_count?: number;
  cache_hit?: boolean;
  snapshot_id?: string;
  warnings?: string[];
  failed?: boolean;
  error_message?: string;
}
