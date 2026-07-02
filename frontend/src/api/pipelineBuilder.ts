import { fetchApi, postApi, putApi } from "@/api/client";
import type {
  PipelineDefinition,
  PipelineDefinitionCreateRequest,
  PipelineNodeOptions,
  PipelineRunLink,
  PipelineRunRequest,
  PipelineRunResponse,
  PipelineRuntimePreview,
  PipelineTemplate,
  PipelineValidationResult,
} from "@/types/pipelineBuilder";

export async function getPipelineTemplates(params?: {
  status?: string;
  pipeline_type?: string;
  active_only?: boolean;
}): Promise<{ items: PipelineTemplate[]; total: number }> {
  return fetchApi("/pipeline-templates", params);
}

export async function getPipelineTemplate(templateId: string): Promise<PipelineTemplate> {
  return fetchApi(`/pipeline-templates/${encodeURIComponent(templateId)}`);
}

export async function getPipelineDefinitions(params?: {
  status?: string;
  pipeline_type?: string;
  template_id?: string;
  active_only?: boolean;
}): Promise<{ items: PipelineDefinition[]; total: number }> {
  return fetchApi("/pipeline-definitions", params);
}

export async function getPipelineDefinition(pipelineId: string): Promise<PipelineDefinition> {
  return fetchApi(`/pipeline-definitions/${encodeURIComponent(pipelineId)}`);
}

export async function createPipelineDefinition(
  payload: PipelineDefinitionCreateRequest,
): Promise<PipelineDefinition> {
  return postApi("/pipeline-definitions", payload);
}

export async function updatePipelineDefinition(
  pipelineId: string,
  payload: Partial<PipelineDefinitionCreateRequest> & { node_config?: Record<string, Record<string, unknown>> },
): Promise<PipelineDefinition> {
  return putApi(`/pipeline-definitions/${encodeURIComponent(pipelineId)}`, payload);
}

export async function validatePipelineDefinition(pipelineId: string): Promise<PipelineValidationResult> {
  return postApi(`/pipeline-definitions/${encodeURIComponent(pipelineId)}/validate`);
}

export async function activatePipelineDefinition(pipelineId: string): Promise<PipelineDefinition> {
  return postApi(`/pipeline-definitions/${encodeURIComponent(pipelineId)}/activate`);
}

export async function archivePipelineDefinition(pipelineId: string): Promise<PipelineDefinition> {
  return postApi(`/pipeline-definitions/${encodeURIComponent(pipelineId)}/archive`);
}

export async function getPipelineNodeOptions(params: {
  component_type: string;
  template_id?: string;
  pipeline_id?: string;
}): Promise<PipelineNodeOptions> {
  return fetchApi("/pipeline-node-options", params);
}

export async function getPipelineRuntimePreview(pipelineId: string): Promise<PipelineRuntimePreview> {
  return postApi(`/pipeline-definitions/${encodeURIComponent(pipelineId)}/runtime-preview`);
}

export async function runPipelineDefinition(
  pipelineId: string,
  payload: PipelineRunRequest = {},
): Promise<PipelineRunResponse> {
  return postApi(`/pipeline-definitions/${encodeURIComponent(pipelineId)}/run`, payload);
}

export async function getPipelineDefinitionRuns(
  pipelineId: string,
  params?: { limit?: number; status?: string },
): Promise<{ items: PipelineRunLink[]; total: number }> {
  return fetchApi(`/pipeline-definitions/${encodeURIComponent(pipelineId)}/runs`, params);
}

export async function getPipelineRunLinks(params?: {
  pipeline_id?: string;
  template_id?: string;
  airflow_dag_id?: string;
  run_status?: string;
  limit?: number;
}): Promise<{ items: PipelineRunLink[]; total: number }> {
  return fetchApi("/pipeline-run-links", params);
}
