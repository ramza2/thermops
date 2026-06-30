export type FeatureRegistrationStatus =
  | "COMPUTABLE"
  | "CATALOG_ONLY"
  | "LEGACY_ALIAS"
  | "DUPLICATE"
  | "REGISTERED_IN_REGISTRY"
  | "REGISTERED_IN_CATALOG"
  | "UNKNOWN";

export interface FeatureNameValidation {
  feature_name: string;
  status: FeatureRegistrationStatus;
  recommended_name: string | null;
  catalog_registered: boolean;
  registry_registered: boolean;
  computable: boolean;
  message: string;
}

export interface LegacyFeatureReplacement {
  from: string;
  to: string;
  reason: string;
}

export interface FeatureSetLegacyReplaceResult {
  feature_set_id: string;
  dry_run: boolean;
  applied?: boolean;
  changed: boolean;
  original_features: string[];
  replaced_features: string[];
  replacements: LegacyFeatureReplacement[];
  removed_duplicates: string[];
  remaining_legacy_features: string[];
  remaining_non_computable_features: string[];
  warnings: string[];
  replacement_count: number;
  duplicate_removed_count: number;
  remaining_legacy_count: number;
  message: string;
}
