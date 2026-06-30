import { fetchApi } from "@/api/client";
import type { FeatureNameValidation } from "@/types/featureRegistration";

export async function validateFeatureName(featureName: string): Promise<FeatureNameValidation> {
  const q = encodeURIComponent(featureName.trim());
  return fetchApi<FeatureNameValidation>(`/features/validate-name?feature_name=${q}`);
}
