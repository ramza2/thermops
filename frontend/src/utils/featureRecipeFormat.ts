import type { FeatureRecipeStatus } from "@/types/featureRecipes";

export function recipeStatusLabel(status: FeatureRecipeStatus): string {
  switch (status) {
    case "DRAFT":
      return "초안";
    case "VALIDATED":
      return "검증됨";
    case "PUBLISHED":
      return "발행됨";
    case "ARCHIVED":
      return "보관";
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

export function recipeBuildSupportLabel(recipe: { status?: string; recipe_type?: string; build_supported?: boolean }): string {
  if (recipe.status !== "PUBLISHED") return "-";
  if (recipe.build_supported) return "Build 지원";
  return "Build 미지원";
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
