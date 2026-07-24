import { fetchApi, postApi, putApi, api } from "@/api/client";
import type {
  ComponentCatalogItem,
  ComponentCatalogResponse,
  ConnectionRule,
  ConnectionRulesResponse,
  GraphTemplateId,
  VisualPipelineCompileResponse,
  VisualPipelineMaterializationResponse,
  VisualPipelineDetail,
  VisualPipelineGraph,
  VisualPipelineListResponse,
  VisualPipelineRunListResponse,
  VisualPipelineRunRequest,
  VisualPipelineRunResponse,
  VisualPipelineScheduleActivationListResponse,
  VisualPipelineScheduleActivationResponse,
  VisualPipelineSummary,
  VisualPipelineValidationRequest,
  VisualPipelineValidationResponse,
  VisualPipelineVersion,
  VisualPipelineVersionListResponse,
} from "@/types/visualPipeline";
import { buildTemplateGraph } from "@/utils/visualPipelineGraph";

export async function listVisualPipelines(params?: {
  status?: string;
  q?: string;
  include_archived?: boolean;
  limit?: number;
  offset?: number;
}): Promise<VisualPipelineListResponse> {
  return fetchApi<VisualPipelineListResponse>("/visual-pipelines", params as Record<string, unknown>);
}

export async function getVisualPipeline(pipelineId: string): Promise<VisualPipelineDetail> {
  return fetchApi<VisualPipelineDetail>(`/visual-pipelines/${pipelineId}`);
}

export async function createVisualPipeline(body: {
  pipeline_name: string;
  description?: string;
  graph?: VisualPipelineGraph;
}): Promise<VisualPipelineDetail> {
  return postApi<VisualPipelineDetail>("/visual-pipelines", body);
}

export async function updateVisualPipeline(
  pipelineId: string,
  body: {
    pipeline_name?: string;
    description?: string;
    status?: string;
    graph?: VisualPipelineGraph;
    change_summary?: string;
    create_version?: boolean;
  },
): Promise<VisualPipelineDetail> {
  return putApi<VisualPipelineDetail>(`/visual-pipelines/${pipelineId}`, body);
}

export async function archiveVisualPipeline(pipelineId: string): Promise<VisualPipelineSummary> {
  return postApi<VisualPipelineSummary>(`/visual-pipelines/${pipelineId}/archive`);
}

export async function listVisualPipelineVersions(pipelineId: string): Promise<VisualPipelineVersionListResponse> {
  return fetchApi<VisualPipelineVersionListResponse>(`/visual-pipelines/${pipelineId}/versions`);
}

export async function createVisualPipelineVersion(
  pipelineId: string,
  change_summary?: string,
): Promise<VisualPipelineVersion> {
  return postApi<VisualPipelineVersion>(`/visual-pipelines/${pipelineId}/versions`, {
    change_summary: change_summary ?? "manual snapshot",
  });
}

export async function validateVisualPipelineGraph(
  payload: VisualPipelineValidationRequest,
): Promise<VisualPipelineValidationResponse> {
  return postApi<VisualPipelineValidationResponse>("/visual-pipelines/validate-graph", {
    graph: payload.graph,
    pipeline_id: payload.pipeline_id,
    validation_level: payload.validation_level ?? "BASIC",
  });
}

/** R11-S6-1: preview only — no DB write / status update. */
export async function compileVisualPipelinePreview(
  pipelineId: string,
): Promise<VisualPipelineCompileResponse> {
  return postApi<VisualPipelineCompileResponse>(`/visual-pipelines/${pipelineId}/compile-preview`, {
    validation_level: "STRICT",
  });
}

/** R11-S6-2: persist compile result + sync status. Not a Run/activation. */
export async function compileVisualPipeline(
  pipelineId: string,
): Promise<VisualPipelineCompileResponse> {
  return postApi<VisualPipelineCompileResponse>(`/visual-pipelines/${pipelineId}/compile`, {
    validation_level: "STRICT",
  });
}

/**
 * Latest compile result. Returns null when 404 COMPILE_RESULT_NOT_FOUND.
 * Other errors are rethrown.
 */
export async function getVisualPipelineCompileResult(
  pipelineId: string,
): Promise<VisualPipelineCompileResponse | null> {
  try {
    const { data } = await api.get<{ success: boolean; data: VisualPipelineCompileResponse }>(
      `/visual-pipelines/${pipelineId}/compile-result`,
    );
    return data.data;
  } catch (err) {
    const status = (err as { response?: { status?: number; data?: { detail?: string } } })?.response
      ?.status;
    const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
    if (status === 404 && (detail === "COMPILE_RESULT_NOT_FOUND" || detail == null || detail === "")) {
      return null;
    }
    if (status === 404 && typeof detail === "string" && detail.includes("COMPILE_RESULT_NOT_FOUND")) {
      return null;
    }
    throw err;
  }
}

/** R11-S6-6: upsert R10 config rows only — no run/activation/load execution. */
export async function materializeVisualPipeline(
  pipelineId: string,
): Promise<VisualPipelineMaterializationResponse> {
  return postApi<VisualPipelineMaterializationResponse>(`/visual-pipelines/${pipelineId}/materialize`, {});
}

/**
 * Latest materialization result. Returns null when 404 MATERIALIZATION_RESULT_NOT_FOUND.
 * Other errors are rethrown.
 */
export async function getVisualPipelineMaterializationResult(
  pipelineId: string,
): Promise<VisualPipelineMaterializationResponse | null> {
  try {
    const { data } = await api.get<{ success: boolean; data: VisualPipelineMaterializationResponse }>(
      `/visual-pipelines/${pipelineId}/materialization-result`,
    );
    return data.data;
  } catch (err) {
    const status = (err as { response?: { status?: number; data?: { detail?: string } } })?.response
      ?.status;
    const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
    if (status === 404 && (detail === "MATERIALIZATION_RESULT_NOT_FOUND" || detail == null || detail === "")) {
      return null;
    }
    if (
      status === 404 &&
      typeof detail === "string" &&
      detail.includes("MATERIALIZATION_RESULT_NOT_FOUND")
    ) {
      return null;
    }
    throw err;
  }
}

/** R11-S7-4: accept BACKGROUND Manual Run (HTTP 202). Does not wait for completion. */
export async function runVisualPipeline(
  pipelineId: string,
  body?: VisualPipelineRunRequest,
): Promise<VisualPipelineRunResponse> {
  return postApi<VisualPipelineRunResponse>(`/visual-pipelines/${pipelineId}/runs`, body ?? {});
}

export async function getVisualPipelineRun(
  pipelineId: string,
  runId: string,
): Promise<VisualPipelineRunResponse> {
  return fetchApi<VisualPipelineRunResponse>(
    `/visual-pipelines/${pipelineId}/runs/${encodeURIComponent(runId)}`,
  );
}

export async function listVisualPipelineRuns(
  pipelineId: string,
  limit = 20,
): Promise<VisualPipelineRunListResponse> {
  return fetchApi<VisualPipelineRunListResponse>(`/visual-pipelines/${pipelineId}/runs`, { limit });
}

/**
 * Latest Manual Run detail. Returns null when no runs exist.
 * Does not start a run (GET-only). Latest list empty → null; other errors rethrown.
 */
export async function getLatestVisualPipelineRun(
  pipelineId: string,
): Promise<VisualPipelineRunResponse | null> {
  const listed = await listVisualPipelineRuns(pipelineId, 1);
  const latest = listed.items?.[0];
  if (!latest?.visual_run_id) return null;
  return getVisualPipelineRun(pipelineId, latest.visual_run_id);
}

/** R11-S7-8: activate schedule — no run_load / no immediate run row. */
export async function activateVisualPipelineSchedule(
  pipelineId: string,
): Promise<VisualPipelineScheduleActivationResponse> {
  return postApi<VisualPipelineScheduleActivationResponse>(
    `/visual-pipelines/${pipelineId}/schedule-activations`,
    {},
  );
}

export async function deactivateVisualPipelineSchedule(
  pipelineId: string,
  activationId: string,
): Promise<VisualPipelineScheduleActivationResponse> {
  return postApi<VisualPipelineScheduleActivationResponse>(
    `/visual-pipelines/${pipelineId}/schedule-activations/${encodeURIComponent(activationId)}/deactivate`,
    {},
  );
}

export async function getCurrentVisualPipelineScheduleActivation(
  pipelineId: string,
): Promise<VisualPipelineScheduleActivationResponse | null> {
  return fetchApi<VisualPipelineScheduleActivationResponse | null>(
    `/visual-pipelines/${pipelineId}/schedule-activations/current`,
  );
}

export async function listVisualPipelineScheduleActivations(
  pipelineId: string,
  limit = 20,
): Promise<VisualPipelineScheduleActivationListResponse> {
  return fetchApi<VisualPipelineScheduleActivationListResponse>(
    `/visual-pipelines/${pipelineId}/schedule-activations`,
    { limit },
  );
}

export async function getComponentCatalog(params?: {
  status?: string;
  category?: string;
}): Promise<ComponentCatalogResponse> {
  const data = await fetchApi<ComponentCatalogItem[] | ComponentCatalogResponse>(
    "/visual-pipelines/components",
    params as Record<string, unknown>,
  );
  if (Array.isArray(data)) {
    return { items: data };
  }
  return data;
}

export async function getConnectionRules(): Promise<ConnectionRulesResponse> {
  const data = await fetchApi<ConnectionRule[] | ConnectionRulesResponse>("/visual-pipelines/connection-rules");
  if (Array.isArray(data)) {
    return { items: data };
  }
  return data;
}

export async function createVisualPipelineFromTemplate(
  pipelineName: string,
  description: string | undefined,
  templateId: GraphTemplateId,
): Promise<VisualPipelineDetail> {
  const graph = templateId === "blank" ? undefined : buildTemplateGraph(templateId);
  return createVisualPipeline({
    pipeline_name: pipelineName,
    description,
    graph,
  });
}
