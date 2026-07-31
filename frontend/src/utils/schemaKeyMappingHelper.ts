/**
 * R11-S8-9-22 / B3: Schema / Key Mapping Helper (FE-only summary).
 * Composes B15 match preview + B27 key recommend/validate. No auto-save / no schema mutation.
 */

import {
  COLUMN_MATCH_STATUS_LABEL,
  buildColumnMatchPreview,
  normalizeColumnName,
  type ColumnMatchLevel,
  type ColumnMatchPreviewResult,
  type PreviewColumn,
} from "@/utils/columnNormalizationPreview";
import {
  parseConflictKeyColumns,
  suggestConflictKeyCandidates,
  validateConflictKeys,
  type ConflictKeySeverity,
} from "@/utils/conflictKeyValidation";

export const SCHEMA_KEY_HELPER_HINT =
  "Source output과 Target schema를 비교해 Upsert 기준키 설정을 도와줍니다. 자동 저장되지 않으며, 적용 후에도 Graph 저장이 필요합니다.";

export const SCHEMA_KEY_HELPER_PREVIEW_HINT =
  "실제 적재 상태는 Target Table sample rows(Target Preview)에서 확인하세요.";

export type SchemaKeyMappingStatus =
  | "ready"
  | "partial"
  | "missing_source"
  | "missing_target"
  | "empty";

export type SchemaKeyMappingRow = {
  sourceColumn?: string;
  targetColumn?: string;
  normalizedName?: string;
  matchStatus: ColumnMatchLevel;
  matchLabel: string;
  sourceType?: string;
  targetType?: string;
  isCurrentKey: boolean;
  isRecommendedKey: boolean;
  message: string;
};

export type SchemaKeyCompareState = "match" | "differ" | "current_empty" | "recommend_empty";

export type SchemaKeyMappingSummary = {
  status: SchemaKeyMappingStatus;
  statusMessage: string;
  sourceColumnCount: number;
  targetColumnCount: number;
  matchedCount: number;
  unmatchedSourceCount: number;
  missingTargetCount: number;
  ambiguousCount: number;
  typeMismatchCount: number;
  currentConflictKeys: string[];
  recommendedConflictKeys: string[];
  keyRecommendationReason: string;
  keyCompareState: SchemaKeyCompareState;
  keyCompareMessage: string;
  keyValidationLevel: ConflictKeySeverity | "unknown";
  keyValidationMessage: string;
  canApplyRecommendedKeys: boolean;
  rows: SchemaKeyMappingRow[];
};

/** Generic time-series style pairs (not domain-hardcoded copy). */
const PRIORITY_KEY_PAIRS: string[][] = [
  ["entity_id", "measured_at"],
  ["external_node_id", "measured_at"],
  ["site_id", "measured_at"],
  ["id", "measured_at"],
  ["key", "measured_at"],
];

function findByNormalized(columns: PreviewColumn[], key: string): PreviewColumn | undefined {
  const norm = normalizeColumnName(key);
  if (!norm) return undefined;
  return columns.find((c) => normalizeColumnName(c.column_name) === norm);
}

function hasNormalized(columns: PreviewColumn[], key: string): boolean {
  return Boolean(findByNormalized(columns, key));
}

function sameKeySet(a: string[], b: string[]): boolean {
  if (a.length !== b.length) return false;
  const na = a.map((k) => normalizeColumnName(k)).filter(Boolean).sort();
  const nb = b.map((k) => normalizeColumnName(k)).filter(Boolean).sort();
  return na.every((k, i) => k === nb[i]);
}

function resolveCanonicalKeys(keys: string[], targetColumns: PreviewColumn[]): string[] {
  return keys.map((k) => findByNormalized(targetColumns, k)?.column_name ?? k);
}

function pickRecommendedKeys(input: {
  sourceColumns: PreviewColumn[];
  targetColumns: PreviewColumn[];
  transformType?: string;
}): { keys: string[]; reason: string } | null {
  const { sourceColumns, targetColumns, transformType } = input;
  if (!targetColumns.length) return null;

  for (const pair of PRIORITY_KEY_PAIRS) {
    if (pair.every((k) => hasNormalized(targetColumns, k) && hasNormalized(sourceColumns, k))) {
      return {
        keys: resolveCanonicalKeys(pair, targetColumns),
        reason: "Source·Target에 공통으로 존재하는 시계열형 기준키 패턴",
      };
    }
  }

  const candidates = suggestConflictKeyCandidates({
    targetColumns,
    sourceColumns,
    transformType,
  });

  for (const c of candidates) {
    if (c.keys.every((k) => hasNormalized(sourceColumns, k) && hasNormalized(targetColumns, k))) {
      return { keys: c.keys, reason: c.reason };
    }
  }

  if (candidates[0]) {
    return { keys: candidates[0].keys, reason: candidates[0].reason };
  }

  return null;
}

function statusFromCounts(input: {
  sourceCount: number;
  targetCount: number;
  ambiguous: number;
  typeMismatch: number;
  unmatched: number;
  missing: number;
}): { status: SchemaKeyMappingStatus; message: string } {
  const { sourceCount, targetCount, ambiguous, typeMismatch, unmatched, missing } = input;
  if (sourceCount === 0 && targetCount === 0) {
    return {
      status: "empty",
      message: "Standard Dataset과 upstream Transform을 먼저 설정하세요.",
    };
  }
  if (sourceCount === 0) {
    return {
      status: "missing_source",
      message: "Source Transform output을 확인하면 매핑 상태를 확인할 수 있습니다.",
    };
  }
  if (targetCount === 0) {
    return {
      status: "missing_target",
      message: "Target schema를 선택하면 매핑 상태를 확인할 수 있습니다.",
    };
  }
  if (ambiguous > 0 || typeMismatch > 0 || unmatched > 0 || missing > 0) {
    const parts: string[] = [];
    if (ambiguous > 0) parts.push("정규화 결과가 여러 target column과 매칭됩니다. 수동 확인이 필요합니다.");
    if (typeMismatch > 0) parts.push("이름은 매칭되지만 타입이 다릅니다. 변환 설정 또는 target schema를 확인하세요.");
    if (!parts.length) parts.push("일부 컬럼이 일치하지 않습니다. 수동 확인이 필요합니다.");
    return { status: "partial", message: parts.join(" ") };
  }
  return {
    status: "ready",
    message: "Source output과 Target schema 비교 결과입니다.",
  };
}

export function buildSchemaKeyMappingSummary(input: {
  sourceColumns: PreviewColumn[];
  targetColumns: PreviewColumn[];
  currentConflictKeys: string[] | unknown;
  transformType?: string;
  writeMode?: string;
  sourceColumnsKnown?: boolean;
  targetColumnsKnown?: boolean;
  matchPreview?: ColumnMatchPreviewResult | null;
}): SchemaKeyMappingSummary {
  const sourceColumns = input.sourceColumns ?? [];
  const targetColumns = input.targetColumns ?? [];
  const currentConflictKeys = parseConflictKeyColumns(input.currentConflictKeys);
  const sourceKnown = input.sourceColumnsKnown ?? sourceColumns.length > 0;
  const targetKnown = input.targetColumnsKnown ?? targetColumns.length > 0;

  const match =
    input.matchPreview ??
    buildColumnMatchPreview(sourceColumns, targetColumns);
  const summary = match.summary;
  const matchedCount = summary.exact + summary.normalized;

  const { status, message: statusMessage } = statusFromCounts({
    sourceCount: sourceKnown ? sourceColumns.length : 0,
    targetCount: targetKnown ? targetColumns.length : 0,
    ambiguous: summary.ambiguous,
    typeMismatch: summary.type_mismatch,
    unmatched: summary.unmatched_source,
    missing: summary.missing_target,
  });

  const picked =
    sourceColumns.length > 0 && targetColumns.length > 0
      ? pickRecommendedKeys({
          sourceColumns,
          targetColumns,
          transformType: input.transformType,
        })
      : null;

  const recommendedConflictKeys = picked?.keys ?? [];
  const keyRecommendationReason =
    picked?.reason ??
    (targetColumns.length === 0
      ? "Target schema가 없어 기준키를 추천할 수 없습니다."
      : sourceColumns.length === 0
        ? "Source output이 없어 기준키를 추천할 수 없습니다. Target 컬럼을 직접 선택하세요."
        : "표시할 추천 후보가 없습니다. Target 컬럼을 직접 선택하세요.");

  const validation = validateConflictKeys({
    selectedKeys: currentConflictKeys,
    targetColumns,
    sourceColumns,
    writeMode: input.writeMode || "UPSERT",
    targetColumnsKnown: targetKnown,
    sourceColumnsKnown: sourceKnown,
  });

  let keyCompareState: SchemaKeyCompareState;
  let keyCompareMessage: string;
  if (!recommendedConflictKeys.length && !currentConflictKeys.length) {
    keyCompareState = "recommend_empty";
    keyCompareMessage = "추천 후보가 없습니다. Target schema와 Source output을 확인하세요.";
  } else if (!currentConflictKeys.length && recommendedConflictKeys.length) {
    keyCompareState = "current_empty";
    keyCompareMessage =
      "Retry/Upsert 안정성을 위해 기준키 설정을 검토하세요.";
  } else if (
    recommendedConflictKeys.length &&
    sameKeySet(currentConflictKeys, recommendedConflictKeys)
  ) {
    keyCompareState = "match";
    keyCompareMessage = "현재 기준키가 추천과 일치합니다.";
  } else if (recommendedConflictKeys.length) {
    keyCompareState = "differ";
    keyCompareMessage =
      "현재 기준키가 추천 후보와 다릅니다. target schema와 source output을 확인하세요.";
  } else {
    keyCompareState = "recommend_empty";
    keyCompareMessage =
      currentConflictKeys.length > 0
        ? "추천 후보는 없지만 현재 기준키가 설정되어 있습니다. 검증 결과를 확인하세요."
        : "추천 후보가 없습니다.";
  }

  const currentNorm = new Set(currentConflictKeys.map((k) => normalizeColumnName(k)));
  const recommendNorm = new Set(recommendedConflictKeys.map((k) => normalizeColumnName(k)));

  const rows: SchemaKeyMappingRow[] = match.rows.map((row) => {
    const keyName = row.target_column || row.source_column || "";
    const norm = normalizeColumnName(keyName);
    const isCurrentKey = Boolean(norm && currentNorm.has(norm));
    const isRecommendedKey = Boolean(norm && recommendNorm.has(norm));
    return {
      sourceColumn: row.source_column,
      targetColumn: row.target_column,
      normalizedName: norm || undefined,
      matchStatus: row.level,
      matchLabel: COLUMN_MATCH_STATUS_LABEL[row.level],
      sourceType: row.source_type,
      targetType: row.target_type,
      isCurrentKey,
      isRecommendedKey,
      message: row.note || COLUMN_MATCH_STATUS_LABEL[row.level],
    };
  });

  const canApplyRecommendedKeys =
    recommendedConflictKeys.length > 0 &&
    !sameKeySet(currentConflictKeys, recommendedConflictKeys);

  return {
    status,
    statusMessage,
    sourceColumnCount: sourceColumns.length,
    targetColumnCount: targetColumns.length,
    matchedCount,
    unmatchedSourceCount: summary.unmatched_source,
    missingTargetCount: summary.missing_target,
    ambiguousCount: summary.ambiguous,
    typeMismatchCount: summary.type_mismatch,
    currentConflictKeys,
    recommendedConflictKeys,
    keyRecommendationReason,
    keyCompareState,
    keyCompareMessage,
    keyValidationLevel: validation.overall || "unknown",
    keyValidationMessage: validation.message,
    canApplyRecommendedKeys,
    rows,
  };
}

export function formatConflictKeysLabel(keys: string[]): string {
  return keys.length ? keys.join(" + ") : "(없음)";
}
