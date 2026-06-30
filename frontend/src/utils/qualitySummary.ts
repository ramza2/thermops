import { formatDisplayDateTime } from "@/utils/predictionPeriod";

export interface QualitySummary {
  quality_score?: number;
  missing_count?: number;
  duplicate_count?: number;
  time_gap_count?: number;
  outlier_count?: number;
  invalid_reference_count?: number;
  missing_rate?: number;
  total_count?: number;
  target_table?: string;
  data_domain?: string;
  checked_start_at?: string | null;
  checked_end_at?: string | null;
  min_history_hours?: number;
  warnings?: string[];
  errors?: string[];
  checks?: QualitySummary[];
  check_type?: string;
}

export interface QualityRun {
  run_id: string;
  source_id: string | null;
  check_type: string;
  run_status: string;
  result_summary: QualitySummary | null;
  started_at: string;
  finished_at: string | null;
}

function formatMetricsLine(s: QualitySummary): string {
  const score = s.quality_score != null ? `점수 ${s.quality_score.toFixed(1)}` : null;
  const missing = s.missing_count != null
    ? `결측 ${s.missing_count}`
    : s.missing_rate != null
      ? `결측 ${(s.missing_rate * 100).toFixed(1)}%`
      : null;
  return [
    score,
    missing,
    `중복 ${s.duplicate_count ?? 0}`,
    `시간누락 ${s.time_gap_count ?? 0}`,
    `이상치 ${s.outlier_count ?? 0}`,
  ].filter(Boolean).join(" · ");
}

export function formatQualityTableSummary(
  summary: QualitySummary | null | undefined,
  runStatus?: string,
): string {
  if (!summary) {
    return runStatus === "FAILED" ? "실패 (상세 없음)" : "-";
  }
  if (summary.errors?.length) {
    const first = summary.errors[0];
    const extra = summary.errors.length > 1 ? ` 외 ${summary.errors.length - 1}건` : "";
    return `실패: ${first}${extra}`;
  }
  if (runStatus === "WARNING" && summary.warnings?.length) {
    const first = summary.warnings[0];
    const extra = summary.warnings.length > 1 ? ` 외 ${summary.warnings.length - 1}건` : "";
    return `주의: ${first}${extra}`;
  }
  return formatMetricsLine(summary);
}

export function extractQualityCheckError(err: unknown): string {
  const raw = (err as { response?: { data?: { detail?: unknown; message?: string } } })?.response?.data;
  if (typeof raw?.detail === "string") return raw.detail;
  if (raw?.detail && typeof raw.detail === "object") {
    const detail = raw.detail as { message?: string; errors?: string[] };
    if (detail.errors?.length) return detail.errors[0];
    if (detail.message) return detail.message;
  }
  if (typeof raw?.message === "string" && raw.message) return raw.message;
  return "품질 점검 실행에 실패했습니다.";
}

function formatPeriod(start?: string | null, end?: string | null): string {
  if (!start && !end) return "-";
  return `${formatDisplayDateTime(start)} ~ ${formatDisplayDateTime(end)}`;
}

export function qualityMetricsRows(summary: QualitySummary): { label: string; value: string }[] {
  const rows: { label: string; value: string }[] = [
    { label: "품질 점수", value: summary.quality_score != null ? summary.quality_score.toFixed(2) : "-" },
    { label: "점검 건수", value: summary.total_count != null ? summary.total_count.toLocaleString() : "-" },
    { label: "점검 기간", value: formatPeriod(summary.checked_start_at, summary.checked_end_at) },
    { label: "결측", value: summary.missing_count != null ? String(summary.missing_count) : "-" },
    { label: "중복", value: String(summary.duplicate_count ?? 0) },
    { label: "시간 누락", value: String(summary.time_gap_count ?? 0) },
    { label: "이상치", value: String(summary.outlier_count ?? 0) },
    { label: "무효 참조", value: String(summary.invalid_reference_count ?? 0) },
  ];
  if (summary.min_history_hours != null) {
    rows.push({ label: "최소 이력(시간)", value: String(summary.min_history_hours) });
  }
  return rows;
}
