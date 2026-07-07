import { fetchApi, postApi, putApi } from "@/api/client";
import type { DataLoadSchedule, DataLoadScheduleRun } from "@/types/dataLoadSchedule";

export async function listDataLoadSchedules(params?: Record<string, string | boolean>): Promise<DataLoadSchedule[]> {
  const q = new URLSearchParams();
  if (params) {
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined && v !== "") q.set(k, String(v));
    });
  }
  const suffix = q.toString() ? `?${q.toString()}` : "";
  return fetchApi(`/data-load-schedules${suffix}`);
}

export async function createDataLoadSchedule(body: Record<string, unknown>): Promise<DataLoadSchedule> {
  return postApi("/data-load-schedules", body);
}

export async function updateDataLoadSchedule(scheduleId: string, body: Record<string, unknown>): Promise<DataLoadSchedule> {
  return putApi(`/data-load-schedules/${encodeURIComponent(scheduleId)}`, body);
}

export async function activateDataLoadSchedule(scheduleId: string): Promise<DataLoadSchedule> {
  return postApi(`/data-load-schedules/${encodeURIComponent(scheduleId)}/activate`, {});
}

export async function deactivateDataLoadSchedule(scheduleId: string): Promise<DataLoadSchedule> {
  return postApi(`/data-load-schedules/${encodeURIComponent(scheduleId)}/deactivate`, {});
}

export async function runDataLoadScheduleNow(scheduleId: string, manualParams?: Record<string, unknown>): Promise<DataLoadScheduleRun> {
  return postApi(`/data-load-schedules/${encodeURIComponent(scheduleId)}/run-now`, { manual_params: manualParams });
}

export async function listDueDataLoadSchedules(): Promise<DataLoadSchedule[]> {
  return fetchApi("/data-load-schedules/due");
}

export async function runDueDataLoadSchedules(): Promise<Record<string, unknown>> {
  return postApi("/data-load-schedules/run-due", {});
}

export async function listDataLoadScheduleRuns(params?: Record<string, string>): Promise<DataLoadScheduleRun[]> {
  const q = new URLSearchParams(params);
  const suffix = q.toString() ? `?${q.toString()}` : "";
  return fetchApi(`/data-load-schedule-runs${suffix}`);
}

export async function retryDataLoadScheduleRun(runId: string): Promise<DataLoadScheduleRun> {
  return postApi(`/data-load-schedule-runs/${encodeURIComponent(runId)}/retry`, {});
}

export async function previewNextRun(body: Record<string, unknown>) {
  return postApi("/data-load-schedules/preview-next-run", body);
}

export async function renderRuntimeParams(body: Record<string, unknown>) {
  return postApi("/data-load-schedules/render-runtime-params", body);
}
