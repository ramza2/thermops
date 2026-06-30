import { fetchApi, postApi } from "@/api/client";
import type {
  FeatureQualityRun,
  FeatureQualityRunCreate,
  FeatureQualityRunListResponse,
} from "@/types/featureQuality";

export async function runFeatureQualityCheck(
  body: FeatureQualityRunCreate,
): Promise<FeatureQualityRun> {
  return postApi<FeatureQualityRun>("/feature-quality-runs", body);
}

export async function getFeatureQualityRuns(params: {
  feature_set_id?: string;
  dataset_version_id?: string;
  status?: string;
  limit?: number;
  offset?: number;
  include_summary?: boolean;
}): Promise<FeatureQualityRunListResponse> {
  const query: Record<string, unknown> = {};
  if (params.feature_set_id) query.feature_set_id = params.feature_set_id;
  if (params.dataset_version_id) query.dataset_version_id = params.dataset_version_id;
  if (params.status) query.status = params.status;
  if (params.limit != null) query.limit = params.limit;
  if (params.offset != null) query.offset = params.offset;
  if (params.include_summary != null) query.include_summary = params.include_summary;
  return fetchApi<FeatureQualityRunListResponse>("/feature-quality-runs", query);
}

export async function getFeatureQualityRun(runId: string): Promise<FeatureQualityRun> {
  return fetchApi<FeatureQualityRun>(`/feature-quality-runs/${encodeURIComponent(runId)}`);
}
