export interface FeatureQualitySummary {
  missing_key_count?: number;
  null_count?: number;
  invalid_count?: number;
  range_violation_count?: number;
  outlier_count?: number;
  catalog_only_feature_count?: number;
  legacy_alias_feature_count?: number;
  non_computable_feature_count?: number;
  registry_missing_feature_count?: number;
}

export interface FeatureQualityFeatureResult {
  feature_name: string;
  status: string;
  count: number;
  null_count: number;
  null_ratio: number;
  invalid_count: number;
  range_violation_count: number;
  outlier_count: number;
  min?: number | null;
  p25?: number | null;
  mean?: number | null;
  p50?: number | null;
  p75?: number | null;
  max?: number | null;
  std?: number | null;
  registration_status?: string;
  catalog_registered?: boolean;
  registry_registered?: boolean;
  computable?: boolean;
  legacy_alias?: boolean;
  recommended_name?: string | null;
  registration_message?: string;
  recipe_id?: string;
  recipe_type?: string;
  build_supported?: boolean;
}

export interface FeatureQualityIssueSample {
  feature_name: string;
  site_id: string;
  feature_at: string | null;
  value: unknown;
  issue_type: string;
  message: string;
  registration_status?: string;
  computable?: boolean;
  recommended_name?: string | null;
  registration_message?: string;
  recipe_id?: string;
  recipe_type?: string;
  build_supported?: boolean;
}

export interface FeatureQualityResultSummary {
  check_type?: string;
  feature_set_id: string;
  feature_set_name?: string;
  dataset_version_id?: string | null;
  status: string;
  score: number;
  row_count: number;
  feature_count: number;
  checked_at?: string;
  time_range?: {
    min_feature_at?: string | null;
    max_feature_at?: string | null;
  };
  site_count?: number;
  summary?: FeatureQualitySummary;
  registration_summary?: FeatureQualitySummary;
  build_coverage?: {
    missing_feature_count?: number;
    missing_features?: string[];
    catalog_only_features?: string[];
    legacy_alias_features?: string[];
    template_feature_count?: number;
    template_generated_feature_count?: number;
    template_build_failed_feature_count?: number;
    template_build_unsupported_feature_count?: number;
    template_build_status_counts?: Record<string, number>;
  };
  features?: FeatureQualityFeatureResult[];
  warnings?: string[];
  errors?: string[];
  issue_samples?: FeatureQualityIssueSample[];
  scoring?: Record<string, unknown>;
}

export interface FeatureQualityRun {
  run_id: string;
  feature_set_id: string;
  dataset_version_id?: string | null;
  status: string;
  score?: number | null;
  row_count?: number;
  feature_count?: number;
  started_at?: string | null;
  ended_at?: string | null;
  summary?: FeatureQualitySummary;
  warnings?: string[];
  errors?: string[];
  result_summary?: FeatureQualityResultSummary;
}

export interface FeatureQualityRunListResponse {
  items: FeatureQualityRun[];
  total: number;
  limit: number;
  offset: number;
}

export interface FeatureQualityRunCreate {
  feature_set_id: string;
  dataset_version_id?: string | null;
}
