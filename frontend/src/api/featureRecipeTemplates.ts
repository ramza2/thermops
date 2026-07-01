import type {
  RecipeTemplate,
  RecipeTemplateListResponse,
  RecipeValidateRequest,
  RecipeValidateResponse,
  FeatureRecipePreviewRequest,
  FeatureRecipePreviewResponse,
} from "@/types/featureRecipeTemplates";
import { fetchApi, postApi } from "@/api/client";

export async function getFeatureRecipeTemplates(params?: {
  mapping_id?: string;
  category?: string;
  status?: string;
  include_availability?: boolean;
}): Promise<RecipeTemplateListResponse> {
  return fetchApi<RecipeTemplateListResponse>("/feature-recipe-templates", params);
}

export async function getFeatureRecipeTemplate(
  recipeType: string,
  params?: { mapping_id?: string; include_availability?: boolean },
): Promise<RecipeTemplate> {
  return fetchApi<RecipeTemplate>(`/feature-recipe-templates/${encodeURIComponent(recipeType)}`, params);
}

export async function validateFeatureRecipe(body: RecipeValidateRequest): Promise<RecipeValidateResponse> {
  return postApi<RecipeValidateResponse>("/feature-recipes/validate", body);
}

export async function previewFeatureRecipe(
  body: FeatureRecipePreviewRequest,
): Promise<FeatureRecipePreviewResponse> {
  return postApi<FeatureRecipePreviewResponse>("/feature-recipes/preview", body);
}
