import { useState } from "react";
import {
  CATCHUP_NOT_AUTO_RECOVERY,
  CATCHUP_PRE_RUN_CHECKLIST,
  CATCHUP_SUMMARY,
  CATCHUP_TERM_DEFINITIONS,
} from "@/utils/catchupGuidance";
import {
  describeScheduleSkipReason,
  nextChecksForScheduleSkipReason,
} from "@/utils/scheduleSkipReason";

interface VpCatchupGuidanceProps {
  /** When present, show reason description + next-check hints. */
  skipReasonCode?: string | null;
  defaultExpanded?: boolean;
}

export function VpCatchupGuidance({
  skipReasonCode,
  defaultExpanded = false,
}: VpCatchupGuidanceProps) {
  const [expanded, setExpanded] = useState(defaultExpanded);
  const hasReason = !!String(skipReasonCode || "").trim();
  const nextChecks = hasReason ? nextChecksForScheduleSkipReason(skipReasonCode) : [];

  return (
    <div
      className="rounded-md border border-teal-200/80 bg-white/80 px-2.5 py-2 space-y-1.5"
      data-testid="visual-pipeline-catchup-guidance"
    >
      <div className="text-[10px] font-bold text-teal-900 uppercase tracking-wide">Catch-up 안내</div>
      <p className="text-[11px] text-slate-700" data-testid="visual-pipeline-catchup-guidance-summary">
        {CATCHUP_SUMMARY}
      </p>
      <p
        className="text-[11px] font-medium text-amber-900"
        data-testid="visual-pipeline-catchup-guidance-not-auto"
      >
        {CATCHUP_NOT_AUTO_RECOVERY}
      </p>

      {hasReason && (
        <div
          className="rounded border border-slate-100 bg-slate-50/80 px-2 py-1.5 space-y-1"
          data-testid="visual-pipeline-catchup-guidance-reason"
          data-reason-code={String(skipReasonCode).trim().toUpperCase()}
        >
          <div className="text-[10px] font-semibold text-slate-600">
            skip reason · <span className="font-mono">{String(skipReasonCode).trim()}</span>
          </div>
          <p className="text-[11px] text-slate-700">{describeScheduleSkipReason(skipReasonCode)}</p>
          <ul
            className="list-disc pl-4 space-y-0.5 text-[10px] text-slate-600"
            data-testid="visual-pipeline-catchup-guidance-next-checks"
          >
            {nextChecks.map((line) => (
              <li key={line}>{line}</li>
            ))}
          </ul>
        </div>
      )}

      <button
        type="button"
        className="text-[10px] font-medium text-teal-900 border border-teal-200 bg-white rounded px-2 py-0.5 hover:bg-teal-50"
        data-testid="visual-pipeline-catchup-guidance-toggle"
        aria-expanded={expanded}
        onClick={() => setExpanded((v) => !v)}
      >
        {expanded ? "상세 안내 접기" : "상세 안내 보기"}
      </button>

      {expanded && (
        <div
          className="space-y-2 border-t border-teal-100 pt-2"
          data-testid="visual-pipeline-catchup-guidance-details"
        >
          <div data-testid="visual-pipeline-catchup-guidance-terms">
            <div className="text-[10px] font-semibold text-slate-600 mb-1">용어</div>
            <dl className="space-y-1.5">
              {CATCHUP_TERM_DEFINITIONS.map((term) => (
                <div key={term.id} data-testid={`visual-pipeline-catchup-guidance-term-${term.id}`}>
                  <dt className="text-[10px] font-mono font-semibold text-slate-700">{term.label}</dt>
                  <dd className="text-[11px] text-slate-600">{term.description}</dd>
                </div>
              ))}
            </dl>
          </div>

          <div data-testid="visual-pipeline-catchup-guidance-checklist">
            <div className="text-[10px] font-semibold text-slate-600 mb-1">
              실행 전 확인사항 (안내 · 저장되지 않음)
            </div>
            <ul className="space-y-1">
              {CATCHUP_PRE_RUN_CHECKLIST.map((item) => (
                <li key={item} className="flex items-start gap-1.5 text-[11px] text-slate-700">
                  <span
                    className="mt-0.5 inline-block h-3 w-3 shrink-0 rounded border border-slate-300 bg-white"
                    aria-hidden
                  />
                  <span>{item}</span>
                </li>
              ))}
            </ul>
          </div>
        </div>
      )}
    </div>
  );
}
