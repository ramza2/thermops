import type { PartialImpactSummary } from "@/utils/partialImpactSummary";

interface VpPartialImpactCardProps {
  summary: PartialImpactSummary;
  /** When conflict keys could not be loaded from graph. */
  conflictKeysFallback?: boolean;
  testIdPrefix?: string;
}

function fmtCount(n: number | undefined): string {
  if (n == null) return "-";
  return String(n);
}

export function VpPartialImpactCard({
  summary,
  conflictKeysFallback,
  testIdPrefix = "visual-pipeline-run-detail",
}: VpPartialImpactCardProps) {
  if (summary.severity === "none") return null;

  const hints = summary.rowHints;

  return (
    <section
      className="rounded-md border border-amber-200 bg-amber-50/60 px-2.5 py-2 space-y-2"
      data-testid={`${testIdPrefix}-partial-impact`}
      data-severity={summary.severity}
      data-duplicate-risk={summary.duplicateRisk}
      data-source={summary.source}
    >
      <div className="text-[10px] font-bold uppercase tracking-wide text-amber-900">
        {summary.title}
      </div>
      <p
        className="text-[11px] text-slate-700"
        data-testid={`${testIdPrefix}-partial-impact-reason`}
      >
        {summary.reason}
      </p>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-1.5 text-[11px]">
        {summary.stoppedAtStep && (
          <div data-testid={`${testIdPrefix}-partial-impact-stopped`}>
            <span className="text-slate-400">중단 단계</span>
            <p className="font-medium text-slate-800">{summary.stoppedAtStep}</p>
          </div>
        )}
        {summary.completedSteps && summary.completedSteps.length > 0 && (
          <div data-testid={`${testIdPrefix}-partial-impact-completed`}>
            <span className="text-slate-400">완료된 단계</span>
            <p className="font-medium text-slate-800">{summary.completedSteps.join(" · ")}</p>
          </div>
        )}
        <div data-testid={`${testIdPrefix}-partial-impact-duplicate-risk`}>
          <span className="text-slate-400">중복 가능성</span>
          <p className="font-medium text-slate-800">{summary.duplicateRiskLabel}</p>
        </div>
        {summary.targetTable && (
          <div data-testid={`${testIdPrefix}-partial-impact-target`}>
            <span className="text-slate-400">대상 테이블</span>
            <p className="font-mono text-slate-800 break-all">{summary.targetTable}</p>
          </div>
        )}
        {summary.conflictKeys && summary.conflictKeys.length > 0 ? (
          <div data-testid={`${testIdPrefix}-partial-impact-conflict-keys`}>
            <span className="text-slate-400">기준키 (conflict key)</span>
            <p className="font-mono text-slate-800 break-all">{summary.conflictKeys.join(" + ")}</p>
          </div>
        ) : (
          <div data-testid={`${testIdPrefix}-partial-impact-conflict-keys-fallback`}>
            <span className="text-slate-400">기준키 (conflict key)</span>
            <p className="text-slate-700">
              {conflictKeysFallback
                ? "Studio Upsert 설정에서 확인하세요."
                : "확인할 수 없습니다. Studio Upsert 설정을 확인하세요."}
            </p>
          </div>
        )}
      </div>

      <p
        className="text-[10px] text-slate-600"
        data-testid={`${testIdPrefix}-partial-impact-duplicate-reason`}
      >
        {summary.duplicateRiskReason}
      </p>

      {hints && (
        <div
          className="rounded border border-amber-100 bg-white/70 px-2 py-1.5 font-mono text-[10px] text-slate-700 grid grid-cols-2 sm:grid-cols-3 gap-1"
          data-testid={`${testIdPrefix}-partial-impact-row-hints`}
        >
          {hints.fetched != null && <div>fetched: {fmtCount(hints.fetched)}</div>}
          {hints.inserted != null && <div>inserted: {fmtCount(hints.inserted)}</div>}
          {hints.updated != null && <div>updated: {fmtCount(hints.updated)}</div>}
          {hints.skipped != null && <div>skipped: {fmtCount(hints.skipped)}</div>}
          {hints.failed != null && <div>failed: {fmtCount(hints.failed)}</div>}
        </div>
      )}

      <div data-testid={`${testIdPrefix}-partial-impact-checklist`}>
        <div className="text-[10px] font-semibold text-slate-600 mb-1">
          Retry 전 확인 (안내 · 저장되지 않음)
        </div>
        <ul className="space-y-1">
          {summary.checklist.map((item) => (
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

      <p
        className="text-[10px] text-slate-500"
        data-testid={`${testIdPrefix}-partial-impact-preview-hint`}
      >
        Target Preview: Studio Upsert Inspector의 Target Table sample rows에서 현재 적재 상태를
        확인하세요. 이 카드에서는 물리 테이블을 변경하지 않습니다.
      </p>
    </section>
  );
}
