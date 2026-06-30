import type { FeatureRegistryItem } from "@/types/featureRegistry";

export function formatCalcMethod(method: string | null | undefined): string {
  if (!method || method === "CODE") return "코드 기반 계산 (CODE)";
  if (method === "UNKNOWN") return "미등록";
  return method;
}

export function formatLeakageSafe(value: boolean | null | undefined): string {
  if (value === true) return "적용";
  if (value === false) return "미적용";
  return "-";
}

export function formatLookbackHours(hours: number | null | undefined): string {
  if (hours == null) return "-";
  return `${hours}h`;
}

export function formatList(values: string[] | null | undefined, separator = ", "): string {
  if (!values?.length) return "-";
  return values.join(separator);
}

export function formatSourceDataSummary(item: Pick<FeatureRegistryItem, "source_tables" | "source_columns">): string {
  const tables = item.source_tables?.length ? item.source_tables.join(", ") : "-";
  const cols = item.source_columns?.length ? item.source_columns.join(", ") : "-";
  return `${tables} · ${cols}`;
}

export function formatRegistrySummary(reg: FeatureRegistryItem | undefined): string {
  if (!reg) return "Registry 미등록";
  const parts = [formatCalcMethod(reg.calc_method)];
  if (reg.lookback_hours != null) parts.push(`Lookback ${reg.lookback_hours}h`);
  parts.push(`누수방지 ${formatLeakageSafe(reg.leakage_safe)}`);
  return parts.join(" · ");
}

export function formatDateTimeShort(iso: string | null | undefined): string {
  if (!iso) return "-";
  const normalized = iso.replace("T", " ").slice(0, 16);
  return normalized;
}
