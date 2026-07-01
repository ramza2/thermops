export interface RecipeTemplateAvailability {
  available: boolean;
  missing_roles: string[];
  warnings: string[];
}

export interface RecipeTemplate {
  recipe_type: string;
  display_name: string;
  description: string;
  category: string;
  status: string;
  required_roles: string[];
  optional_roles?: string[];
  required_input_count: number;
  output_data_type: string;
  param_schema: Record<string, unknown>;
  default_params?: Record<string, unknown>;
  output_name_rule: string;
  leakage_policy: string;
  supported_granularity?: string[];
  enabled_by_default?: boolean;
  examples?: Record<string, unknown>[];
  warnings?: string[];
  available?: boolean | null;
  availability?: RecipeTemplateAvailability | null;
}

export interface RecipeTemplateListSummary {
  total_count: number;
  available_count: number | null;
  active_count: number;
}

export interface RecipeTemplateListResponse {
  items: RecipeTemplate[];
  summary: RecipeTemplateListSummary;
  mapping_id?: string;
}

export interface RecipeValidationMessage {
  code: string;
  message: string;
}

export interface RecipeValidateRequest {
  mapping_id?: string;
  recipe_type: string;
  source_columns: string[];
  entity_keys?: string[];
  time_key?: string;
  target_column?: string;
  params?: Record<string, unknown>;
  output_feature_name?: string | null;
  cardinality?: number;
}

export interface RecipeLineagePreview {
  calc_method: string;
  recipe_type: string;
  source_columns: string[];
  entity_keys: string[];
  time_key?: string | null;
  target_column?: string | null;
  params: Record<string, unknown>;
}

export interface RecipeValidateResponse {
  valid: boolean;
  recipe_type: string;
  generated_feature_name?: string;
  output_feature_name?: string;
  generated_feature_names?: string[];
  output_feature_names?: string[];
  duplicate_policy?: string;
  reusable_existing_feature?: boolean;
  reusable_existing_features?: ReusableExistingFeature[];
  errors: RecipeValidationMessage[];
  warnings: string[];
  infos: string[];
  template?: RecipeTemplate;
  lineage_preview?: RecipeLineagePreview;
}

export interface ReusableExistingFeature {
  feature_name: string;
  reason: string;
}

export interface FeatureRecipePreviewStats {
  row_count: number;
  sample_size: number;
  entity_count?: number;
  time_gap_warning_count?: number;
  features: Record<string, {
    null_count: number;
    null_ratio: number;
    invalid_count?: number;
    insufficient_history_count?: number;
    min?: number;
    max?: number;
    mean?: number;
    expected_granularity?: string;
    observed_granularity_summary?: string;
    time_gap_warning_count?: number;
  }>;
}

export interface TimeSeriesPreviewMeta {
  entity_keys: string[];
  time_key: string;
  source_column: string;
  sort_order: string;
  row_step_based: boolean;
  expected_granularity: string;
  include_current_row?: boolean;
}

export interface EntitySummary {
  entity_count: number;
  rows_per_entity_min: number;
  rows_per_entity_max: number;
}

export interface QualityPreview {
  estimated_status: string;
  warnings: string[];
}

export interface FeatureRecipePreviewRequest extends RecipeValidateRequest {
  sample_size?: number;
  start_at?: string | null;
  end_at?: string | null;
}

export interface FeatureRecipePreviewResponse {
  preview_id: string;
  recipe_type: string;
  supported: boolean;
  valid: boolean;
  generated_feature_names?: string[];
  output_feature_names?: string[];
  reusable_existing_features?: ReusableExistingFeature[];
  duplicate_policy?: string;
  preview_rows: Record<string, unknown>[];
  stats: FeatureRecipePreviewStats;
  lineage_preview?: RecipeLineagePreview | null;
  quality_preview?: QualityPreview;
  time_series_preview?: TimeSeriesPreviewMeta | null;
  time_gap_warnings?: string[];
  leakage_warnings?: string[];
  history_warnings?: string[];
  entity_summary?: EntitySummary | null;
  computation_policy?: Record<string, unknown> | null;
  errors: RecipeValidationMessage[];
  warnings: string[];
  infos: string[];
}
