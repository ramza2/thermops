import type { RecipeTemplate } from "@/types/featureRecipeTemplates";

const CATEGORY_LABELS: Record<string, string> = {
  RAW: "원본",
  TIME_SERIES: "시계열",
  AGGREGATION: "집계",
  RATIO: "비율",
  DATETIME: "날짜/시간",
  TRANSFORM: "변환",
  CATEGORICAL: "범주형",
};

const STATUS_LABELS: Record<string, string> = {
  ACTIVE: "사용 가능",
  EXPERIMENTAL: "실험적",
  PLANNED: "예정",
};

export function templateCategoryLabel(category: string): string {
  return CATEGORY_LABELS[category] ?? category;
}

export function templateStatusLabel(status: string): string {
  return STATUS_LABELS[status] ?? status;
}

export function templateStatusClass(status: string): string {
  switch (status) {
    case "ACTIVE":
      return "text-emerald-700 bg-emerald-50 border-emerald-200";
    case "EXPERIMENTAL":
      return "text-amber-700 bg-amber-50 border-amber-200";
    case "PLANNED":
      return "text-slate-600 bg-slate-100 border-slate-300";
    default:
      return "text-slate-700 bg-slate-50 border-slate-200";
  }
}

export function templateAvailabilityClass(available: boolean | null | undefined): string {
  if (available === true) return "text-emerald-700";
  if (available === false) return "text-amber-700";
  return "text-slate-500";
}

export function leakagePolicyLabel(policy: string): string {
  switch (policy) {
    case "SHIFT_REQUIRED":
      return "Shift 필수";
    case "WINDOW_INCLUDES_CURRENT_RISK":
      return "현재 행 포함 시 누수 위험";
    case "LOW":
      return "낮음";
    case "NONE":
      return "없음";
    default:
      return policy;
  }
}

export function formatRequiredRoles(template: RecipeTemplate): string {
  if (template.required_roles.length) {
    return template.required_roles.join(", ");
  }
  if (template.optional_roles?.length) {
    return `선택: ${template.optional_roles.slice(0, 3).join(", ")}`;
  }
  return "-";
}

export const RECIPE_BUILDER_FUTURE_NOTE =
  "Recipe Builder는 후속 단계에서 제공됩니다. 현재 단계에서는 템플릿 사용 가능 여부만 확인할 수 있습니다.";

export const RECIPE_TEMPLATE_SECTION_TITLE = "사용 가능한 Recipe 템플릿";
