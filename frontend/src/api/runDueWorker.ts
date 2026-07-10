import { fetchApi, postApi } from "./client";

export interface RunDueWorkerInstance {
  worker_instance_id: string;
  worker_name: string;
  worker_mode: string;
  host_name?: string | null;
  process_id?: number | null;
  enabled_yn: boolean;
  status: string;
  poll_interval_seconds: number;
  last_heartbeat_at?: string | null;
  last_run_started_at?: string | null;
  last_run_finished_at?: string | null;
  last_run_status?: string | null;
  consecutive_failure_count: number;
  total_run_count: number;
  total_success_count: number;
  total_failure_count: number;
  created_at?: string;
  updated_at?: string | null;
}

export interface RunDueWorkerRun {
  worker_run_id: string;
  worker_instance_id?: string | null;
  worker_name?: string | null;
  run_mode: string;
  started_at: string;
  finished_at?: string | null;
  run_status: string;
  due_schedule_count: number;
  executed_schedule_count: number;
  success_schedule_count: number;
  failed_schedule_count: number;
  skipped_schedule_count: number;
  run_due_result_json?: Record<string, unknown> | null;
  error_message?: string | null;
}

export interface RunDueWorkerSummary {
  instance_count: number;
  active_instance_count: number;
  stale_instance_count: number;
  total_worker_run_count: number;
  failed_worker_run_count: number;
  lock_key: string;
}

export interface RunDueWorkerLock {
  lock_key: string;
  owner_instance_id: string;
  acquired_at?: string | null;
  expires_at?: string | null;
  heartbeat_at?: string | null;
}

export async function getRunDueWorkerSummary(): Promise<RunDueWorkerSummary> {
  return fetchApi<RunDueWorkerSummary>("/run-due-worker/summary");
}

export async function listRunDueWorkerInstances(): Promise<RunDueWorkerInstance[]> {
  return fetchApi<RunDueWorkerInstance[]>("/run-due-worker/instances");
}

export async function listRunDueWorkerRuns(limit = 50): Promise<RunDueWorkerRun[]> {
  return fetchApi<RunDueWorkerRun[]>(`/run-due-worker/runs?limit=${limit}`);
}

export async function listRunDueWorkerLocks(): Promise<RunDueWorkerLock[]> {
  return fetchApi<RunDueWorkerLock[]>("/run-due-worker/locks");
}

export async function runDueWorkerOnce(workerName?: string): Promise<RunDueWorkerRun> {
  return postApi<RunDueWorkerRun>("/run-due-worker/run-once", { worker_name: workerName ?? null });
}

export async function markStaleRunDueWorkers(): Promise<RunDueWorkerInstance[]> {
  return postApi<RunDueWorkerInstance[]>("/run-due-worker/mark-stale", {});
}
