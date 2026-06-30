import { fetchApi, postApi } from "@/api/client";
import type { FeatureNameValidation, FeatureSetLegacyReplaceResult } from "@/types/featureRegistration";

export async function validateFeatureName(featureName: string): Promise<FeatureNameValidation> {
  const q = encodeURIComponent(featureName.trim());
  return fetchApi<FeatureNameValidation>(`/features/validate-name?feature_name=${q}`);
}

export async function replaceLegacyFeatures(
  featureSetId: string,
  dryRun: boolean,
): Promise<FeatureSetLegacyReplaceResult> {
  return postApi<FeatureSetLegacyReplaceResult>(
    `/feature-sets/${encodeURIComponent(featureSetId)}/replace-legacy-features`,
    { dry_run: dryRun },
  );
}
