import { fetchApi, postApi, putApi } from "@/api/client";
import type { ForecastPreviewResult, ForecastProviderConfig } from "@/types/forecastProvider";

export async function getForecastProviderConfig(): Promise<ForecastProviderConfig> {
  return fetchApi("/forecast-provider/config");
}

export async function saveForecastProviderConfig(body: Partial<ForecastProviderConfig>): Promise<ForecastProviderConfig> {
  return putApi("/forecast-provider/config", body);
}

export async function resolveForecastBaseTime(body?: { base_date?: string; base_time?: string }): Promise<{
  base_date: string;
  base_time: string;
  forecast_base_at?: string;
  policy?: string;
}> {
  return postApi("/forecast-provider/resolve-base-time", body || {});
}

export async function previewForecastInput(body: Record<string, unknown>): Promise<ForecastPreviewResult> {
  return postApi("/forecast-provider/preview-input", body);
}

export async function previewForecastRequest(body: Record<string, unknown>) {
  return postApi("/forecast-provider/request-preview", body);
}

export async function listConnectorOperations(): Promise<{ operation_id: string; operation_name: string }[]> {
  return fetchApi("/api-connectors/operations");
}

export async function listForecastSnapshots(params?: { prediction_job_id?: string; entity_id?: string }) {
  const q = new URLSearchParams();
  if (params?.prediction_job_id) q.set("prediction_job_id", params.prediction_job_id);
  if (params?.entity_id) q.set("entity_id", params.entity_id);
  const suffix = q.toString() ? `?${q.toString()}` : "";
  return fetchApi(`/forecast-provider/snapshots${suffix}`);
}

export async function getPredictionWeatherInputs(predictionJobId: string) {
  return fetchApi(`/prediction-jobs/${encodeURIComponent(predictionJobId)}/weather-inputs`);
}
