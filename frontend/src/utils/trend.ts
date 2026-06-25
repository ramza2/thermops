export type TrendDataSource = "MATCHED" | "PREDICTION_ONLY" | "EMPTY";

export interface TrendItem {
  time: string;
  predicted: number;
  actual: number | null;
  error: number | null;
  target_at?: string;
}

export interface TrendResponse {
  data_source: TrendDataSource;
  items: TrendItem[];
  count: number;
}

/** API 응답(신규 객체 / 구 배열)을 안전하게 TrendResponse로 변환 */
export function normalizeTrendResponse(raw: unknown): TrendResponse {
  if (Array.isArray(raw)) {
    const items = raw as TrendItem[];
    const dataSource: TrendDataSource = items.some((t) => t?.actual != null)
      ? "MATCHED"
      : items.length > 0
        ? "PREDICTION_ONLY"
        : "EMPTY";
    return { data_source: dataSource, items, count: items.length };
  }

  if (raw && typeof raw === "object") {
    const obj = raw as Partial<TrendResponse>;
    const items = Array.isArray(obj.items) ? obj.items : [];
    const dataSource = (obj.data_source as TrendDataSource | undefined)
      ?? (items.length === 0 ? "EMPTY" : items.some((t) => t?.actual != null) ? "MATCHED" : "PREDICTION_ONLY");
    return {
      data_source: dataSource,
      items,
      count: typeof obj.count === "number" ? obj.count : items.length,
    };
  }

  return { data_source: "EMPTY", items: [], count: 0 };
}

export function trendChartTitle(dataSource: TrendDataSource): string {
  if (dataSource === "MATCHED") return "예측 vs 실제 추이 (예측값-실제값 매칭)";
  if (dataSource === "PREDICTION_ONLY") return "예측 추이 (실제값 매칭 전)";
  return "예측 추이";
}

export function trendChartSubtitle(dataSource: TrendDataSource): string | undefined {
  if (dataSource === "PREDICTION_ONLY") return "실제값 매칭 전 — 예측 결과만 표시됩니다.";
  if (dataSource === "MATCHED") return "운영 예측 추이: 예측값-실제값 매칭 기준";
  return undefined;
}

export function monitoringTrendChartTitle(dataSource: TrendDataSource): string {
  if (dataSource === "MATCHED") return "운영 예측 추이: 예측값-실제값 매칭 기준";
  if (dataSource === "PREDICTION_ONLY") return "실제값 매칭 전 예측 추이";
  return "예측 성능 추이";
}
