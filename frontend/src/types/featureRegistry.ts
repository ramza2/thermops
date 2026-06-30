/** Feature Registry·Lineage (ml/feature_registry.py, tb_feature_lineage) */

export interface FeatureRegistryItem {
  feature_name: string;
  display_name: string;
  feature_group: string;
  feature_type: string;
  calc_method: string;
  calc_expression: string;
  source_tables: string[];
  source_columns: string[];
  partition_keys: string[];
  time_key: string;
  lookback_hours: number | null;
  requires_shift: boolean;
  leakage_safe: boolean;
  description: string;
  registry_version?: string;
}

export interface FeatureRegistryResponse {
  registry_version: string;
  features: FeatureRegistryItem[];
}

export interface FeatureLineageItem {
  lineage_id: number;
  dataset_version_id: string;
  feature_build_job_id: string | null;
  feature_set_id: string;
  feature_name: string;
  registry_version?: string;
  calc_method: string;
  calc_expression: string | null;
  source_tables: string[];
  source_columns: string[];
  partition_keys: string[];
  time_key: string | null;
  lookback_hours: number | null;
  requires_shift: boolean | null;
  leakage_safe: boolean | null;
  build_start_at: string | null;
  build_end_at: string | null;
  site_filter: string | null;
  lineage_json: Record<string, unknown> | null;
  created_at: string | null;
}

export interface FeatureLineageResponse {
  dataset_version_id: string;
  lineage_count: number;
  items: FeatureLineageItem[];
}

export interface FeatureBuildJobLineageResponse {
  job_id: string;
  dataset_version_id?: string | null;
  lineage_count: number;
  items: FeatureLineageItem[];
}

export interface FeatureBuildResult {
  job_id: string;
  status?: string;
  inserted_count: number;
  dataset_version_id?: string;
  lineage_count?: number;
  lineage_error?: string | null;
  checked_start_at?: string;
  checked_end_at?: string;
  feature_names?: string[];
  warnings?: string[];
  result_summary?: {
    lineage_count?: number;
    lineage_error?: string | null;
    dataset_version_id?: string;
    warnings?: string[];
  };
}
