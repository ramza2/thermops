/** B15: FE-only Source ↔ Target column match preview (diagnosis, not saved mapping). */

export type PreviewColumn = {
  column_name: string;
  data_type?: string;
  required?: boolean;
};

export type ColumnMatchLevel =
  | "EXACT"
  | "NORMALIZED"
  | "UNMATCHED_SOURCE"
  | "MISSING_TARGET"
  | "TYPE_MISMATCH"
  | "AMBIGUOUS";

export type ColumnMatchRow = {
  source_column?: string;
  source_type?: string;
  target_column?: string;
  target_type?: string;
  level: ColumnMatchLevel;
  note?: string;
};

export type ColumnMatchSummary = {
  exact: number;
  normalized: number;
  unmatched_source: number;
  missing_target: number;
  type_mismatch: number;
  ambiguous: number;
};

export type ColumnMatchPreviewResult = {
  rows: ColumnMatchRow[];
  summary: ColumnMatchSummary;
};

export const COLUMN_MATCH_PREVIEW_HINT =
  "이 미리보기는 FE 정규화 규칙으로 계산한 진단 결과입니다. 실제 적재 정책은 compile/run 시점의 기존 pipeline 설정을 따릅니다. 컬럼명을 자동 변경하지 않습니다.";

export const COLUMN_MATCH_UNMAPPED_POLICY_HINT =
  "미매핑 컬럼 처리 방식은 Transform 설정의 unmapped_policy를 따릅니다.";

export const COLUMN_MATCH_STATUS_LABEL: Record<ColumnMatchLevel, string> = {
  EXACT: "일치",
  NORMALIZED: "정규화 일치",
  UNMATCHED_SOURCE: "Source만 있음",
  MISSING_TARGET: "Target 필수 누락",
  TYPE_MISMATCH: "타입 확인 필요",
  AMBIGUOUS: "중복 후보",
};

/** Comparison-only normalization. Does not rewrite real column names. */
export function normalizeColumnName(name: string): string {
  return name
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9가-힣]+/g, "_")
    .replace(/^_+|_+$/g, "");
}

function canonType(value: string | undefined): string {
  return String(value || "")
    .trim()
    .toUpperCase()
    .replace(/^STRING$/, "VARCHAR")
    .replace(/^JSON$/, "JSONB");
}

type TypeCompat = "compatible" | "warning" | "mismatch";

function compareDataTypes(sourceType: string | undefined, targetType: string | undefined): TypeCompat {
  const a = canonType(sourceType);
  const b = canonType(targetType);
  if (!a || !b) return "compatible";
  if (a === b) return "compatible";

  const pair = new Set([a, b]);
  const softPairs: Array<[string, string]> = [
    ["INTEGER", "NUMERIC"],
    ["BIGINT", "NUMERIC"],
    ["INTEGER", "BIGINT"],
    ["TIMESTAMP", "TIMESTAMPTZ"],
    ["VARCHAR", "TEXT"],
    ["JSONB", "VARCHAR"],
    ["JSONB", "TEXT"],
  ];
  for (const [x, y] of softPairs) {
    if (pair.has(x) && pair.has(y)) return "warning";
  }

  const numericFamily = new Set(["INTEGER", "BIGINT", "NUMERIC"]);
  const textFamily = new Set(["VARCHAR", "TEXT"]);
  const timeFamily = new Set(["DATE", "TIMESTAMP", "TIMESTAMPTZ"]);
  if (numericFamily.has(a) && numericFamily.has(b)) return "compatible";
  if (textFamily.has(a) && textFamily.has(b)) return "compatible";
  if (timeFamily.has(a) && timeFamily.has(b)) return "warning";

  if (
    (numericFamily.has(a) && textFamily.has(b)) ||
    (textFamily.has(a) && numericFamily.has(b)) ||
    (numericFamily.has(a) && timeFamily.has(b)) ||
    (timeFamily.has(a) && numericFamily.has(b)) ||
    (a === "BOOLEAN" && b !== "BOOLEAN") ||
    (b === "BOOLEAN" && a !== "BOOLEAN")
  ) {
    return "mismatch";
  }

  return "warning";
}

function emptySummary(): ColumnMatchSummary {
  return {
    exact: 0,
    normalized: 0,
    unmatched_source: 0,
    missing_target: 0,
    type_mismatch: 0,
    ambiguous: 0,
  };
}

function groupByNormalized(columns: PreviewColumn[]): Map<string, PreviewColumn[]> {
  const map = new Map<string, PreviewColumn[]>();
  for (const col of columns) {
    const name = col.column_name?.trim();
    if (!name) continue;
    const key = normalizeColumnName(name);
    if (!key) continue;
    const list = map.get(key) ?? [];
    list.push({ ...col, column_name: name });
    map.set(key, list);
  }
  return map;
}

function pushMatched(
  rows: ColumnMatchRow[],
  source: PreviewColumn,
  target: PreviewColumn,
  nameLevel: "EXACT" | "NORMALIZED",
): void {
  const typeCompat = compareDataTypes(source.data_type, target.data_type);
  if (typeCompat === "mismatch") {
    rows.push({
      source_column: source.column_name,
      source_type: source.data_type,
      target_column: target.column_name,
      target_type: target.data_type,
      level: "TYPE_MISMATCH",
      note: `${nameLevel === "EXACT" ? "이름 일치" : "정규화 일치"} · 타입 불일치 (${source.data_type || "?"} → ${target.data_type || "?"})`,
    });
    return;
  }
  rows.push({
    source_column: source.column_name,
    source_type: source.data_type,
    target_column: target.column_name,
    target_type: target.data_type,
    level: nameLevel,
    note:
      typeCompat === "warning"
        ? `타입 확인 권장 (${source.data_type || "?"} ↔ ${target.data_type || "?"})`
        : undefined,
  });
}

export function buildColumnMatchPreview(
  sourceColumns: PreviewColumn[],
  targetColumns: PreviewColumn[],
): ColumnMatchPreviewResult {
  const rows: ColumnMatchRow[] = [];
  const sourceGroups = groupByNormalized(sourceColumns);
  const targetGroups = groupByNormalized(targetColumns);
  const allKeys = new Set([...sourceGroups.keys(), ...targetGroups.keys()]);

  for (const key of [...allKeys].sort()) {
    const sources = sourceGroups.get(key) ?? [];
    const targets = targetGroups.get(key) ?? [];

    if (sources.length > 1 || targets.length > 1) {
      rows.push({
        source_column: sources.map((s) => s.column_name).join(", ") || undefined,
        source_type: sources.map((s) => s.data_type || "?").join(", ") || undefined,
        target_column: targets.map((t) => t.column_name).join(", ") || undefined,
        target_type: targets.map((t) => t.data_type || "?").join(", ") || undefined,
        level: "AMBIGUOUS",
        note: `정규화 키 "${key}"에 후보가 여러 개 있습니다.`,
      });
      continue;
    }

    if (sources.length === 1 && targets.length === 1) {
      const source = sources[0];
      const target = targets[0];
      const nameLevel = source.column_name === target.column_name ? "EXACT" : "NORMALIZED";
      pushMatched(rows, source, target, nameLevel);
      continue;
    }

    if (sources.length === 1 && targets.length === 0) {
      rows.push({
        source_column: sources[0].column_name,
        source_type: sources[0].data_type,
        level: "UNMATCHED_SOURCE",
        note: "Target에 대응 컬럼 없음",
      });
      continue;
    }

    if (sources.length === 0 && targets.length === 1) {
      const target = targets[0];
      if (target.required) {
        rows.push({
          target_column: target.column_name,
          target_type: target.data_type,
          level: "MISSING_TARGET",
          note: "필수 Target 컬럼에 Source 대응 없음",
        });
      }
    }
  }

  const summary = emptySummary();
  for (const row of rows) {
    switch (row.level) {
      case "EXACT":
        summary.exact += 1;
        break;
      case "NORMALIZED":
        summary.normalized += 1;
        break;
      case "UNMATCHED_SOURCE":
        summary.unmatched_source += 1;
        break;
      case "MISSING_TARGET":
        summary.missing_target += 1;
        break;
      case "TYPE_MISMATCH":
        summary.type_mismatch += 1;
        break;
      case "AMBIGUOUS":
        summary.ambiguous += 1;
        break;
    }
  }

  return { rows, summary };
}

export function formatUnmappedPolicyHint(policy: string | undefined): string | null {
  const p = String(policy || "").trim().toUpperCase();
  if (!p) return COLUMN_MATCH_UNMAPPED_POLICY_HINT;
  if (p === "FAIL_LOAD") {
    return `${COLUMN_MATCH_UNMAPPED_POLICY_HINT} 현재 값(FAIL_LOAD)이면 미매핑이 실행 실패로 이어질 수 있습니다.`;
  }
  if (p === "SKIP_UNMAPPED" || p === "LOG_ONLY") {
    return `${COLUMN_MATCH_UNMAPPED_POLICY_HINT} 현재 값(${p}).`;
  }
  return COLUMN_MATCH_UNMAPPED_POLICY_HINT;
}
