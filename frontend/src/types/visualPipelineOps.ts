/** R11-S7-12 Visual Pipeline Ops — read-only admin summary/stuck types. */

export type VisualPipelineRunStatus =
  | "PENDING"
  | "RUNNING"
  | "SUCCESS"
  | "FAILED"
  | "PARTIAL"
  | "CANCELLED";

export type VisualPipelineActivationStatus = "ACTIVE" | "PAUSED" | "INACTIVE" | "ERROR";

export type VisualPipelineOpsStuckReason = "PENDING_TOO_OLD" | "RUNNING_LOCK_EXPIRED";

export interface VisualPipelineOpsWorkerConfig {
  run_executor?: string;
  schedule_activation_enabled?: boolean;
  run_worker_enabled?: boolean;
  schedule_worker_enabled?: boolean;
  run_worker_mode?: string;
  schedule_worker_mode?: string;
  run_worker_poll_interval_seconds?: number;
  run_worker_lock_ttl_seconds?: number;
  run_worker_max_batch_size?: number;
  schedule_worker_poll_interval_seconds?: number;
  schedule_worker_max_batch_size?: number;
}

export interface VisualPipelineOpsStuckSummary {
  pending_older_than_threshold?: number;
  running_lock_expired?: number;
}

export interface VisualPipelineOpsActivityHints {
  latest_claimed_at?: string | null;
  latest_heartbeat_at?: string | null;
  latest_last_triggered_at?: string | null;
  latest_last_skip_at?: string | null;
}

export interface VisualPipelineOpsRecentFailure {
  visual_run_id: string;
  pipeline_id: string;
  mode?: string | null;
  finished_at?: string | null;
  error_message?: string | null;
  activation_id?: string | null;
}

export interface VisualPipelineOpsSummary {
  run_status_counts: Partial<Record<string, number>>;
  activation_status_counts: Partial<Record<string, number>>;
  worker_config: VisualPipelineOpsWorkerConfig;
  stuck_summary: VisualPipelineOpsStuckSummary;
  stuck_criteria?: {
    pending_age_seconds?: number;
    running_lock_grace_seconds?: number;
  };
  activity_hints?: VisualPipelineOpsActivityHints;
  recent_failures?: VisualPipelineOpsRecentFailure[];
  generated_at?: string | null;
}

export interface VisualPipelineOpsStuckRun {
  visual_run_id: string;
  pipeline_id: string;
  mode?: string | null;
  activation_id?: string | null;
  scheduled_for?: string | null;
  run_status: string;
  reason: VisualPipelineOpsStuckReason | string;
  age_seconds?: number | null;
  locked_until?: string | null;
  heartbeat_at?: string | null;
  claimed_by?: string | null;
  attempt_count?: number;
  heartbeat_stale_hint?: boolean;
  created_at?: string | null;
  started_at?: string | null;
}

export interface VisualPipelineOpsStuckRunsResponse {
  items: VisualPipelineOpsStuckRun[];
  total: number;
  criteria: {
    pending_age_seconds: number;
    running_lock_grace_seconds: number;
    limit?: number;
  };
}

export interface VisualPipelineOpsStuckRunsParams {
  pending_age_seconds?: number;
  running_lock_grace_seconds?: number;
  limit?: number;
}
