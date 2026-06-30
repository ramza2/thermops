import { fetchApi } from "@/api/client";
import type {
  FeatureBuildJobLineageResponse,
  FeatureLineageResponse,
  FeatureRegistryItem,
  FeatureRegistryResponse,
} from "@/types/featureRegistry";

export async function getFeatureRegistry(): Promise<FeatureRegistryResponse> {
  return fetchApi<FeatureRegistryResponse>("/feature-registry");
}

export async function getFeatureRegistryItem(featureName: string): Promise<FeatureRegistryItem> {
  return fetchApi<FeatureRegistryItem>(`/feature-registry/${encodeURIComponent(featureName)}`);
}

export async function getFeatureLineageByDatasetVersion(
  datasetVersionId: string,
): Promise<FeatureLineageResponse> {
  return fetchApi<FeatureLineageResponse>("/feature-lineage", {
    dataset_version_id: datasetVersionId,
  });
}

export async function getFeatureBuildJobLineage(jobId: string): Promise<FeatureBuildJobLineageResponse> {
  return fetchApi<FeatureBuildJobLineageResponse>(`/feature-build-jobs/${encodeURIComponent(jobId)}/lineage`);
}
