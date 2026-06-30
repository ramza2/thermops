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
