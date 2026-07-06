const SECRET_KEYS = /servicekey|secret|authorization|api[_-]?key|token|password/i;

export function redactForDisplay(value: unknown): unknown {
  if (value === null || value === undefined) return value;
  if (Array.isArray(value)) return value.map(redactForDisplay);
  if (typeof value === "object") {
    const out: Record<string, unknown> = {};
    for (const [k, v] of Object.entries(value as Record<string, unknown>)) {
      out[k] = SECRET_KEYS.test(k) ? "****" : redactForDisplay(v);
    }
    return out;
  }
  return value;
}

export function safeJsonStringify(value: unknown, indent = 2): string {
  return JSON.stringify(redactForDisplay(value), null, indent);
}

export function extractDotPath(payload: unknown, path: string): unknown {
  if (!path?.trim()) return payload;
  let current: unknown = payload;
  for (const part of path.split(".")) {
    if (current === null || current === undefined) return undefined;
    if (typeof current !== "object") return undefined;
    current = (current as Record<string, unknown>)[part];
  }
  return current;
}

export function normalizePreviewItems(payload: unknown, path: string): Record<string, unknown>[] {
  const node = path ? extractDotPath(payload, path) : payload;
  if (node === undefined || node === null) return [];
  if (Array.isArray(node)) return node.filter((x) => x && typeof x === "object") as Record<string, unknown>[];
  if (typeof node === "object") return [node as Record<string, unknown>];
  return [];
}

export function computeColumnMatching(
  sourceFields: string[],
  targetColumns: string[],
): { rows: { source_field: string; target_column: string | null; status: string }[]; matched: number } {
  const targetSet = new Set(targetColumns);
  const matchedSources = new Set<string>();
  const rows = sourceFields.map((field) => {
    if (targetSet.has(field)) {
      matchedSources.add(field);
      return { source_field: field, target_column: field, status: "matched" };
    }
    return { source_field: field, target_column: null, status: "no_target" };
  });
  for (const col of targetColumns) {
    if (!matchedSources.has(col)) {
      rows.push({ source_field: "-", target_column: col, status: "unmapped_target" });
    }
  }
  return { rows, matched: matchedSources.size };
}
