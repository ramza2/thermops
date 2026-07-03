const DOMAIN_LABELS: Record<string, string> = {
  HEAT_DEMAND: "열수요",
  WEATHER: "기상",
  MASTER: "기준정보",
  FACILITY: "설비",
  COST: "원가",
  EMISSION: "환경",
  OPERATION: "운영",
};

const CATEGORY_LABELS: Record<string, string> = {
  FACT: "Fact",
  MASTER: "Master",
  MAPPING: "Mapping",
  CODE: "Code",
  EVENT: "Event",
  SENSOR: "Sensor",
};

const STATUS_LABELS: Record<string, string> = {
  ACTIVE: "운영",
  DRAFT: "설계",
  PLANNED: "계획",
  VALIDATED: "검증",
  ARCHIVED: "보관",
};

export function domainLabel(code?: string | null): string {
  if (!code) return "-";
  return DOMAIN_LABELS[code] || code;
}

export function categoryLabel(code?: string | null): string {
  if (!code) return "-";
  return CATEGORY_LABELS[code] || code;
}

export function datasetStatusLabel(status: string): string {
  return STATUS_LABELS[status] || status;
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

export function targetTableOptionLabel(item: {
  dataset_type_name: string;
  target_table: string;
}): string {
  return `${item.dataset_type_name} (${item.target_table})`;
}
