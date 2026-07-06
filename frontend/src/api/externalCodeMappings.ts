import { fetchApi, postApi, putApi } from "@/api/client";
import type {
  ExternalCodeMapping,
  MappingOptions,
  ResolveResult,
  TargetCandidate,
  UnmappedExternalCode,
} from "@/types/externalCodeMappings";

export async function listExternalCodeMappings(params?: Record<string, string | boolean>): Promise<ExternalCodeMapping[]> {
  return fetchApi("/external-code-mappings", params);
}

export async function getExternalCodeMapping(mappingId: string): Promise<ExternalCodeMapping> {
  return fetchApi(`/external-code-mappings/${encodeURIComponent(mappingId)}`);
}

export async function createExternalCodeMapping(body: Record<string, unknown>): Promise<ExternalCodeMapping> {
  return postApi("/external-code-mappings", body);
}

export async function updateExternalCodeMapping(mappingId: string, body: Record<string, unknown>): Promise<ExternalCodeMapping> {
  return putApi(`/external-code-mappings/${encodeURIComponent(mappingId)}`, body);
}

export async function archiveExternalCodeMapping(mappingId: string, archivedReason?: string): Promise<ExternalCodeMapping> {
  return postApi(`/external-code-mappings/${encodeURIComponent(mappingId)}/archive`, { archived_reason: archivedReason });
}

export async function listUnmappedExternalCodes(params?: Record<string, string>): Promise<UnmappedExternalCode[]> {
  return fetchApi("/external-code-mappings/unmapped", params);
}

export async function assignUnmappedCode(unmappedId: string, body: Record<string, unknown>): Promise<{ mapping: ExternalCodeMapping; unmapped: UnmappedExternalCode }> {
  return postApi(`/external-code-mappings/unmapped/${encodeURIComponent(unmappedId)}/assign`, body);
}

export async function ignoreUnmappedCode(unmappedId: string, ignoredReason?: string): Promise<UnmappedExternalCode> {
  return postApi(`/external-code-mappings/unmapped/${encodeURIComponent(unmappedId)}/ignore`, { ignored_reason: ignoredReason });
}

export async function archiveUnmappedCode(unmappedId: string): Promise<UnmappedExternalCode> {
  return postApi(`/external-code-mappings/unmapped/${encodeURIComponent(unmappedId)}/archive`);
}

export async function resolveExternalCode(body: Record<string, unknown>): Promise<ResolveResult> {
  return postApi("/external-code-mappings/resolve", body);
}

export async function getExternalCodeMappingOptions(): Promise<MappingOptions> {
  return fetchApi("/external-code-mappings/options");
}

export async function searchTargetCandidates(targetType: string, keyword?: string): Promise<TargetCandidate[]> {
  return fetchApi("/external-code-mappings/target-candidates", { target_type: targetType, keyword: keyword || "" });
}
