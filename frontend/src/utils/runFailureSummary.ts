/**
 * R11-S8-9-16 / B6: Run Detail failure one-line summary (FE-only).
 * Uses existing run detail / events / progress — no backend changes.
 */

import type {
  VisualPipelineRunEvent,
  VisualPipelineRunIssue,
  VisualPipelineRunProgress,
  VisualPipelineRunResponse,
} from "@/types/visualPipeline";

export type RunFailureSummarySeverity = "error" | "warning" | "info" | "none";

export type RunFailureSummarySource = "run" | "event" | "progress" | "issue" | "fallback";

export type RunFailureSummary = {
  severity: RunFailureSummarySeverity;
  title: string;
  stepName?: string;
  reason: string;
  hint?: string;
  source: RunFailureSummarySource;
};

const REASON_MAX = 200;
const FALLBACK_REASON = "상세 원인 정보가 없습니다. 아래 진행 이력·이슈를 확인하세요.";

const STEP_LABELS: Record<string, string> = {
  SOURCE_FETCH: "REST Source",
  TRANSFORM: "Transform",
  UPSERT_LOAD: "Upsert Load",
  VP_REST_API_SOURCE: "REST Source",
  VP_TRANSFORM: "Transform",
  VP_UPSERT_LOAD: "Upsert Load",
  VP_CRON_SCHEDULE: "Schedule",
  REST: "REST Source",
  rest_call: "REST Source",
  rest: "REST Source",
  run: "Run",
  COMPILE: "Compile",
  MATERIALIZE: "Materialization",
  /** Backend Korean STEP_LABELS → user-facing English aliases */
  "REST 데이터 조회": "REST Source",
  "변환 적용": "Transform",
  "적재 실행": "Upsert Load",
};

export function mapRunStepName(raw?: string | null): string | undefined {
  if (!raw) return undefined;
  const key = String(raw).trim();
  if (!key) return undefined;
  if (STEP_LABELS[key]) return STEP_LABELS[key];
  const upper = key.toUpperCase();
  if (STEP_LABELS[upper]) return STEP_LABELS[upper];
  if (/rest|source_fetch|data.?source/i.test(key)) return "REST Source";
  if (/transform/i.test(key)) return "Transform";
  if (/upsert|load/i.test(key)) return "Upsert Load";
  if (/cron|schedule/i.test(key)) return "Schedule";
  return key.length > 40 ? `${key.slice(0, 37)}…` : key;
}

function truncateReason(text: string, max = REASON_MAX): string {
  let cleaned = String(text || "").replace(/\s+/g, " ").trim();
  if (!cleaned) return "";
  // Avoid dumping stack traces into the one-line summary.
  if (/Traceback \(most recent call last\)/i.test(cleaned) || /\bat\s+\S+\(/i.test(cleaned)) {
    const firstLine = cleaned.split(/[.。]/).map((s) => s.trim()).find(Boolean) || cleaned;
    cleaned = firstLine.slice(0, max);
    if (cleaned.length >= max || cleaned !== firstLine) {
      return `${cleaned.slice(0, Math.min(cleaned.length, max - 1))}…`;
    }
    return `${cleaned} (상세는 이슈·이력 참고)`;
  }
  if (cleaned.length <= max) return cleaned;
  return `${cleaned.slice(0, max - 1)}…`;
}

function hintFor(codeOrMsg: string | undefined, status: string): string | undefined {
  const blob = `${codeOrMsg || ""}`.toLowerCase();
  if (/cancel|중단/.test(blob) || status === "CANCELLED") {
    return "중단 요청 사유와 단계 경계 반영 여부를 확인하세요.";
  }
  if (/table|물리|active|target.?table|not found|존재하지/.test(blob)) {
    return "표준 데이터셋이 ACTIVE인지, 물리 테이블이 생성되어 있는지 확인해 보세요.";
  }
  if (/unmapped|fail_load|mapping/.test(blob)) {
    return "Transform 매핑·unmapped_policy와 Source/Target 컬럼 정합성을 확인해 보세요.";
  }
  if (/rest|http|timeout|연결|응답|fetch|source/.test(blob)) {
    return "Data Source 연결·endpoint·응답 경로를 확인해 보세요.";
  }
  return undefined;
}

function pickIssue(issues: VisualPipelineRunIssue[] | undefined): VisualPipelineRunIssue | null {
  if (!issues?.length) return null;
  const errorish = issues.find((i) => String(i.severity || "").toUpperCase() === "ERROR");
  return errorish ?? issues[0] ?? null;
}

function latestEvent(
  events: VisualPipelineRunEvent[] | undefined,
  types: string[],
): VisualPipelineRunEvent | null {
  if (!events?.length) return null;
  const set = new Set(types.map((t) => t.toUpperCase()));
  for (let i = events.length - 1; i >= 0; i -= 1) {
    const ev = events[i];
    if (set.has(String(ev.event_type || "").toUpperCase())) return ev;
  }
  return null;
}

function noneSummary(): RunFailureSummary {
  return {
    severity: "none",
    title: "",
    reason: "",
    source: "fallback",
  };
}

/**
 * Build a diagnostic one-line failure summary for Run Detail.
 * Does not mutate run status or invent causes beyond available fields.
 */
export function buildRunFailureSummary(
  detail: VisualPipelineRunResponse | null | undefined,
  events?: VisualPipelineRunEvent[] | null,
  progress?: VisualPipelineRunProgress | null,
): RunFailureSummary {
  if (!detail) return noneSummary();
  const status = String(detail.run_status || "").toUpperCase();

  if (status === "SUCCESS" || status === "RUNNING" || status === "PENDING" || !status) {
    return noneSummary();
  }

  if (status === "CANCELLED") {
    const cancelEv = latestEvent(events ?? undefined, ["RUN_CANCELLED", "RUN_CANCEL_REQUESTED"]);
    const stepName =
      mapRunStepName(cancelEv?.step_name) ||
      mapRunStepName(cancelEv?.step_key) ||
      mapRunStepName(progress?.current_step_name) ||
      mapRunStepName(progress?.current_step_key);
    const rawReason =
      detail.cancel_reason ||
      cancelEv?.message ||
      detail.error_message ||
      FALLBACK_REASON;
    const reason = truncateReason(rawReason) || FALLBACK_REASON;
    return {
      severity: "info",
      title: stepName ? `${stepName} 단계 취소` : "실행 취소",
      stepName,
      reason,
      hint: hintFor(`${detail.cancel_reason || ""} ${reason}`, status),
      source: detail.cancel_reason
        ? "run"
        : cancelEv?.message
          ? "event"
          : detail.error_message
            ? "run"
            : "fallback",
    };
  }

  const severity: RunFailureSummarySeverity = status === "PARTIAL" ? "warning" : "error";
  const titleVerb = status === "PARTIAL" ? "부분 성공·경고" : "실패";

  const issue = pickIssue(detail.issues);
  if (issue && (issue.message || issue.code)) {
    const stepName =
      mapRunStepName(issue.step_id) ||
      mapRunStepName(issue.phase) ||
      mapRunStepName(issue.node_id) ||
      mapRunStepName(progress?.current_step_name) ||
      mapRunStepName(progress?.current_step_key);
    const reason =
      truncateReason(String(issue.message || issue.code || "")) || FALLBACK_REASON;
    return {
      severity,
      title: stepName ? `${stepName} 단계 ${titleVerb}` : `실행 ${titleVerb}`,
      stepName,
      reason,
      hint: hintFor(`${issue.code || ""} ${reason}`, status),
      source: "issue",
    };
  }

  const failedEv = latestEvent(events ?? undefined, ["RUN_FAILED"]);
  if (failedEv && (failedEv.message || failedEv.step_key || failedEv.step_name)) {
    const stepName =
      mapRunStepName(failedEv.step_name) ||
      mapRunStepName(failedEv.step_key) ||
      mapRunStepName(progress?.current_step_name) ||
      mapRunStepName(progress?.current_step_key);
    const reason = truncateReason(String(failedEv.message || detail.error_message || "")) || FALLBACK_REASON;
    return {
      severity,
      title: stepName ? `${stepName} 단계 ${titleVerb}` : `실행 ${titleVerb}`,
      stepName,
      reason,
      hint: hintFor(reason, status),
      source: failedEv.message ? "event" : "run",
    };
  }

  if (detail.error_message) {
    const stepName =
      mapRunStepName(progress?.current_step_name) || mapRunStepName(progress?.current_step_key);
    const reason = truncateReason(detail.error_message) || FALLBACK_REASON;
    return {
      severity,
      title: stepName ? `${stepName} 단계 ${titleVerb}` : `실행 ${titleVerb}`,
      stepName,
      reason,
      hint: hintFor(reason, status),
      source: "run",
    };
  }

  const stepName =
    mapRunStepName(progress?.current_step_name) || mapRunStepName(progress?.current_step_key);
  return {
    severity,
    title: stepName ? `${stepName} 단계 ${titleVerb}` : `실행 ${titleVerb}`,
    stepName,
    reason: FALLBACK_REASON,
    hint: stepName
      ? "해당 단계 근처에서 중단되었을 수 있습니다. 진행 이력을 확인하세요."
      : undefined,
    source: stepName ? "progress" : "fallback",
  };
}
