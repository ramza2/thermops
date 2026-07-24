import { fetchApi } from "@/api/client";
import type {
  VisualPipelineOpsStuckRunsParams,
  VisualPipelineOpsStuckRunsResponse,
  VisualPipelineOpsSummary,
} from "@/types/visualPipelineOps";

/** R11-S7-12 — consume S7-10 read-only ops APIs. */

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
