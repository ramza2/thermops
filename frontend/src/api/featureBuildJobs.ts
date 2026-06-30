import { fetchApi } from "@/api/client";
import type {
  FeatureBuildJobListParams,
  FeatureBuildJobListResponse,
  FeatureBuildJobSummary,
} from "@/types/featureRegistry";

export async function getFeatureBuildJobs(
  params: FeatureBuildJobListParams = {},
): Promise<FeatureBuildJobListResponse> {
  const query: Record<string, unknown> = {};
  if (params.feature_set_id) query.feature_set_id = params.feature_set_id;
  if (params.status) query.status = params.status;
  if (params.limit != null) query.limit = params.limit;
  if (params.offset != null) query.offset = params.offset;
  if (params.include_summary != null) query.include_summary = params.include_summary;
  return fetchApi<FeatureBuildJobListResponse>("/feature-build-jobs", query);
}

/** 목록 API 기준 최신 Build Job (limit=1). */
export async function getLatestFeatureBuildJob(
  featureSetId: string,
): Promise<FeatureBuildJobSummary | null> {
  const res = await getFeatureBuildJobs({ feature_set_id: featureSetId, limit: 1, offset: 0 });
  return res.items[0] ?? null;
}

export function pickDefaultBuildJob(jobs: FeatureBuildJobSummary[]): FeatureBuildJobSummary | null {
  if (!jobs.length) return null;
  const withLineage = jobs.find(
    (j) => (j.lineage_count ?? 0) > 0 && (j.status === "SUCCESS" || j.status === "WARNING"),
  );
  if (withLineage) return withLineage;
  const successOrWarn = jobs.find((j) => j.status === "SUCCESS" || j.status === "WARNING");
  if (successOrWarn) return successOrWarn;
  return jobs[0];
}
