export interface ColumnRoleCode {
  code: string;
  label: string;
  description: string;
  feature_candidate: boolean;
  required_for: string[];
}

export interface FeatureColumnRole {
  role_id?: string;
  source_column: string;
  target_column?: string | null;
  data_type?: string | null;
  column_role: string | null;
  inferred_role?: string | null;
  inference_confidence?: number | null;
  role_source?: string | null;
  description?: string | null;
  saved?: boolean;
}

export interface RecipeReadinessItem {
  ready: boolean;
  message: string;
}

export interface FeatureColumnRoleSummary {
  entity_key_count: number;
  time_key_count: number;
  target_count: number;
  numeric_input_count: number;
  measure_count: number;
  categorical_input_count: number;
  boolean_input_count: number;
  feature_candidate_count: number;
  recipe_readiness: {
    time_series: RecipeReadinessItem;
    ratio: RecipeReadinessItem;
    encoding: RecipeReadinessItem;
    date_part: RecipeReadinessItem;
  };
}

export interface FeatureColumnRoleValidation {
  valid: boolean;
  blocking?: boolean;
  errors: string[];
  warnings: string[];
  infos?: string[];
}

export interface FeatureColumnRoleListResponse {
  items: FeatureColumnRole[];
  mapping_id?: string | null;
  data_source_id?: string | null;
  target_table?: string | null;
  summary: FeatureColumnRoleSummary;
  validation: FeatureColumnRoleValidation;
  saved_count?: number;
}

export interface FeatureColumnRoleInferRequest {
  mapping_id?: string;
  columns: {
    source_column: string;
    target_column?: string | null;
    data_type?: string | null;
    cardinality?: number | null;
  }[];
  target_table?: string | null;
  source_table?: string | null;
}

export interface FeatureColumnRoleBulkUpdateRequest {
  mapping_id: string;
  roles: {
    source_column: string;
    target_column?: string | null;
    data_type?: string | null;
    column_role: string;
    description?: string | null;
  }[];
}
