import {
  formatDisplayDateTime,
  isPeriodWithinRange,
  toDatetimeLocalValue,
  parseNaiveIso,
} from "@/utils/predictionPeriod";

export interface SourceDataRange {
  source_id: string;
  exists: boolean;
  row_count: number;
  valid_timestamp_count: number;
  min_at: string | null;
  max_at: string | null;
  timestamp_column: string | null;
  message?: string;
}

export const INGESTION_LIMIT_OPTIONS = [
  { value: "", label: "무제한" },
  { value: "100", label: "100건" },
  { value: "500", label: "500건" },
  { value: "1000", label: "1,000건" },
  { value: "5000", label: "5,000건" },
  { value: "10000", label: "10,000건" },
] as const;

export function defaultIngestionPeriod(range: SourceDataRange): { start: string; end: string } {
  if (!range.exists || !range.min_at || !range.max_at) {
    return { start: "", end: "" };
  }
  return {
    start: toDatetimeLocalValue(parseNaiveIso(range.min_at)),
    end: toDatetimeLocalValue(parseNaiveIso(range.max_at)),
  };
}

export function toNaiveApiDateTime(localValue: string): string {
  if (!localValue) return "";
  return localValue.length === 16 ? `${localValue}:00` : localValue;
}

export function validateCsvIngestionPeriod(
  startLocal: string,
  endLocal: string,
  range: SourceDataRange | null,
): string | null {
  if (!range?.exists) {
    return "CSV 파일에서 시각 컬럼(measured_at)을 찾을 수 없습니다. 파일 경로와 컬럼을 확인하세요.";
  }
  if (!startLocal || !endLocal) {
    return "적재 기간 시작·종료를 입력하세요.";
  }
  if (startLocal > endLocal) {
    return "시작 시각은 종료 시각보다 이전이어야 합니다.";
  }
  if (!isPeriodWithinRange(startLocal, endLocal, range.min_at, range.max_at)) {
    return `CSV 파일의 사용 가능한 데이터 기간은 ${formatDisplayDateTime(range.min_at)} ~ ${formatDisplayDateTime(range.max_at)}입니다. 적재 기간을 이 범위 안으로 선택해 주세요.`;
  }
  return null;
}

export { formatDisplayDateTime, isPeriodWithinRange };
