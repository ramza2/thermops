import { fetchApi, postApi, putApi } from "@/api/client";
import type {
  ComponentCatalogItem,
  ComponentCatalogResponse,
  ConnectionRule,
  ConnectionRulesResponse,
  GraphTemplateId,
  VisualPipelineDetail,
  VisualPipelineGraph,
  VisualPipelineListResponse,
  VisualPipelineSummary,
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
