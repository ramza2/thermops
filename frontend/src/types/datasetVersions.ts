export interface DatasetVersion {
  dataset_version_id: string;
  feature_set_id: string | null;
  dataset_type: string | null;
  dataset_version_role: string | null;
  dataset_version_status: string | null;
  build_scope: string | null;
  is_primary: boolean;
  is_training_ready: boolean;
  is_serving_ready: boolean;
  record_count: number | null;
  feature_count: number | null;
  coverage_ratio: number | null;
  null_ratio: number | null;
  quality_score: number | null;
  base_start_at: string | null;
  base_end_at: string | null;
  build_started_at: string | null;
  build_finished_at: string | null;
  archived_at: string | null;
  archived_reason: string | null;
  selection_policy_note: string | null;
  created_by: string | null;
  created_at: string | null;
  metadata_json: Record<string, unknown> | null;
}

export interface DatasetVersionSelectionPreview {
  feature_set_id: string;
  purpose: string;
  selected: DatasetVersion | null;
  selection_reason: string;
  warnings: string[];
  excluded_candidates: { dataset_version_id: string; reason: string }[];
}

export interface DatasetVersionCleanupPreview {
  dry_run: boolean;
  count: number;
  items: DatasetVersion[];
}
