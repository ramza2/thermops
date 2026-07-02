import type {
  FeatureRecipe,
  FeatureRecipeCreateRequest,
  FeatureRecipeListResponse,
  FeatureSetAddRecipeFeatureResult,
} from "@/types/featureRecipes";
import type { FeatureRecipePreviewResponse } from "@/types/featureRecipeTemplates";
import { fetchApi, postApi, putApi } from "@/api/client";

export async function createFeatureRecipe(
  body: FeatureRecipeCreateRequest,
): Promise<FeatureRecipe & { validate_result?: Record<string, unknown> }> {
  return postApi("/feature-recipes", body);
}

export async function listFeatureRecipes(params?: {
  status?: string;
  recipe_type?: string;
  mapping_id?: string;
  feature_name?: string;
  include_archived?: boolean;
  limit?: number;
  offset?: number;
}): Promise<FeatureRecipeListResponse> {
  return fetchApi<FeatureRecipeListResponse>("/feature-recipes", params);
}

export async function getFeatureRecipe(recipeId: string): Promise<FeatureRecipe> {
  return fetchApi<FeatureRecipe>(`/feature-recipes/${encodeURIComponent(recipeId)}`);
}

export async function updateFeatureRecipe(
  recipeId: string,
  body: Partial<FeatureRecipeCreateRequest>,
): Promise<FeatureRecipe> {
  return putApi<FeatureRecipe>(`/feature-recipes/${encodeURIComponent(recipeId)}`, body);
}

export async function archiveFeatureRecipe(recipeId: string): Promise<FeatureRecipe> {
  return postApi<FeatureRecipe>(`/feature-recipes/${encodeURIComponent(recipeId)}/archive`, {});
}

export async function validateSavedFeatureRecipe(recipeId: string): Promise<{
  recipe: FeatureRecipe;
  validation: Record<string, unknown>;
}> {
  return postApi(`/feature-recipes/${encodeURIComponent(recipeId)}/validate`, {});
}

export async function previewSavedFeatureRecipe(
  recipeId: string,
  sampleSize = 100,
): Promise<{
  recipe: FeatureRecipe;
  preview: FeatureRecipePreviewResponse;
  preview_summary: Record<string, unknown>;
}> {
  return postApi(`/feature-recipes/${encodeURIComponent(recipeId)}/preview`, { sample_size: sampleSize });
}

export async function publishFeatureRecipe(recipeId: string): Promise<{
  recipe: FeatureRecipe;
  feature: Record<string, unknown>;
  warnings: string[];
}> {
  return postApi(`/feature-recipes/${encodeURIComponent(recipeId)}/publish`, {});
}

export async function addRecipeFeatureToFeatureSet(
  featureSetId: string,
  body: { recipe_id: string; feature_name?: string },
): Promise<FeatureSetAddRecipeFeatureResult> {
  return postApi<FeatureSetAddRecipeFeatureResult>(
    `/feature-sets/${encodeURIComponent(featureSetId)}/add-recipe-feature`,
    body,
  );
}

export interface RecipeBuildHistoryItem {
  job_id: string;
  feature_set_id: string;
  dataset_version_id?: string;
  status: string;
  template_feature_status: string;
  started_at?: string;
  row_count?: number;
  null_ratio?: number;
  warning_codes?: string[];
  error_codes?: string[];
  warnings?: string[];
}

export interface RecipeBuildHistoryResponse {
  recipe_id: string;
  feature_name: string | null;
  latest_build_status: string;
  items: RecipeBuildHistoryItem[];
  total: number;
}

export async function getRecipeBuildHistory(
  recipeId: string,
  limit = 20,
): Promise<RecipeBuildHistoryResponse> {
  return fetchApi<RecipeBuildHistoryResponse>(
    `/feature-recipes/${encodeURIComponent(recipeId)}/build-history`,
    { limit },
  );
}

export async function compareRecipePreviewBuild(
  recipeId: string,
  body: { dataset_version_id: string; feature_set_id?: string; sample_size?: number },
): Promise<Record<string, unknown>> {
  return postApi(`/feature-recipes/${encodeURIComponent(recipeId)}/compare-preview-build`, body);
}
