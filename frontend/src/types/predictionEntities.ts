export interface WeatherReadiness {
  entity_id: string;
  location_ready: boolean;
  forecast_ready: boolean;
  observation_ready: boolean;
  prediction_input_ready: boolean;
  training_weather_ready: boolean;
  warnings: string[];
}

export interface PredictionEntity {
  entity_id: string;
  entity_code: string;
  entity_name: string;
  entity_type: string;
  business_domain?: string | null;
  description?: string | null;
  active_yn: boolean;
  created_at?: string;
  updated_at?: string;
  weather_readiness?: WeatherReadiness;
}

export interface PredictionEntityLocation {
  location_id: string;
  entity_id: string;
  address?: string | null;
  latitude?: number | null;
  longitude?: number | null;
  location_source?: string;
  active_yn: boolean;
}

export interface ForecastGrid {
  forecast_grid_id: string;
  grid_system: string;
  nx: number;
  ny: number;
  grid_name?: string | null;
  latitude?: number | null;
  longitude?: number | null;
  active_yn: boolean;
}

export interface ObservationStation {
  station_id: string;
  station_code: string;
  station_name: string;
  station_type: string;
  latitude?: number | null;
  longitude?: number | null;
  address?: string | null;
  active_yn: boolean;
}

export interface WeatherMapping {
  mapping_id: string;
  entity_id: string;
  forecast_grid_id?: string | null;
  station_id?: string | null;
  mapping_type: string;
  mapping_method?: string;
  priority: number;
  active_yn: boolean;
  forecast_grid?: ForecastGrid;
  observation_station?: ObservationStation;
}

export interface PredictionEntityDetail extends PredictionEntity {
  locations?: PredictionEntityLocation[];
  weather_mappings?: WeatherMapping[];
}

export const ENTITY_TYPE_OPTIONS = [
  { value: "SITE", label: "지점 (SITE)" },
  { value: "BRANCH", label: "지사 (BRANCH)" },
  { value: "FACILITY", label: "설비 (FACILITY)" },
  { value: "REGION", label: "지역 (REGION)" },
  { value: "ZONE", label: "구역 (ZONE)" },
  { value: "CUSTOM", label: "사용자 정의 (CUSTOM)" },
];
