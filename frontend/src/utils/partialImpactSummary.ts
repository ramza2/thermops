/** R11-S8-9-20 / B8: PARTIAL impact / retry-precheck summary (FE-only).
 *
 * Does not analyze physical duplicates, mutate tables, or enqueue retry.
 */

import { parseConflictKeyColumns } from "@/utils/conflictKeyValidation";
import { mapRunStepName } from "@/utils/runFailureSummary";
import type {
  VisualPipelineGraph,
  VisualPipelineGraphNode,
  VisualPipelineRunEvent,
  VisualPipelineRunProgress,
  VisualPipelineRunResponse,
} from "@/types/visualPipeline";

export type PartialImpactSeverity = "warning" | "info" | "none";
export type PartialDuplicateRisk = "low" | "medium" | "unknown";
export type PartialImpactSource = "run" | "event" | "progress" | "config" | "fallback";

export type PartialImpactRowHints = {
  fetched?: number;
  inserted?: number;
  updated?: number;
  skipped?: number;
  failed?: number;
};

export type PartialImpactSummary = {
  severity: PartialImpactSeverity;
  title: string;
  reason: string;
  completedSteps?: string[];
  stoppedAtStep?: string;
  rowHints?: PartialImpactRowHints;
  duplicateRisk: PartialDuplicateRisk;
  duplicateRiskLabel: string;
  duplicateRiskReason: string;
  conflictKeys?: string[];
  writeMode?: string;
  targetTable?: string;
  checklist: string[];
  source: PartialImpactSource;
};

export type PartialImpactConfigHints = {
  conflictKeys?: string[] | null;
  writeMode?: string | null;
  /** When true, graph was loaded but no Upsert keys found. */
  graphChecked?: boolean;
};

export const PARTIAL_IMPACT_CHECKLIST: string[] = [
  "실패 요약에서 중단 단계와 reason 확인",
  "Studio Upsert Inspector의 Target Table sample rows에서 일부 적재 여부 확인",
  "conflict_key_columns_json이 최신 target 컬럼 기준으로 설정되어 있는지 확인",
  "동일 scheduled_at/run이 이미 생성되어 있는지 Run History 확인",
  "필요한 경우 Retry 실행 전 원천 데이터 중복 가능성 확인",
];

const FALLBACK_REASON =
  "일부 처리 여부를 판단할 정보가 부족합니다. Target Preview와 Upsert 기준키를 확인하세요.";

function noneSummary(): PartialImpactSummary {
  return {
    severity: "none",
    title: "",
    reason: "",
    duplicateRisk: "unknown",
    duplicateRiskLabel: "",
    duplicateRiskReason: "",
    checklist: [],
    source: "fallback",
  };
}

function asNumber(value: unknown): number | undefined {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string" && value.trim() !== "" && Number.isFinite(Number(value))) {
    return Number(value);
  }
  return undefined;
}

function resultRecord(detail: VisualPipelineRunResponse): Record<string, unknown> {
  const result = detail.result;
  if (result && typeof result === "object" && !Array.isArray(result)) {
    return result as Record<string, unknown>;
  }
  return {};
}

function extractRowHints(result: Record<string, unknown>): PartialImpactRowHints | undefined {
  const hints: PartialImpactRowHints = {};
  const fetched = asNumber(result.fetched_count);
  const inserted = asNumber(result.inserted_count);
  const updated = asNumber(result.updated_count);
  const skipped = asNumber(result.skipped_count);
  const failed = asNumber(result.failed_count);
  if (fetched != null) hints.fetched = fetched;
  if (inserted != null) hints.inserted = inserted;
  if (updated != null) hints.updated = updated;
  if (skipped != null) hints.skipped = skipped;
  if (failed != null) hints.failed = failed;
  return Object.keys(hints).length ? hints : undefined;
}

function hasPositiveLoad(hints?: PartialImpactRowHints): boolean {
  if (!hints) return false;
  return (
    (hints.inserted != null && hints.inserted > 0) ||
    (hints.updated != null && hints.updated > 0) ||
    (hints.fetched != null && hints.fetched > 0)
  );
}

function completedAndStopped(
  progress: VisualPipelineRunProgress | null | undefined,
  events: VisualPipelineRunEvent[] | undefined,
): { completed: string[]; stopped?: string; source: PartialImpactSource } {
  const completed: string[] = [];
  if (progress?.steps?.length) {
    for (const step of progress.steps) {
      if (String(step.status || "").toLowerCase() === "completed") {
        const label = mapRunStepName(step.step_name) || mapRunStepName(step.step_key) || step.step_key;
        if (label) completed.push(label);
      }
    }
  }
  if (!completed.length && events?.length) {
    for (const ev of events) {
      if (String(ev.event_type || "").toUpperCase() === "STEP_COMPLETED") {
        const label = mapRunStepName(ev.step_name) || mapRunStepName(ev.step_key);
        if (label && !completed.includes(label)) completed.push(label);
      }
    }
  }

  const stopped =
    mapRunStepName(progress?.current_step_name) ||
    mapRunStepName(progress?.current_step_key) ||
    (() => {
      if (!events?.length) return undefined;
      for (let i = events.length - 1; i >= 0; i -= 1) {
        const t = String(events[i].event_type || "").toUpperCase();
        if (t === "RUN_FAILED" || t === "STEP_STARTED" || t === "LOAD_FINALIZE") {
          return mapRunStepName(events[i].step_name) || mapRunStepName(events[i].step_key);
        }
      }
      return undefined;
    })();

  const source: PartialImpactSource = progress?.steps?.length
    ? "progress"
    : events?.length
      ? "event"
      : "fallback";
  return { completed, stopped, source };
}

function riskLabel(risk: PartialDuplicateRisk): string {
  if (risk === "low") return "기준키 있음 · 확인 권장";
  if (risk === "medium") return "확인 필요";
  return "판단 정보 부족";
}

function assessDuplicateRisk(args: {
  conflictKeys: string[];
  writeMode?: string;
  targetTable?: string;
  rowHints?: PartialImpactRowHints;
}): { risk: PartialDuplicateRisk; reason: string } {
  const { conflictKeys, writeMode, targetTable, rowHints } = args;
  const mode = String(writeMode || "").toUpperCase();
  const loadHint = hasPositiveLoad(rowHints);

  if (conflictKeys.length > 0) {
    return {
      risk: loadHint ? "medium" : "low",
      reason: loadHint
        ? "기준키가 설정되어 있어 retry 시 중복 방지 기준이 있습니다. 다만 일부 row가 이미 적재되었을 수 있으므로 Target Preview와 정합성을 확인하세요."
        : "기준키가 설정되어 있어 retry 시 중복 방지 기준이 있습니다. 그래도 source/target 정합성과 target table 상태는 확인해야 합니다.",
    };
  }

  if (/UPSERT|DEDUPLICATE|MERGE/.test(mode)) {
    return {
      risk: "medium",
      reason:
        "Upsert/중복 처리 모드이지만 기준키를 확인할 수 없습니다. Studio Upsert 설정에서 conflict_key_columns_json을 확인하세요.",
    };
  }

  if (!targetTable && !rowHints) {
    return {
      risk: "unknown",
      reason: "target table과 적재 건수 정보가 없어 영향 범위를 판단하기 어렵습니다.",
    };
  }

  if (loadHint) {
    return {
      risk: "medium",
      reason:
        "일부 row가 이미 적재되었을 수 있습니다. Retry 전 Target Preview와 conflict key 설정을 확인하세요.",
    };
  }

  return {
    risk: "unknown",
    reason: FALLBACK_REASON,
  };
}

function nodeComponentType(node: VisualPipelineGraphNode): string {
  const data = (node.data || {}) as Record<string, unknown>;
  return String(data.component_type || node.type || "").toUpperCase();
}

function nodeConfig(node: VisualPipelineGraphNode): Record<string, unknown> {
  const data = (node.data || {}) as Record<string, unknown>;
  const cfg = data.config;
  if (cfg && typeof cfg === "object" && !Array.isArray(cfg)) {
    return cfg as Record<string, unknown>;
  }
  return {};
}

/** Best-effort Upsert config from pipeline graph (existing GET pipeline). */
export function extractUpsertHintsFromGraph(graph: VisualPipelineGraph | null | undefined): {
  conflictKeys: string[];
  writeMode?: string;
  targetTable?: string;
} {
  if (!graph?.nodes?.length) return { conflictKeys: [] };
  for (const node of graph.nodes) {
    const ctype = nodeComponentType(node);
    if (!(ctype === "VP_UPSERT_LOAD" || ctype.includes("UPSERT_LOAD") || ctype === "UPSERT")) {
      continue;
    }
    const cfg = nodeConfig(node);
    const keys = parseConflictKeyColumns(cfg.conflict_key_columns_json);
    const writeMode = cfg.write_mode != null ? String(cfg.write_mode) : undefined;
    const targetTable =
      cfg.target_table != null && String(cfg.target_table).trim()
        ? String(cfg.target_table).trim()
        : undefined;
    return { conflictKeys: keys, writeMode, targetTable };
  }
  return { conflictKeys: [] };
}

/**
 * Build PARTIAL-only impact summary for Run Detail.
 * Returns severity "none" for non-PARTIAL statuses.
 */
export function buildPartialImpactSummary(
  detail: VisualPipelineRunResponse | null | undefined,
  events?: VisualPipelineRunEvent[] | null,
  progress?: VisualPipelineRunProgress | null,
  configHints?: PartialImpactConfigHints | null,
): PartialImpactSummary {
  if (!detail) return noneSummary();
  const status = String(detail.run_status || "").toUpperCase();
  if (status !== "PARTIAL") return noneSummary();

  const result = resultRecord(detail);
  const rowHints = extractRowHints(result);
  const targetFromResult =
    result.target_table != null && String(result.target_table).trim()
      ? String(result.target_table).trim()
      : undefined;
  const conflictKeys = (configHints?.conflictKeys || []).filter(Boolean);
  const writeMode = configHints?.writeMode ? String(configHints.writeMode) : undefined;
  const targetTable = targetFromResult;

  const { completed, stopped, source: stepSource } = completedAndStopped(
    progress ?? null,
    events ?? undefined,
  );

  const { risk, reason: riskReason } = assessDuplicateRisk({
    conflictKeys,
    writeMode,
    targetTable,
    rowHints,
  });

  let reason = "";
  let source: PartialImpactSource = "fallback";
  if (hasPositiveLoad(rowHints) || targetTable) {
    reason = hasPositiveLoad(rowHints)
      ? "일부 단계가 완료된 뒤 실행이 중단되었을 수 있으며, 일부 row가 이미 적재되었을 수 있습니다."
      : "일부 단계가 완료된 뒤 실행이 중단되었을 수 있습니다. Retry 전 대상 테이블과 기준키를 확인하세요.";
    source = "run";
  } else if (stopped || completed.length) {
    reason = "일부 단계가 완료된 뒤 실행이 중단되었을 수 있습니다. Retry 전 영향 범위를 확인하세요.";
    source = stepSource;
  } else if (detail.error_message || (detail.issues && detail.issues.length > 0)) {
    reason = "부분 완료 상태입니다. 실패 요약과 진행 이력을 확인한 뒤 Retry 여부를 판단하세요.";
    source = "run";
  } else {
    reason = FALLBACK_REASON;
    source = "fallback";
  }

  if (conflictKeys.length) source = source === "fallback" ? "config" : source;

  return {
    severity: "warning",
    title: "PARTIAL 영향 확인",
    reason,
    completedSteps: completed.length ? completed : undefined,
    stoppedAtStep: stopped,
    rowHints,
    duplicateRisk: risk,
    duplicateRiskLabel: riskLabel(risk),
    duplicateRiskReason: riskReason,
    conflictKeys: conflictKeys.length ? conflictKeys : undefined,
    writeMode,
    targetTable,
    checklist: [...PARTIAL_IMPACT_CHECKLIST],
    source,
  };
}
