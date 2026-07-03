export interface ApiConnectorOperation {
  operation_id: string;
  data_source_id: string;
  operation_name: string;
  operation_description?: string | null;
  http_method: string;
  endpoint_path: string;
  full_url_preview?: string | null;
  response_format: string;
  response_item_path?: string | null;
  target_table?: string | null;
  active_yn: boolean;
  created_at?: string | null;
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
}

export interface ApiConnectorCallLog {
  call_log_id: string;
  operation_id: string;
  called_at: string;
  request_url_masked?: string;
  success_yn: boolean;
  response_item_count: number;
  http_status?: number;
}

export interface ApiConnectorLoadRun {
  load_run_id: string;
  operation_id: string;
  target_table?: string;
  run_status: string;
  inserted_count: number;
  started_at?: string;
}
