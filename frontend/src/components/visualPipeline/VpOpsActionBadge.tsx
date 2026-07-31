import { Link } from "react-router-dom";
import {
  OPS_ACTION_REQUIRED_HREF,
  type OpsActionBadgeSummary,
} from "@/utils/opsActionRequired";

export interface VpOpsActionBadgeProps {
  badge: OpsActionBadgeSummary | null;
  loading?: boolean;
  /** Soft load failure — never crash the host page. */
  error?: boolean;
  /** Accessible short label (preferred: 확인 필요 / 운영 확인 필요 / 조치 필요). */
  label?: string;
  href?: string;
  size?: "sm" | "md";
  className?: string;
  testId?: string;
  /** When false, render span only (e.g. already on Ops page). */
  asLink?: boolean;
  onClick?: () => void;
}

const TONE_CLASS: Record<"error" | "warning" | "soft-error", string> = {
  error: "bg-red-600 text-white border-red-700",
  warning: "bg-amber-500 text-white border-amber-600",
  "soft-error": "bg-slate-200 text-slate-600 border-slate-300",
};

/**
 * R11-S8-9-21 / B5: derived Ops 「확인 필요」badge (read-model PoC).
 * Hidden when count is 0 or still loading. Soft-error shows a small "!" only.
 */
export function VpOpsActionBadge({
  badge,
  loading,
  error,
  label = "확인 필요",
  href = OPS_ACTION_REQUIRED_HREF,
  size = "sm",
  className = "",
  testId = "visual-pipeline-ops-action-badge",
  asLink = true,
  onClick,
}: VpOpsActionBadgeProps) {
  if (loading) {
    return null;
  }

  if (error && (!badge || badge.empty)) {
    return (
      <span
        className={`inline-flex items-center justify-center rounded-full border text-[9px] font-bold leading-none ${TONE_CLASS["soft-error"]} ${
          size === "md" ? "w-4 h-4" : "w-3.5 h-3.5"
        } ${className}`}
        title="운영 확인 상태를 불러오지 못했습니다"
        data-testid={`${testId}-error`}
        aria-label="운영 확인 상태 로드 실패"
      >
        !
      </span>
    );
  }

  if (!badge || badge.empty || badge.totalCount <= 0) {
    return null;
  }

  const pad = size === "md" ? "min-w-[1.25rem] h-5 px-1.5 text-[10px]" : "min-w-[1rem] h-4 px-1 text-[9px]";
  const body = (
    <span
      className={`inline-flex items-center justify-center rounded-full border font-bold tabular-nums leading-none ${pad} ${TONE_CLASS[badge.tone]} ${className}`}
      title={`${label} ${badge.totalCount}건 (ERROR ${badge.errorCount} · WARNING ${badge.warningCount})`}
      data-testid={testId}
      data-count={badge.totalCount}
      data-error-count={badge.errorCount}
      data-warning-count={badge.warningCount}
      data-tone={badge.tone}
      aria-label={`${label} ${badge.displayCount}건`}
    >
      {badge.displayCount}
    </span>
  );

  if (!asLink) {
    if (onClick) {
      return (
        <button
          type="button"
          className="inline-flex items-center gap-1 align-middle"
          onClick={onClick}
          data-testid={`${testId}-button`}
        >
          {body}
        </button>
      );
    }
    return body;
  }

  return (
    <Link
      to={href}
      className="inline-flex items-center gap-1 align-middle no-underline"
      onClick={onClick}
      data-testid={`${testId}-link`}
      aria-label={`${label} — Visual Pipeline 운영으로 이동`}
    >
      {body}
    </Link>
  );
}
