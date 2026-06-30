export interface FeatureQualitySummary {
  missing_key_count?: number;
  null_count?: number;
  invalid_count?: number;
  range_violation_count?: number;
  outlier_count?: number;
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
}

export interface FeatureQualityIssueSample {
  feature_name: string;
  site_id: string;
  feature_at: string | null;
  value: unknown;
  issue_type: string;
  message: string;
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
