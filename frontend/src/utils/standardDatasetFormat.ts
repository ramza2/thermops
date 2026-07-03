const CATEGORY_LABELS: Record<string, string> = {
  MASTER: "기준/마스터",
  FACT: "실적/집계",
  TIMESERIES: "시계열",
  EVENT: "이벤트",
  TRANSACTION: "거래/이력",
  LOG: "로그",
  MAPPING: "매핑",
  CUSTOM: "사용자 정의",
};

import { lifecycleStatusLabel } from "@/constants/displayLabels";

export function datasetCategoryLabel(code?: string | null): string {
  if (!code) return "-";
  return CATEGORY_LABELS[code] || code;
}

/** @deprecated use datasetCategoryLabel */
export const categoryLabel = datasetCategoryLabel;

export function datasetStatusLabel(status: string): string {
  return lifecycleStatusLabel(status, status);
}

export function datasetStatusClass(status: string): string {
  switch (status) {
    case "ACTIVE":
      return "bg-emerald-100 text-emerald-800 border-emerald-200";
    case "DRAFT":
      return "bg-blue-100 text-blue-800 border-blue-200";
    case "PLANNED":
      return "bg-amber-100 text-amber-800 border-amber-200";
    case "VALIDATED":
      return "bg-violet-100 text-violet-800 border-violet-200";
    case "ARCHIVED":
      return "bg-slate-100 text-slate-600 border-slate-200";
    default:
      return "bg-slate-100 text-slate-700 border-slate-200";
  }
}

export function supportBadgeClass(supported: boolean): string {
  return supported
    ? "bg-emerald-50 text-emerald-700 border-emerald-200"
    : "bg-slate-50 text-slate-500 border-slate-200";
}

export function supportLabel(supported: boolean, yes = "지원", no = "미지원"): string {
  return supported ? yes : no;
}

export function physicalTableLabel(exists: boolean): string {
  return exists ? "물리 테이블 존재" : "물리 테이블 없음";
}

export function formatTags(tags?: string[] | null): string {
  if (!tags?.length) return "-";
  return tags.join(", ");
}

export function targetTableOptionLabel(item: {
  dataset_type_name: string;
  target_table: string;
  dataset_category?: string | null;
  category?: string | null;
  business_domain?: string | null;
}): string {
  const category = datasetCategoryLabel(item.dataset_category || item.category);
  const domain = item.business_domain?.trim();
  const meta = [category, domain].filter(Boolean).join(" / ");
  return meta
    ? `${item.dataset_type_name} (${item.target_table} / ${meta})`
    : `${item.dataset_type_name} (${item.target_table})`;
}
