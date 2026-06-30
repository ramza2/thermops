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
  errors: RecipeValidationMessage[];
  warnings: string[];
  infos: string[];
  template?: RecipeTemplate;
  lineage_preview?: RecipeLineagePreview;
}
