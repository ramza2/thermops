import { fetchApi, postApi, putApi } from "@/api/client";
import type {
  StandardDatasetType,
  StandardDatasetTypeCreateRequest,
  StandardDatasetTypeUpdateRequest,
  StandardDatasetValidation,
  StandardTargetTable,
} from "@/types/standardDatasets";

export async function getStandardDatasetTypes(params?: {
  status?: string;
  domain?: string;
  category?: string;
  mapping_supported?: boolean;
  recipe_supported?: boolean;
  build_supported?: boolean;
  include_columns?: boolean;
  include_planned?: boolean;
}): Promise<{ items: StandardDatasetType[]; total: number }> {
  return fetchApi("/standard-dataset-types", params);
}

export async function getStandardDatasetType(
  id: string,
  params?: { include_columns?: boolean; include_recipe_availability?: boolean },
): Promise<StandardDatasetType> {
  return fetchApi(`/standard-dataset-types/${encodeURIComponent(id)}`, params);
}

export async function getStandardTargetTables(params?: {
  mapping_supported?: boolean;
  active_only?: boolean;
}): Promise<{ items: StandardTargetTable[] }> {
  return fetchApi("/standard-target-tables", params);
}

export async function validateTargetTable(targetTable: string): Promise<StandardDatasetValidation> {
  return postApi("/standard-dataset-types/validate-target-table", { target_table: targetTable });
}

export async function createStandardDatasetType(
  payload: StandardDatasetTypeCreateRequest,
): Promise<StandardDatasetType> {
  return postApi("/standard-dataset-types", payload);
}

export async function updateStandardDatasetType(
  id: string,
  payload: StandardDatasetTypeUpdateRequest,
): Promise<StandardDatasetType> {
  return putApi(`/standard-dataset-types/${encodeURIComponent(id)}`, payload);
}

export async function activateStandardDatasetType(id: string): Promise<StandardDatasetType> {
  return postApi(`/standard-dataset-types/${encodeURIComponent(id)}/activate`);
}

export async function archiveStandardDatasetType(id: string): Promise<StandardDatasetType> {
  return postApi(`/standard-dataset-types/${encodeURIComponent(id)}/archive`);
}
