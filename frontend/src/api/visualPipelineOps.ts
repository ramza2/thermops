import { fetchApi } from "@/api/client";
import type {
  VisualPipelineAuditLogsParams,
  VisualPipelineAuditLogsResponse,
  VisualPipelineOpsStuckRunsParams,
  VisualPipelineOpsStuckRunsResponse,
  VisualPipelineOpsSummary,
} from "@/types/visualPipelineOps";

/** R11-S7-12/S7-13 — consume S7-10 ops + S7-13 audit read APIs. */

export async function getVisualPipelineOpsSummary(params?: {
  pending_age_seconds?: number;
  running_lock_grace_seconds?: number;
}): Promise<VisualPipelineOpsSummary> {
  return fetchApi<VisualPipelineOpsSummary>(
    "/visual-pipeline-ops/summary",
    params as Record<string, unknown> | undefined,
  );
}

export async function getVisualPipelineOpsStuckRuns(
  params?: VisualPipelineOpsStuckRunsParams,
): Promise<VisualPipelineOpsStuckRunsResponse> {
  return fetchApi<VisualPipelineOpsStuckRunsResponse>(
    "/visual-pipeline-ops/stuck-runs",
    params as Record<string, unknown> | undefined,
  );
}

export async function getVisualPipelineOpsAuditLogs(
  params?: VisualPipelineAuditLogsParams,
): Promise<VisualPipelineAuditLogsResponse> {
  return fetchApi<VisualPipelineAuditLogsResponse>(
    "/visual-pipeline-ops/audit-logs",
    params as Record<string, unknown> | undefined,
  );
}
