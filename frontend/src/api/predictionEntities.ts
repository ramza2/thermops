import { fetchApi, postApi, putApi } from "@/api/client";
import type {
  ForecastGrid,
  ObservationStation,
  PredictionEntity,
  PredictionEntityDetail,
  PredictionEntityLocation,
  WeatherMapping,
  WeatherReadiness,
} from "@/types/predictionEntities";

export async function listPredictionEntities(params?: Record<string, string | boolean>): Promise<PredictionEntity[]> {
  return fetchApi("/prediction-entities", params);
}

export async function getPredictionEntity(entityId: string): Promise<PredictionEntityDetail> {
  return fetchApi(`/prediction-entities/${encodeURIComponent(entityId)}`);
}

export async function createPredictionEntity(body: Record<string, unknown>): Promise<PredictionEntity> {
  return postApi("/prediction-entities", body);
}

export async function updatePredictionEntity(entityId: string, body: Record<string, unknown>): Promise<PredictionEntity> {
  return putApi(`/prediction-entities/${encodeURIComponent(entityId)}`, body);
}

export async function archivePredictionEntity(entityId: string): Promise<PredictionEntity> {
  return postApi(`/prediction-entities/${encodeURIComponent(entityId)}/archive`);
}

export async function createEntityLocation(entityId: string, body: Record<string, unknown>): Promise<PredictionEntityLocation> {
  return postApi(`/prediction-entities/${encodeURIComponent(entityId)}/locations`, body);
}

export async function convertLatLonToGrid(latitude: number, longitude: number): Promise<{ nx: number; ny: number; grid_system: string; hint?: string }> {
  return postApi("/weather/convert-latlon-to-grid", { latitude, longitude });
}

export async function upsertForecastGrid(body: Record<string, unknown>): Promise<ForecastGrid> {
  return postApi("/weather/forecast-grids", body);
}

export async function listForecastGrids(): Promise<ForecastGrid[]> {
  return fetchApi("/weather/forecast-grids");
}

export async function upsertObservationStation(body: Record<string, unknown>): Promise<ObservationStation> {
  return postApi("/weather/observation-stations", body);
}

export async function listObservationStations(): Promise<ObservationStation[]> {
  return fetchApi("/weather/observation-stations");
}

export async function createWeatherMapping(entityId: string, body: Record<string, unknown>): Promise<WeatherMapping> {
  return postApi(`/prediction-entities/${encodeURIComponent(entityId)}/weather-mappings`, body);
}

export async function getWeatherReadiness(entityId: string): Promise<WeatherReadiness> {
  return fetchApi(`/prediction-entities/${encodeURIComponent(entityId)}/weather-readiness`);
}

export async function getWeatherMappingPreview(entityId: string): Promise<WeatherReadiness & { grid_suggestion?: { nx: number; ny: number } }> {
  return postApi(`/prediction-entities/${encodeURIComponent(entityId)}/weather-mapping-preview`);
}
