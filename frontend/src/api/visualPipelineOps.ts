import { extractApiErrorMessage, fetchApi, postApi } from "@/api/client";
import type {
  MarkVisualPipelineRunFailedRequest,
  MarkVisualPipelineRunFailedResponse,
  VisualPipelineAuditLogsParams,
  VisualPipelineAuditLogsResponse,
  VisualPipelineOpsStuckRunsParams,
  VisualPipelineOpsStuckRunsResponse,
  VisualPipelineOpsSummary,
} from "@/types/visualPipelineOps";

/** R11-S7-12/S7-13/S7-14 — ops summary/stuck/audit + mark-failed. */

const MARK_FAILED_MESSAGES: Record<string, string> = {
  VP_ADMIN_ACTIONS_DISABLED: "Admin Action 기능이 비활성화되어 있습니다.",
  RUN_MARK_FAILED_CONFIRM_MISMATCH: "Run ID 확인값이 일치하지 않습니다.",
  RUN_MARK_FAILED_REASON_INVALID: "사유는 5자 이상 200자 이하여야 합니다.",
  RUN_MARK_FAILED_NOT_ELIGIBLE:
    "현재 상태에서는 실패 처리할 수 없습니다. 목록을 새로고침하세요.",
  RUN_MARK_FAILED_AUDIT_REQUIRED_FAILED:
    "Audit 기록 실패로 실패 처리가 취소되었습니다.",
  VISUAL_PIPELINE_RUN_NOT_FOUND: "Run을 찾을 수 없습니다.",
};

export function markFailedErrorMessage(err: unknown, fallback?: string): string {
  const raw = (err as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail;
  if (typeof raw === "string" && MARK_FAILED_MESSAGES[raw]) {
    return MARK_FAILED_MESSAGES[raw];
  }
  return extractApiErrorMessage(
    err,
    fallback ?? "실패 처리 요청에 실패했습니다.",
  );
}

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

export async function markVisualPipelineStuckRunFailed(
  visualRunId: string,
  payload: MarkVisualPipelineRunFailedRequest,
): Promise<MarkVisualPipelineRunFailedResponse> {
  return postApi<MarkVisualPipelineRunFailedResponse>(
    `/visual-pipeline-ops/stuck-runs/${encodeURIComponent(visualRunId)}/mark-failed`,
    payload,
  );
}
