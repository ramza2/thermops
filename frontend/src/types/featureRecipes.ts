export type FeatureRecipeStatus = "DRAFT" | "VALIDATED" | "PUBLISHED" | "ARCHIVED";

export interface FeatureRecipe {
  recipe_id: string;
  feature_name: string | null;
  display_name: string;
  description?: string | null;
  domain?: string | null;
  task_type?: string | null;
  calc_mode: string;
  recipe_type: string;
  mapping_id?: string | null;
  data_source_id?: string | null;
  source_table?: string | null;
  target_table?: string | null;
  source_columns: string[];
  entity_keys?: string[];
  time_key?: string | null;
  target_column?: string | null;
  params: Record<string, unknown>;
  output_feature_names?: string[];
  output_data_type?: string | null;
  status: FeatureRecipeStatus;
  version: number;
  validation_summary?: Record<string, unknown> | null;
  preview_summary?: Record<string, unknown> | null;
  lineage_preview?: Record<string, unknown> | null;
  quality_preview?: Record<string, unknown> | null;
  published_at?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
  build_supported?: boolean;
}

export interface FeatureRecipeListResponse {
  items: FeatureRecipe[];
  total: number;
  limit: number;
  offset: number;
}

export interface FeatureRecipeCreateRequest {
  mapping_id?: string | null;
  recipe_type: string;
  source_columns: string[];
  entity_keys?: string[] | null;
  time_key?: string | null;
  target_column?: string | null;
  params?: Record<string, unknown> | null;
  output_feature_name?: string | null;
  display_name?: string | null;
  description?: string | null;
}

export interface FeatureSetAddRecipeFeatureResult {
  feature_set_id: string;
  feature_name: string;
  recipe_id: string;
  added: boolean;
  features: string[];
  warnings: string[];
  message?: string;
}

export const R6_BUILD_INFO =
  "R6 Recipe Engine이 RAW_COLUMN, DATE_PART, LAG, ROLLING_MEAN, ROLLING_SUM Feature Build를 지원합니다.";

export const R5_BUILD_WARNING = R6_BUILD_INFO;

export const RECIPE_PREVIEW_NO_SAVE_NOTE =
  "Preview 결과는 저장하지 않습니다. preview_summary만 Recipe에 기록됩니다.";
