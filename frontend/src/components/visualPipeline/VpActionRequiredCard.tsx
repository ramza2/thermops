import type { OpsActionGroup, OpsActionItem, OpsActionRequired } from "@/utils/opsActionRequired";

interface VpActionRequiredCardProps {
  model: OpsActionRequired;
  loading?: boolean;
  onRefresh?: () => void;
  onOpenDetail?: (pipelineId: string, visualRunId: string) => void;
  /** Optional scroll/jump to B9 Schedule Skip history panel (no auto action). */
  onOpenSkipHistory?: () => void;
}

function severityClass(severity: OpsActionGroup["severity"]): string {
  if (severity === "error") return "border-red-200 bg-red-50/60 text-red-900";
  if (severity === "warning") return "border-amber-200 bg-amber-50/60 text-amber-900";
  return "border-slate-200 bg-slate-50 text-slate-800";
}

function severityBadge(severity: OpsActionGroup["severity"]): string {
  return severity.toUpperCase();
}

function GroupBlock({
  group,
  onOpenDetail,
  onOpenSkipHistory,
}: {
  group: OpsActionGroup;
  onOpenDetail?: (pipelineId: string, visualRunId: string) => void;
  onOpenSkipHistory?: () => void;
}) {
  return (
    <div
      className={`rounded-md border px-2.5 py-2 space-y-1.5 ${severityClass(group.severity)}`}
      data-testid={`visual-pipeline-ops-action-required-group-${group.id}`}
      data-severity={group.severity}
      data-count={group.count}
    >
      <div className="flex items-center justify-between gap-2">
        <div className="text-[11px] font-semibold">
          [{severityBadge(group.severity)}] {group.label} {group.count}건
        </div>
      </div>
      <ul className="space-y-1.5">
        {group.items.map((item) => (
          <ActionItemRow
            key={item.id}
            item={item}
            groupId={group.id}
            onOpenDetail={onOpenDetail}
            onOpenSkipHistory={onOpenSkipHistory}
          />
        ))}
      </ul>
    </div>
  );
}

function ActionItemRow({
  item,
  groupId,
  onOpenDetail,
  onOpenSkipHistory,
}: {
  item: OpsActionItem;
  groupId: OpsActionGroup["id"];
  onOpenDetail?: (pipelineId: string, visualRunId: string) => void;
  onOpenSkipHistory?: () => void;
}) {
  const canOpen =
    item.openDetail && !!item.pipelineId && !!item.visualRunId && typeof onOpenDetail === "function";
  const showSkipLink = groupId === "catchup_hint" && typeof onOpenSkipHistory === "function";

  return (
    <li
      className="rounded border border-white/60 bg-white/70 px-2 py-1.5 space-y-0.5"
      data-testid="visual-pipeline-ops-action-required-item"
      data-open-detail={canOpen ? "true" : "false"}
    >
      <div className="text-[11px] font-medium text-slate-800 font-mono break-all">{item.title}</div>
      <p
        className="text-[10px] text-slate-600"
        data-testid="visual-pipeline-ops-action-required-reason"
      >
        {item.reason}
      </p>
      {item.meta && <p className="text-[9px] text-slate-400 font-mono">{item.meta}</p>}
      <div className="flex flex-wrap gap-1.5 mt-1">
        {canOpen && (
          <button
            type="button"
            className="text-[10px] font-medium text-violet-800 border border-violet-200 bg-white rounded px-2 py-0.5 hover:bg-violet-50"
            data-testid="visual-pipeline-ops-action-required-detail-button"
            onClick={() => onOpenDetail?.(String(item.pipelineId), String(item.visualRunId))}
          >
            상세 보기
          </button>
        )}
        {showSkipLink && (
          <button
            type="button"
            className="text-[10px] font-medium text-slate-700 border border-slate-200 bg-white rounded px-2 py-0.5 hover:bg-slate-50"
            data-testid="visual-pipeline-ops-action-required-skip-history-link"
            onClick={() => onOpenSkipHistory?.()}
          >
            Skip 이력 보기
          </button>
        )}
      </div>
    </li>
  );
}

export function VpActionRequiredCard({
  model,
  loading,
  onRefresh,
  onOpenDetail,
  onOpenSkipHistory,
}: VpActionRequiredCardProps) {
  return (
    <section
      className="bg-white border border-slate-200 rounded-lg p-4 shadow-sm space-y-3"
      data-testid="visual-pipeline-ops-action-required"
      data-empty={model.empty ? "true" : "false"}
      data-total={model.totalActionCount}
    >
      <div className="flex items-start justify-between gap-2">
        <div>
          <h2 className="text-sm font-semibold text-slate-800">조치 필요</h2>
          <p className="text-[11px] text-slate-500 mt-0.5">
            현재 확인이 필요한 실행/스케줄 항목입니다. 자동 조치·알림 발송은 수행하지 않습니다.
          </p>
        </div>
        {onRefresh && (
          <button
            type="button"
            className="shrink-0 text-[11px] text-slate-600 border border-slate-200 rounded px-2 py-1 hover:bg-slate-50 disabled:opacity-50"
            onClick={onRefresh}
            disabled={loading}
            data-testid="visual-pipeline-ops-action-required-refresh"
          >
            {loading ? "새로고침 중…" : "새로고침"}
          </button>
        )}
      </div>

      {model.empty ? (
        <div
          className="rounded-md border border-emerald-100 bg-emerald-50/50 px-2.5 py-2"
          data-testid="visual-pipeline-ops-action-required-empty"
        >
          <p className="text-[11px] font-medium text-emerald-900">현재 조치 필요 항목이 없습니다.</p>
          <p className="text-[10px] text-emerald-800/80 mt-0.5">
            최근 실행과 스케줄 상태가 정상으로 보입니다.
          </p>
        </div>
      ) : (
        <div className="space-y-2" data-testid="visual-pipeline-ops-action-required-groups">
          <div className="text-[10px] text-slate-500">
            요약: 조치 후보 합계 {model.totalActionCount}건
            {model.generatedAt ? ` · generated_at=${model.generatedAt}` : ""}
          </div>
          {model.groups.map((group) => (
            <GroupBlock
              key={group.id}
              group={group}
              onOpenDetail={onOpenDetail}
              onOpenSkipHistory={onOpenSkipHistory}
            />
          ))}
        </div>
      )}
    </section>
  );
}
