export function formatQualityStatusLabel(status: string): string {
  switch (status) {
    case "SUCCESS":
      return "정상";
    case "WARNING":
      return "주의";
    case "FAILED":
      return "실패";
    case "RUNNING":
      return "실행 중";
    default:
      return status;
  }
}

export function formatPercent(ratio: number | null | undefined, digits = 1): string {
  if (ratio == null || Number.isNaN(ratio)) return "-";
  return `${(ratio * 100).toFixed(digits)}%`;
}

export function formatNumber(val: number | null | undefined, digits = 2): string {
  if (val == null || Number.isNaN(val)) return "-";
  return val.toLocaleString("ko-KR", { maximumFractionDigits: digits });
}

export function formatScore(score: number | null | undefined): string {
  if (score == null || Number.isNaN(score)) return "-";
  return score.toFixed(1);
}
