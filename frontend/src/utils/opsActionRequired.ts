/**
 * R11-S8-9-17 / B10: Ops 「조치 필요」card grouping (FE-only).
 * Uses existing ops summary + stuck runs — no automated actions, no Notification badge.
 */

import type {
  VisualPipelineOpsRecentFailure,
  VisualPipelineOpsStuckRun,
  VisualPipelineOpsSummary,
} from "@/types/visualPipelineOps";

export type OpsActionSeverity = "error" | "warning" | "info";

export type OpsActionGroupId =
  | "stuck"
  | "failed"
  | "partial"
  | "retryable"
  | "catchup_hint";

export type OpsActionItem = {
  id: string;
  title: string;
  reason: string;
  pipelineId?: string | null;
  visualRunId?: string | null;
  meta?: string | null;
  /** Only stuck/failed items open Run Detail. */
  openDetail: boolean;
};

export type OpsActionGroup = {
  id: OpsActionGroupId;
  severity: OpsActionSeverity;
  label: string;
  count: number;
  items: OpsActionItem[];
};

export type OpsActionRequired = {
  empty: boolean;
  totalActionCount: number;
  groups: OpsActionGroup[];
  generatedAt?: string | null;
};

const REASON_MAX = 200;
const FAILED_LIST_LIMIT = 5;
const STUCK_LIST_LIMIT = 5;
const FALLBACK_FAIL_REASON = "상세에서 실패 원인 요약을 확인하세요.";

function truncateReason(text: string | null | undefined, max = REASON_MAX): string {
  const cleaned = String(text || "")
    .replace(/\s+/g, " ")
    .trim();
  if (!cleaned) return "";
  if (/Traceback \(most recent call last\)/i.test(cleaned)) {
    return FALLBACK_FAIL_REASON;
  }
  if (cleaned.length <= max) return cleaned;
  return `${cleaned.slice(0, max - 1)}…`;
}

function stuckReasonLabel(reason: string | undefined): string {
  const r = String(reason || "").toUpperCase();
  if (r === "PENDING_TOO_OLD") return "PENDING이 임계 시간보다 오래 유지됨";
  if (r === "RUNNING_LOCK_EXPIRED") return "RUNNING lock/heartbeat가 만료됨";
  return reason || "장시간 미완료 실행";
}

export function buildOpsActionRequired(input: {
  summary: VisualPipelineOpsSummary | null | undefined;
  stuckItems?: VisualPipelineOpsStuckRun[] | null;
}): OpsActionRequired {
  const summary = input.summary;
  if (!summary) {
    return { empty: true, totalActionCount: 0, groups: [], generatedAt: null };
  }

  const stuckItems = input.stuckItems ?? [];
  const failures = summary.recent_failures ?? [];
  const counts = summary.run_status_counts ?? {};
  const failedCount = Number(counts.FAILED ?? failures.length ?? 0);
  const partialCount = Number(counts.PARTIAL ?? 0);
  const stuckSummaryCount =
    Number(summary.stuck_summary?.pending_older_than_threshold ?? 0) +
    Number(summary.stuck_summary?.running_lock_expired ?? 0);
  const stuckCount = Math.max(stuckItems.length, stuckSummaryCount);
  const skipAt = summary.activity_hints?.latest_last_skip_at ?? null;

  const groups: OpsActionGroup[] = [];

  // 1) Stuck
  {
    const items: OpsActionItem[] = stuckItems.slice(0, STUCK_LIST_LIMIT).map((row) => ({
      id: `stuck-${row.visual_run_id}`,
      title: `${row.run_status} · ${row.visual_run_id}`,
      reason: stuckReasonLabel(String(row.reason)),
      pipelineId: row.pipeline_id,
      visualRunId: row.visual_run_id,
      meta:
        row.age_seconds != null
          ? `age=${row.age_seconds}s · pipeline=${row.pipeline_id}`
          : `pipeline=${row.pipeline_id}`,
      openDetail: true,
    }));
    if (stuckCount > 0 || items.length > 0) {
      groups.push({
        id: "stuck",
        severity: "error",
        label: "장시간 실행 중 / Stuck",
        count: Math.max(stuckCount, items.length),
        items,
      });
    }
  }

  // 2) Failed
  {
    const items: OpsActionItem[] = failures.slice(0, FAILED_LIST_LIMIT).map((row: VisualPipelineOpsRecentFailure) => ({
      id: `failed-${row.visual_run_id}`,
      title: `FAILED · ${row.visual_run_id}`,
      reason: truncateReason(row.error_message) || FALLBACK_FAIL_REASON,
      pipelineId: row.pipeline_id,
      visualRunId: row.visual_run_id,
      meta: row.finished_at ? `finished=${row.finished_at}` : `pipeline=${row.pipeline_id}`,
      openDetail: true,
    }));
    if (failedCount > 0 || items.length > 0) {
      groups.push({
        id: "failed",
        severity: "error",
        label: "실패",
        count: Math.max(failedCount, items.length),
        items,
      });
    }
  }

  // 3) Partial (count-only)
  if (partialCount > 0) {
    groups.push({
      id: "partial",
      severity: "warning",
      label: "부분 완료",
      count: partialCount,
      items: [
        {
          id: "partial-count",
          title: `PARTIAL ${partialCount}건`,
          reason:
            "부분 완료 Run이 있습니다. Run Detail에서 PARTIAL 영향·Retry 전 확인을 검토하세요. (목록 API 없음 · Studio 실행 이력에서도 확인 가능)",
          openDetail: false,
        },
      ],
    });
  }

  // 4) Retryable (count-only guidance — never enqueue retry from this card)
  const retryableCount = failedCount + partialCount;
  if (retryableCount > 0) {
    groups.push({
      id: "retryable",
      severity: "warning",
      label: "재시도 검토",
      count: retryableCount,
      items: [
        {
          id: "retryable-count",
          title: `FAILED/PARTIAL 합계 ${retryableCount}건`,
          reason:
            "상세 보기에서 재시도 가능 여부를 확인하세요. 이 카드에서는 재시도를 실행하지 않습니다.",
          openDetail: false,
        },
      ],
    });
  }

  // 5) Catch-up hint (skip activity only — no enqueue)
  if (skipAt) {
    groups.push({
      id: "catchup_hint",
      severity: "warning",
      label: "Catch-up 검토 힌트",
      count: 1,
      items: [
        {
          id: "catchup-skip-hint",
          title: "최근 스케줄 skip 활동",
          reason: `latest_last_skip_at=${skipAt}. Studio Catch-up 섹션에서 누락 후보를 검토하세요. 이 카드에서는 Catch-up을 실행하지 않습니다.`,
          openDetail: false,
          meta: skipAt,
        },
      ],
    });
  }

  const totalActionCount = groups.reduce((sum, g) => sum + g.count, 0);
  return {
    empty: totalActionCount === 0 || groups.length === 0,
    totalActionCount,
    groups,
    generatedAt: summary.generated_at ?? null,
  };
}
