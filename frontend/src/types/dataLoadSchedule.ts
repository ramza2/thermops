export interface DataLoadSchedule {
  schedule_id: string;
  schedule_name: string;
  schedule_description?: string | null;
  operation_id: string;
  operation_name?: string | null;
  schedule_type: string;
  cron_expression?: string | null;
  timezone: string;
  active_yn: boolean;
  run_policy: string;
  load_window_type: string;
  window_offset_minutes?: number | null;
  runtime_params_template?: Record<string, unknown> | null;
  retry_enabled_yn: boolean;
  max_retry_count: number;
  retry_interval_minutes: number;
  last_run_at?: string | null;
  last_success_at?: string | null;
  next_run_at?: string | null;
  last_run_status?: string | null;
  start_at?: string | null;
  end_at?: string | null;
}

export interface DataLoadScheduleRun {
  schedule_run_id: string;
  schedule_id: string;
  schedule_name?: string | null;
  operation_id: string;
  api_load_run_id?: string | null;
  run_source: string;
  scheduled_for?: string | null;
  started_at?: string | null;
  finished_at?: string | null;
  run_status: string;
  attempt_no: number;
  inserted_count: number;
  updated_count?: number;
  skipped_count: number;
  skipped_duplicate_count?: number;
  write_mode?: string;
  error_count: number;
  error_message?: string | null;
  runtime_params_masked?: Record<string, unknown> | null;
  result_summary?: Record<string, unknown> | null;
}

export interface CronPreviewResult {
  valid: boolean;
  normalized_expression?: string | null;
  timezone?: string;
  next_run_at?: string | null;
  next_runs?: string[];
  explanation?: string | null;
  warnings?: string[];
  errors?: string[];
}

export const SCHEDULE_TYPE_OPTIONS = [
  { value: "MANUAL", label: "수동" },
  { value: "HOURLY", label: "매시간" },
  { value: "DAILY", label: "매일" },
  { value: "WEEKLY", label: "매주" },
  { value: "MONTHLY", label: "매월" },
  { value: "CRON", label: "CRON 일정" },
];

export const LOAD_WINDOW_OPTIONS = [
  { value: "NONE", label: "없음" },
  { value: "LAST_SUCCESS_TO_NOW", label: "마지막 성공 ~ 현재" },
  { value: "FIXED_OFFSET", label: "고정 오프셋" },
  { value: "MANUAL_PARAMS", label: "수동 파라미터" },
];

export const CRON_EXAMPLES = [
  { label: "매 5분", expression: "*/5 * * * *" },
  { label: "매시간 정각", expression: "0 * * * *" },
  { label: "매일 02:30", expression: "30 2 * * *" },
  { label: "평일 09:00", expression: "0 9 * * 1-5" },
  { label: "매월 1일 00:00", expression: "0 0 1 * *" },
];
