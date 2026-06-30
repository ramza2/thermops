import type {
  ColumnRoleCode,
  FeatureColumnRole,
  FeatureColumnRoleInferRequest,
  FeatureColumnRoleListResponse,
  FeatureColumnRoleBulkUpdateRequest,
  FeatureColumnRoleValidation,
} from "@/types/featureColumnRoles";
import { fetchApi, postApi, putApi } from "@/api/client";

export async function getColumnRoleCodes(): Promise<{ items: ColumnRoleCode[] }> {
  return fetchApi<{ items: ColumnRoleCode[] }>("/feature-column-role-codes");
}

export async function getColumnRoles(params: {
  mapping_id?: string;
  include_inferred?: boolean;
}): Promise<FeatureColumnRoleListResponse> {
  return fetchApi<FeatureColumnRoleListResponse>("/feature-column-roles", params);
}

export async function inferColumnRoles(
  body: FeatureColumnRoleInferRequest,
): Promise<FeatureColumnRoleListResponse> {
  return postApi<FeatureColumnRoleListResponse>("/feature-column-roles/infer", body);
}

export async function validateColumnRoles(body: {
  mapping_id?: string;
  roles: { source_column: string; target_column?: string | null; column_role: string }[];
  mapping_columns?: { source_column: string; target_column?: string | null; data_type?: string | null }[];
}): Promise<{ validation: FeatureColumnRoleValidation; summary: FeatureColumnRoleListResponse["summary"] }> {
  return postApi("/feature-column-roles/validate", body);
}

export async function saveColumnRoles(
  body: FeatureColumnRoleBulkUpdateRequest,
): Promise<FeatureColumnRoleListResponse & { saved_count: number }> {
  return putApi("/feature-column-roles", body);
}

export type { FeatureColumnRole };
