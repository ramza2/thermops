/** B27: FE-only conflict_key_columns_json selection helpers (recommend + validate). */

import {
  compareColumnDataTypes,
  normalizeColumnName,
  type PreviewColumn,
} from "@/utils/columnNormalizationPreview";

export const CONFLICT_KEYS_HINT =
  "같은 데이터인지 판단할 기준 컬럼입니다. 선택한 컬럼 조합이 같으면 update, 없으면 insert됩니다.";

export const CONFLICT_KEYS_RECOMMEND_HINT =
  "추천은 후보일 뿐이며 자동 저장되지 않습니다. 실제 upsert 기준키는 사용자가 선택한 conflict_key_columns_json만 저장됩니다.";

export type ConflictKeySeverity = "OK" | "WARNING" | "ERROR" | "UNKNOWN";

export type ConflictKeyIssueCode =
  | "TARGET_FOUND"
  | "TARGET_MISSING"
  | "SOURCE_FOUND"
  | "SOURCE_MISSING"
  | "NULLABLE_WARNING"
  | "TYPE_MISMATCH_WARNING"
  | "DUPLICATE_KEY"
  | "UNKNOWN_COLUMN"
  | "NO_KEYS_REQUIRED";

export type ConflictKeyColumnCheck = {
  key: string;
  severity: ConflictKeySeverity;
  target_status: "TARGET_FOUND" | "TARGET_MISSING" | "UNKNOWN_COLUMN";
  source_status: "SOURCE_FOUND" | "SOURCE_MISSING" | "UNKNOWN_COLUMN";
  notes: string[];
};

export type ConflictKeyValidationResult = {
  overall: ConflictKeySeverity;
  checks: ConflictKeyColumnCheck[];
  orphan_keys: string[];
  empty_keys_error: boolean;
  message: string;
};

export type ConflictKeyCandidate = {
  id: string;
  keys: string[];
  label: string;
  reason: string;
};

export function parseConflictKeyColumns(value: unknown): string[] {
  if (value == null) return [];
  if (Array.isArray(value)) {
    return value.map((v) => String(v).trim()).filter(Boolean);
  }
  if (typeof value === "string") {
    return value
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean);
  }
  return [];
}

function findByNormalized(columns: PreviewColumn[], key: string): PreviewColumn | undefined {
  const norm = normalizeColumnName(key);
  if (!norm) return undefined;
  return columns.find((c) => normalizeColumnName(c.column_name) === norm);
}

function hasNormalized(columns: PreviewColumn[], key: string): boolean {
  return Boolean(findByNormalized(columns, key));
}

function patternScore(name: string): number {
  const n = name.toLowerCase();
  if (
    n === "measured_at" ||
    n === "observed_at" ||
    n === "calendar_date" ||
    n === "date" ||
    n === "hour"
  ) {
    return 3;
  }
  if (n.endsWith("_id") || n.endsWith("_code")) return 2;
  return 0;
}

function dedupeCandidates(candidates: ConflictKeyCandidate[]): ConflictKeyCandidate[] {
  const seen = new Set<string>();
  const out: ConflictKeyCandidate[] = [];
  for (const c of candidates) {
    const sig = c.keys.map((k) => normalizeColumnName(k)).join("|");
    if (!sig || seen.has(sig)) continue;
    seen.add(sig);
    out.push(c);
  }
  return out;
}

function presetPairs(transformType: string): string[][] {
  switch (String(transformType || "").toUpperCase()) {
    case "WIDE_HOUR_TO_LONG":
      return [
        ["entity_id", "measured_at"],
        ["site_id", "measured_at"],
        ["external_node_id", "measured_at"],
      ];
    case "ASOS_HOURLY_TO_CANONICAL":
      return [["station_code", "observed_at"]];
    case "CALENDAR_DATE_TO_HOUR":
      return [["calendar_date", "hour"]];
    case "CALENDAR_SPECIAL_DAY_TO_DATE":
      return [
        ["calendar_date", "special_day_type"],
        ["calendar_date", "holiday_name"],
      ];
    default:
      return [];
  }
}

/** Recommendation only — never auto-applied. */
export function suggestConflictKeyCandidates(input: {
  targetColumns: PreviewColumn[];
  sourceColumns: PreviewColumn[];
  transformType?: string;
}): ConflictKeyCandidate[] {
  const { targetColumns, sourceColumns, transformType } = input;
  if (!targetColumns.length) return [];

  const candidates: ConflictKeyCandidate[] = [];

  for (const pair of presetPairs(transformType || "")) {
    if (pair.every((k) => hasNormalized(targetColumns, k))) {
      candidates.push({
        id: `preset:${pair.join("+")}`,
        keys: pair.map((k) => findByNormalized(targetColumns, k)!.column_name),
        label: pair.join(" + "),
        reason: `Transform(${String(transformType || "").toUpperCase()}) 프리셋`,
      });
    }
  }

  const requiredBoth = targetColumns.filter(
    (t) => t.required && hasNormalized(sourceColumns, t.column_name),
  );
  if (requiredBoth.length >= 2) {
    const keys = requiredBoth.slice(0, 2).map((c) => c.column_name);
    candidates.push({
      id: `required:${keys.join("+")}`,
      keys,
      label: keys.join(" + "),
      reason: "필수 Target + Source 존재",
    });
  } else if (requiredBoth.length === 1) {
    const timed = targetColumns.find(
      (t) => patternScore(t.column_name) >= 3 && hasNormalized(sourceColumns, t.column_name),
    );
    if (timed) {
      const keys = [requiredBoth[0].column_name, timed.column_name];
      candidates.push({
        id: `required-time:${keys.join("+")}`,
        keys,
        label: keys.join(" + "),
        reason: "필수 컬럼 + 시간 패턴",
      });
    }
  }

  const patterned = targetColumns
    .filter((t) => patternScore(t.column_name) > 0 && hasNormalized(sourceColumns, t.column_name))
    .sort((a, b) => patternScore(b.column_name) - patternScore(a.column_name));
  if (patterned.length >= 2) {
    const keys = patterned.slice(0, 2).map((c) => c.column_name);
    candidates.push({
      id: `pattern:${keys.join("+")}`,
      keys,
      label: keys.join(" + "),
      reason: "이름 패턴(*_id / 시간)",
    });
  }

  return dedupeCandidates(candidates).slice(0, 6);
}

function worse(a: ConflictKeySeverity, b: ConflictKeySeverity): ConflictKeySeverity {
  const order: ConflictKeySeverity[] = ["OK", "UNKNOWN", "WARNING", "ERROR"];
  return order.indexOf(a) >= order.indexOf(b) ? a : b;
}

export function validateConflictKeys(input: {
  selectedKeys: string[];
  targetColumns: PreviewColumn[];
  sourceColumns: PreviewColumn[];
  writeMode: string;
  targetColumnsKnown: boolean;
  sourceColumnsKnown: boolean;
}): ConflictKeyValidationResult {
  const {
    selectedKeys,
    targetColumns,
    sourceColumns,
    writeMode,
    targetColumnsKnown,
    sourceColumnsKnown,
  } = input;

  const mode = String(writeMode || "").toUpperCase();
  const keysRequired = mode === "UPSERT" || mode === "DEDUPLICATE";
  const uniqueKeys = [...new Set(selectedKeys.map((k) => k.trim()).filter(Boolean))];
  const orphan_keys =
    targetColumnsKnown && targetColumns.length > 0
      ? uniqueKeys.filter((k) => !hasNormalized(targetColumns, k))
      : [];

  const empty_keys_error = keysRequired && uniqueKeys.length === 0;
  const checks: ConflictKeyColumnCheck[] = [];
  let overall: ConflictKeySeverity = "OK";

  if (empty_keys_error) {
    overall = "ERROR";
  }

  const seenNorm = new Set<string>();
  for (const key of uniqueKeys) {
    const notes: string[] = [];
    let severity: ConflictKeySeverity = "OK";
    const norm = normalizeColumnName(key);

    if (seenNorm.has(norm)) {
      severity = "ERROR";
      notes.push("중복 기준키");
      checks.push({
        key,
        severity,
        target_status: "TARGET_FOUND",
        source_status: "SOURCE_FOUND",
        notes,
      });
      overall = worse(overall, severity);
      continue;
    }
    seenNorm.add(norm);

    let target_status: ConflictKeyColumnCheck["target_status"] = "UNKNOWN_COLUMN";
    let source_status: ConflictKeyColumnCheck["source_status"] = "UNKNOWN_COLUMN";
    const targetCol = findByNormalized(targetColumns, key);
    const sourceCol = findByNormalized(sourceColumns, key);

    if (!targetColumnsKnown || targetColumns.length === 0) {
      target_status = "UNKNOWN_COLUMN";
      severity = worse(severity, "UNKNOWN");
      notes.push("Target 컬럼 목록을 확인할 수 없음");
    } else if (!targetCol) {
      target_status = "TARGET_MISSING";
      severity = "ERROR";
      notes.push("Target 컬럼 목록에 없음");
    } else {
      target_status = "TARGET_FOUND";
      if (targetCol.required === false) {
        severity = worse(severity, "WARNING");
        notes.push("Target nullable/비필수 컬럼");
      }
    }

    if (!sourceColumnsKnown || sourceColumns.length === 0) {
      source_status = "UNKNOWN_COLUMN";
      severity = worse(severity, "UNKNOWN");
      notes.push("Source 컬럼 목록을 확인할 수 없음");
    } else if (!sourceCol) {
      source_status = "SOURCE_MISSING";
      severity = worse(severity, "WARNING");
      notes.push("Source/Transform 출력에 대응 컬럼 없음");
    } else {
      source_status = "SOURCE_FOUND";
      if (targetCol) {
        const compat = compareColumnDataTypes(sourceCol.data_type, targetCol.data_type);
        if (compat === "mismatch" || compat === "warning") {
          severity = worse(severity, "WARNING");
          notes.push(
            `타입 확인 권장 (${sourceCol.data_type || "?"} ↔ ${targetCol.data_type || "?"})`,
          );
        }
      }
    }

    checks.push({ key, severity, target_status, source_status, notes });
    overall = worse(overall, severity);
  }

  let message = "기준키 검증 OK";
  if (empty_keys_error) {
    message = `${mode} 모드에서는 conflict_key_columns_json이 필요합니다.`;
  } else if (overall === "ERROR") {
    message = "기준키 검증 오류가 있습니다.";
  } else if (overall === "WARNING") {
    message = "기준키 검증 경고가 있습니다.";
  } else if (overall === "UNKNOWN") {
    message = "기준키를 완전히 검증하지 못했습니다.";
  }

  return { overall, checks, orphan_keys, empty_keys_error, message };
}
