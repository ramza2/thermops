import type {
  FeatureRecipeStatus,
  RecipeBuildHistoryItem,
  RecipeBuildStatusBadge,
  RecipePreviewBuildCompareSummary,
} from "@/types/featureRecipes";

export function recipeStatusLabel(status: FeatureRecipeStatus): string {
  switch (status) {
    case "DRAFT":
      return "작성 중";
    case "VALIDATED":
      return "검증 완료";
    case "PUBLISHED":
      return "사용 가능";
    case "ARCHIVED":
      return "보관됨";
    default:
      return status;
  }
}

export function recipeStatusClass(status: FeatureRecipeStatus): string {
  switch (status) {
    case "PUBLISHED":
      return "bg-emerald-50 text-emerald-800 border-emerald-200";
    case "VALIDATED":
      return "bg-sky-50 text-sky-800 border-sky-200";
    case "DRAFT":
      return "bg-amber-50 text-amber-800 border-amber-200";
    case "ARCHIVED":
      return "bg-slate-50 text-slate-500 border-slate-200";
    default:
      return "bg-slate-50 text-slate-600 border-slate-200";
  }
}

export const BUILDER_SUPPORTED_TYPES = [
  "RAW_COLUMN",
  "DATE_PART",
  "LAG",
  "ROLLING_MEAN",
  "ROLLING_SUM",
] as const;

export function recipeBuildSupportLabel(recipe: {
  status?: string;
  recipe_type?: string;
  build_supported?: boolean;
}): string {
  if (recipe.status !== "PUBLISHED") return "-";
  if (recipe.build_supported) return "생성 지원";
  return "생성 미지원";
}

export function recipeBuildSupportClass(recipe: { build_supported?: boolean }): string {
  return recipe.build_supported
    ? "bg-emerald-50 text-emerald-800 border-emerald-200"
    : "bg-amber-50 text-amber-800 border-amber-200";
}

export const BUILDER_FUTURE_TYPES = [
  "DIFF",
  "RATIO",
  "BINNING",
  "FILL_NULL",
  "CATEGORY_ENCODING",
] as const;

export function mapTemplateFeatureStatusToBadge(status: string | undefined | null): RecipeBuildStatusBadge {
  switch (status) {
    case "GENERATED":
      return "BUILD_OK";
    case "GENERATED_WITH_WARNING":
      return "BUILD_WARNING";
    case "FAILED":
      return "BUILD_FAILED";
    case "UNSUPPORTED":
      return "BUILD_UNSUPPORTED";
    case "NO_BUILD":
      return "BUILD_NOT_RUN";
    case "UNKNOWN":
      return "BUILD_LIMITED";
    default:
      return "BUILD_UNKNOWN";
  }
}

export function getRecipeBuildStatusLabel(badge: RecipeBuildStatusBadge): string {
  switch (badge) {
    case "BUILD_OK":
      return "최근 생성 성공";
    case "BUILD_WARNING":
      return "최근 생성 경고";
    case "BUILD_FAILED":
      return "최근 생성 실패";
    case "BUILD_UNSUPPORTED":
      return "생성 미지원";
    case "BUILD_NOT_RUN":
      return "아직 생성 없음";
    case "BUILD_LIMITED":
      return "진단 정보 제한";
    default:
      return "상태 미확인";
  }
}

export function getRecipeBuildStatusBadgeClass(badge: RecipeBuildStatusBadge): string {
  switch (badge) {
    case "BUILD_OK":
      return "bg-emerald-50 text-emerald-800 border-emerald-200";
    case "BUILD_WARNING":
      return "bg-amber-50 text-amber-800 border-amber-200";
    case "BUILD_FAILED":
      return "bg-red-50 text-red-800 border-red-200";
    case "BUILD_UNSUPPORTED":
      return "bg-slate-100 text-slate-700 border-slate-300";
    case "BUILD_NOT_RUN":
      return "bg-slate-50 text-slate-500 border-slate-200";
    case "BUILD_LIMITED":
      return "bg-violet-50 text-violet-800 border-violet-200";
    default:
      return "bg-slate-50 text-slate-600 border-slate-200";
  }
}

export function formatNullRatio(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return "-";
  return `${(value * 100).toFixed(1)}%`;
}

export function formatCompareSummary(summary: RecipePreviewBuildCompareSummary | undefined): string {
  if (!summary) return "-";
  const parts = [
    `샘플 ${summary.sample_count}`,
    `일치 ${summary.matched_count}`,
    `불일치 ${summary.mismatch_count}`,
  ];
  if (summary.max_abs_diff != null) {
    parts.push(`최대차이 ${summary.max_abs_diff.toFixed(6)}`);
  }
  return parts.join(" · ");
}

const DIAGNOSTIC_CODE_LABELS: Record<string, string> = {
  RECIPE_NOT_PUBLISHED: "Recipe 미발행",
  RECIPE_ARCHIVED: "Recipe 보관됨",
  UNSUPPORTED_RECIPE_TYPE: "Build 미지원 Type",
  SOURCE_COLUMN_MISSING: "원천 컬럼 없음",
  ENTITY_KEY_MISSING: "Entity key 없음",
  TIME_KEY_MISSING: "Time key 없음",
  INVALID_PARAM: "파라미터 오류",
  NUMERIC_CONVERSION_FAILED: "숫자 변환 실패",
  DATETIME_CONVERSION_FAILED: "시간 변환 실패",
  INSUFFICIENT_HISTORY: "이력 부족 (초기 null 가능)",
  TIME_GAP_DETECTED: "시간 간격 불일치 (row step)",
  LEAKAGE_RISK: "누수 위험 (현재 행 포함)",
  UNKNOWN_BUILD_ERROR: "알 수 없는 오류",
};

export function formatDiagnosticCode(code: string | undefined): string {
  if (!code) return "-";
  return DIAGNOSTIC_CODE_LABELS[code] ?? code;
}

export function getDiagnosticSeverityLabel(severity: string | undefined): string {
  if (severity === "ERROR") return "오류";
  if (severity === "WARNING") return "경고";
  return severity ?? "-";
}

export function summarizeBuildHistoryItem(item: RecipeBuildHistoryItem | undefined): string {
  if (!item) return "";
  const codes = [...(item.warning_codes ?? []), ...(item.error_codes ?? [])];
  if (!codes.length) return "-";
  return codes.map(formatDiagnosticCode).join(", ");
}

export const COMPARE_HELP_NOTE =
  "Preview/Build 비교는 샘플 기반 운영 검증 기능입니다. 완전한 정합성을 보장하지 않습니다.";

export const COMPARE_LIMITED_NOTE =
  "원천 데이터 기간 또는 entity/time 정렬이 다르면 비교가 제한될 수 있습니다.";

export const LAG_ROLLING_COMPARE_NOTE =
  "LAG/ROLLING은 row step 기반이므로 time gap이 있으면 차이가 발생할 수 있습니다.";

export const LEGACY_JOB_DIAGNOSTICS_NOTE =
  "R6-S1 이전 Build Job은 template_build_status_by_feature 등 진단 필드가 없어 이력 검색·상태 표시가 제한될 수 있습니다.";
