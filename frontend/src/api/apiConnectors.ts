import { extractApiErrorMessage, fetchApi, postApi, putApi } from "@/api/client";
import type {
  ApiConnectorCallLog,
  ApiConnectorCredential,
  ApiConnectorLoadPreview,
  ApiConnectorLoadRun,
  ApiConnectorOperation,
  ApiConnectorOperationDetail,
  ApiConnectorPagination,
  ApiConnectorParam,
  ApiConnectorRequestPreview,
  ApiConnectorResponsePreview,
  ApiConnectorSnapshot,
  ApiConnectorTestCallResult,
  ApiConnectorTransformConfig,
  ApiConnectorTransformPreview,
} from "@/types/apiConnector";

export function apiConnectorErrorMessage(err: unknown, fallback: string): string {
  return extractApiErrorMessage(err, fallback);
}

export async function listApiConnectorOperations(dataSourceId?: string): Promise<ApiConnectorOperation[]> {
  return fetchApi("/api-connectors/operations", dataSourceId ? { data_source_id: dataSourceId } : undefined);
}

export async function getApiConnectorOperation(operationId: string): Promise<ApiConnectorOperationDetail> {
  return fetchApi(`/api-connectors/operations/${encodeURIComponent(operationId)}`);
}

export async function createApiConnectorOperation(body: Record<string, unknown>): Promise<ApiConnectorOperation> {
  return postApi("/api-connectors/operations", body);
}

export async function updateApiConnectorOperation(
  operationId: string,
  body: Record<string, unknown>,
): Promise<ApiConnectorOperation> {
  return putApi(`/api-connectors/operations/${encodeURIComponent(operationId)}`, body);
}

export async function archiveApiConnectorOperation(operationId: string): Promise<void> {
  await postApi(`/api-connectors/operations/${encodeURIComponent(operationId)}/archive`);
}

export async function getApiConnectorParams(operationId: string): Promise<ApiConnectorParam[]> {
  return fetchApi(`/api-connectors/operations/${encodeURIComponent(operationId)}/params`);
}

export async function replaceApiConnectorParams(
  operationId: string,
  params: ApiConnectorParam[],
): Promise<ApiConnectorParam[]> {
  return putApi(`/api-connectors/operations/${encodeURIComponent(operationId)}/params`, { params });
}

export async function getApiConnectorCredential(dataSourceId: string): Promise<ApiConnectorCredential | null> {
  try {
    return await fetchApi(`/api-connectors/data-sources/${encodeURIComponent(dataSourceId)}/credential`);
  } catch {
    return null;
  }
}

export async function upsertApiConnectorCredential(
  dataSourceId: string,
  body: Record<string, unknown>,
): Promise<ApiConnectorCredential> {
  return putApi(`/api-connectors/data-sources/${encodeURIComponent(dataSourceId)}/credential`, body);
}

export async function getApiConnectorPagination(operationId: string): Promise<ApiConnectorPagination | null> {
  try {
    return await fetchApi(`/api-connectors/operations/${encodeURIComponent(operationId)}/pagination`);
  } catch {
    return null;
  }
}

export async function upsertApiConnectorPagination(
  operationId: string,
  body: ApiConnectorPagination,
): Promise<ApiConnectorPagination> {
  return putApi(`/api-connectors/operations/${encodeURIComponent(operationId)}/pagination`, body);
}

export async function requestApiConnectorPreview(
  operationId: string,
  runtimeParams: Record<string, string> = {},
): Promise<ApiConnectorRequestPreview> {
  return postApi(`/api-connectors/operations/${encodeURIComponent(operationId)}/request-preview`, {
    runtime_params: runtimeParams,
  });
}

export async function testApiConnectorCall(
  operationId: string,
  runtimeParams: Record<string, string> = {},
): Promise<ApiConnectorTestCallResult> {
  return postApi(`/api-connectors/operations/${encodeURIComponent(operationId)}/test-call`, {
    runtime_params: runtimeParams,
  });
}

export async function responseApiConnectorPreview(
  operationId: string,
  runtimeParams: Record<string, string> = {},
): Promise<ApiConnectorResponsePreview> {
  return postApi(`/api-connectors/operations/${encodeURIComponent(operationId)}/response-preview`, {
    runtime_params: runtimeParams,
  });
}

export async function loadApiConnectorPreview(
  operationId: string,
  runtimeParams: Record<string, string> = {},
): Promise<ApiConnectorLoadPreview> {
  return postApi(`/api-connectors/operations/${encodeURIComponent(operationId)}/load-preview`, {
    runtime_params: runtimeParams,
  });
}

export async function runApiConnectorLoad(
  operationId: string,
  runtimeParams: Record<string, string> = {},
): Promise<ApiConnectorLoadRun> {
  return postApi(`/api-connectors/operations/${encodeURIComponent(operationId)}/load-run`, {
    runtime_params: runtimeParams,
  });
}

export async function getApiConnectorTransformConfig(
  operationId: string,
): Promise<ApiConnectorTransformConfig | null> {
  return fetchApi(`/api-connectors/operations/${encodeURIComponent(operationId)}/transform-config`);
}

export async function upsertApiConnectorTransformConfig(
  operationId: string,
  body: Partial<ApiConnectorTransformConfig>,
): Promise<ApiConnectorTransformConfig> {
  return putApi(`/api-connectors/operations/${encodeURIComponent(operationId)}/transform-config`, body);
}

export async function transformApiConnectorPreview(
  operationId: string,
  body: { raw_items?: Record<string, unknown>[]; runtime_params?: Record<string, string> } = {},
): Promise<ApiConnectorTransformPreview> {
  return postApi(`/api-connectors/operations/${encodeURIComponent(operationId)}/transform-preview`, body);
}

export async function listApiConnectorCallLogs(operationId?: string): Promise<ApiConnectorCallLog[]> {
  return fetchApi("/api-connectors/call-logs", operationId ? { operation_id: operationId } : undefined);
}

export async function listApiConnectorLoadRuns(operationId?: string): Promise<ApiConnectorLoadRun[]> {
  return fetchApi("/api-connectors/load-runs", operationId ? { operation_id: operationId } : undefined);
}

export async function getApiConnectorLoadRun(loadRunId: string): Promise<ApiConnectorLoadRun> {
  return fetchApi(`/api-connectors/load-runs/${encodeURIComponent(loadRunId)}`);
}

export async function getApiConnectorSnapshot(snapshotId: string): Promise<ApiConnectorSnapshot> {
  return fetchApi(`/api-connectors/snapshots/${encodeURIComponent(snapshotId)}`);
}
