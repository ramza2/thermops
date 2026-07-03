import { fetchApi, postApi, putApi } from "@/api/client";
import type {
  StandardDatasetMetadataOptions,
  StandardDatasetType,
  StandardDatasetTypeCreateRequest,
  StandardDatasetTypeUpdateRequest,
  StandardDatasetValidation,
  StandardTargetTable,
} from "@/types/standardDatasets";

export async function getStandardDatasetMetadataOptions(): Promise<StandardDatasetMetadataOptions> {
  return fetchApi("/standard-datasets/metadata-options");
}

export async function getStandardDatasetTypes(params?: {
  status?: string;
  business_domain?: string;
  dataset_category?: string;
  tag?: string;
  keyword?: string;
  physical_table_exists_yn?: string;
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

export async function suggestTableName(datasetCode: string): Promise<{ physical_table_name: string }> {
  return fetchApi("/standard-dataset-types/suggest-table-name", { dataset_code: datasetCode });
}

export async function validateDatasetDefinition(id: string): Promise<WizardValidationResult> {
  return postApi(`/standard-dataset-types/${encodeURIComponent(id)}/validate`);
}

export async function previewCreateTable(id: string): Promise<WizardValidationResult> {
  return postApi(`/standard-dataset-types/${encodeURIComponent(id)}/preview-create-table`);
}

export async function createPhysicalTable(id: string, confirm = true): Promise<WizardCreateResult> {
  return postApi(`/standard-dataset-types/${encodeURIComponent(id)}/create-physical-table`, { confirm });
}

export interface WizardValidationResult {
  valid: boolean;
  errors?: { code: string; message: string }[];
  warnings?: { code: string; message: string }[];
  sql_preview?: string | null;
  physical_table_name?: string;
  lifecycle_status?: string;
}

export interface WizardCreateResult {
  status: string;
  physical_table_name: string;
  physical_table_exists_yn?: string;
  lifecycle_status?: string;
  dataset_type?: StandardDatasetType;
}
