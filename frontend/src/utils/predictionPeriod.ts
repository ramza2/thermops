export interface FeatureDatasetSiteRange {
  site_id: string;
  min_target_at: string | null;
  max_target_at: string | null;
  row_count: number;
}

export interface FeatureDatasetRange {
  feature_set_id: string;
  exists: boolean;
  row_count: number;
  min_target_at: string | null;
  max_target_at: string | null;
  site_count: number;
  sites: FeatureDatasetSiteRange[];
  dataset_version_id?: string | null;
}

export interface ApiErrorDetail {
  error_code?: string;
  message?: string;
  feature_set_id?: string;
  requested_start_at?: string;
  requested_end_at?: string;
  available_start_at?: string;
  available_end_at?: string;
}

/** naive ISO (2026-06-20T23:00:00) → datetime-local value */
export function parseNaiveIso(iso: string): Date {
  const [datePart, timePart = "00:00:00"] = iso.split("T");
  const [y, m, d] = datePart.split("-").map(Number);
  const [hh, mm, ss = "0"] = timePart.split(":");
  return new Date(y, m - 1, d, Number(hh), Number(mm), Number(ss.split(".")[0]));
}

export function toDatetimeLocalValue(d: Date): string {
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

export function formatDisplayDateTime(iso: string | null | undefined): string {
  if (!iso) return "-";
  const d = parseNaiveIso(iso);
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

export function effectiveRange(
  range: FeatureDatasetRange | null,
  siteId: string,
): { min: string | null; max: string | null; rowCount: number; siteCount: number } {
  if (!range?.exists) {
    return { min: null, max: null, rowCount: 0, siteCount: 0 };
  }
  if (siteId) {
    const site = range.sites.find((s) => s.site_id === siteId);
    if (site) {
      return {
        min: site.min_target_at,
        max: site.max_target_at,
        rowCount: site.row_count,
        siteCount: 1,
      };
    }
    return { min: null, max: null, rowCount: 0, siteCount: 0 };
  }
  return {
    min: range.min_target_at,
    max: range.max_target_at,
    rowCount: range.row_count,
    siteCount: range.site_count,
  };
}

export function defaultPredictionPeriod(range: FeatureDatasetRange): { start: string; end: string } {
  if (!range.exists || !range.min_target_at || !range.max_target_at) {
    return { start: "", end: "" };
  }
  const min = parseNaiveIso(range.min_target_at);
  const max = parseNaiveIso(range.max_target_at);
  const spanMs = max.getTime() - min.getTime();
  const dayMs = 24 * 60 * 60 * 1000;
  let start = min;
  if (spanMs >= dayMs - 3_600_000) {
    start = new Date(max.getTime() - dayMs + 3_600_000);
    if (start < min) start = min;
  }
  return { start: toDatetimeLocalValue(start), end: toDatetimeLocalValue(max) };
}

export function isPeriodWithinRange(
  startLocal: string,
  endLocal: string,
  minIso: string | null,
  maxIso: string | null,
): boolean {
  if (!startLocal || !endLocal || !minIso || !maxIso) return false;
  const start = parseNaiveIso(startLocal.length === 16 ? `${startLocal}:00` : startLocal);
  const end = parseNaiveIso(endLocal.length === 16 ? `${endLocal}:00` : endLocal);
  const min = parseNaiveIso(minIso);
  const max = parseNaiveIso(maxIso);
  return start >= min && end <= max && start <= end;
}

export function extractApiError(err: unknown): { message: string; detail?: ApiErrorDetail } {
  const raw = (err as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail;
  if (typeof raw === "string") return { message: raw };
  if (raw && typeof raw === "object") {
    const detail = raw as ApiErrorDetail;
    return { message: detail.message || "요청에 실패했습니다.", detail };
  }
  return { message: "예측 실행에 실패했습니다." };
}

export function formatPeriodErrorMessage(detail: ApiErrorDetail): string {
  if (detail.error_code === "PREDICTION_PERIOD_OUT_OF_FEATURE_RANGE") {
    const from = formatDisplayDateTime(detail.available_start_at);
    const to = formatDisplayDateTime(detail.available_end_at);
    return `선택한 Feature Set의 사용 가능한 데이터 기간은 ${from} ~ ${to}입니다. 예측 기간을 이 범위 안으로 선택해 주세요.`;
  }
  if (detail.error_code === "NO_FEATURE_DATASET") {
    return "이 Feature Set으로 생성된 Feature Dataset이 없습니다. Feature Set 상세 화면에서 Feature 생성을 먼저 실행하세요.";
  }
  return detail.message || "예측 실행에 실패했습니다.";
}
