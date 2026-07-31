import { describeScheduleSkipReason } from "@/utils/scheduleSkipReason";
import type { VisualPipelineScheduleSkipItem } from "@/types/visualPipelineOps";

const LIMIT_OPTIONS = [10, 20, 50] as const;

interface VpScheduleSkipHistoryPanelProps {
  items: VisualPipelineScheduleSkipItem[];
  loading?: boolean;
  error?: string | null;
  limit: number;
  onLimitChange?: (limit: number) => void;
  onRefresh?: () => void;
  onOpenDetail?: (pipelineId: string, visualRunId: string) => void;
  onSelectPipeline?: (pipelineId: string) => void;
}

function fmt(value: string | null | undefined): string {
  if (value === null || value === undefined || value === "") return "-";
  return String(value);
}

export function VpScheduleSkipHistoryPanel({
  items,
  loading,
  error,
  limit,
  onLimitChange,
  onRefresh,
  onOpenDetail,
  onSelectPipeline,
}: VpScheduleSkipHistoryPanelProps) {
  const empty = !loading && !error && items.length === 0;

  return (
    <section
      id="visual-pipeline-ops-schedule-skip-history"
      className="bg-white border border-slate-200 rounded-lg p-4 shadow-sm space-y-3"
      data-testid="visual-pipeline-ops-schedule-skip-history"
      data-empty={empty ? "true" : "false"}
      data-count={items.length}
      data-limit={limit}
    >
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <h2 className="text-sm font-semibold text-slate-800">스케줄 Skip 이력</h2>
          <p className="text-[11px] text-slate-500 mt-0.5">
            스케줄이 실행을 생성하지 않은 최근 사유입니다. 자동 Catch-up·재시도·중단은 수행하지
            않습니다.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2 shrink-0">
          {onLimitChange && (
            <label className="flex items-center gap-1 text-[11px] text-slate-600">
              <span className="sr-only">표시 건수</span>
              <select
                className="border border-slate-200 rounded px-1.5 py-1 bg-white"
                value={limit}
                disabled={loading}
                data-testid="visual-pipeline-ops-schedule-skip-limit"
                onChange={(e) => onLimitChange(Number(e.target.value))}
              >
                {LIMIT_OPTIONS.map((n) => (
                  <option key={n} value={n}>
                    최근 {n}건
                  </option>
                ))}
              </select>
            </label>
          )}
          {onRefresh && (
            <button
              type="button"
              className="text-[11px] text-slate-600 border border-slate-200 rounded px-2 py-1 hover:bg-slate-50 disabled:opacity-50"
              onClick={onRefresh}
              disabled={loading}
              data-testid="visual-pipeline-ops-schedule-skip-refresh"
            >
              {loading ? "새로고침 중…" : "새로고침"}
            </button>
          )}
        </div>
      </div>

      {loading && items.length === 0 && !error && (
        <p
          className="text-[11px] text-slate-500"
          data-testid="visual-pipeline-ops-schedule-skip-loading"
        >
          스케줄 skip 이력을 불러오는 중입니다.
        </p>
      )}

      {error && (
        <div
          className="rounded-md border border-red-200 bg-red-50 px-2.5 py-2"
          data-testid="visual-pipeline-ops-schedule-skip-error"
        >
          <p className="text-[11px] text-red-800">
            스케줄 skip 이력을 불러오지 못했습니다. 잠시 후 다시 시도하세요.
          </p>
          <p className="text-[10px] text-red-700/80 mt-0.5 font-mono break-all">{error}</p>
        </div>
      )}

      {empty && (
        <div
          className="rounded-md border border-slate-100 bg-slate-50 px-2.5 py-2"
          data-testid="visual-pipeline-ops-schedule-skip-empty"
        >
          <p className="text-[11px] text-slate-700">최근 스케줄 skip 이력이 없습니다.</p>
        </div>
      )}

      {!empty && items.length > 0 && (
        <div className="overflow-x-auto" data-testid="visual-pipeline-ops-schedule-skip-table">
          <table className="min-w-full text-left text-[11px]">
            <thead>
              <tr className="border-b border-slate-100 text-slate-400">
                <th className="py-1.5 pr-2 font-medium">Scheduled At</th>
                <th className="py-1.5 pr-2 font-medium">Pipeline</th>
                <th className="py-1.5 pr-2 font-medium">Reason</th>
                <th className="py-1.5 pr-2 font-medium">설명</th>
                <th className="py-1.5 pr-2 font-medium">발생 시각</th>
                <th className="py-1.5 font-medium">액션</th>
              </tr>
            </thead>
            <tbody>
              {items.map((item) => {
                const reasonCode = item.reason_code || "";
                const description = describeScheduleSkipReason(reasonCode);
                const canOpenRun =
                  !!item.pipeline_id &&
                  !!item.visual_run_id &&
                  typeof onOpenDetail === "function";
                const canSelectPipeline =
                  !!item.pipeline_id && typeof onSelectPipeline === "function";

                return (
                  <tr
                    key={item.event_id}
                    className="border-b border-slate-50 align-top"
                    data-testid="visual-pipeline-ops-schedule-skip-row"
                    data-reason-code={reasonCode || "UNKNOWN"}
                    data-source={item.source || ""}
                  >
                    <td className="py-1.5 pr-2 font-mono text-slate-700 whitespace-nowrap">
                      {fmt(item.scheduled_at)}
                    </td>
                    <td className="py-1.5 pr-2 text-slate-700">
                      <div className="font-medium">{fmt(item.pipeline_name || item.pipeline_id)}</div>
                      {item.pipeline_id && (
                        <div className="text-[9px] text-slate-400 font-mono break-all">
                          {item.pipeline_id}
                        </div>
                      )}
                    </td>
                    <td
                      className="py-1.5 pr-2 font-mono text-slate-800 whitespace-nowrap"
                      data-testid="visual-pipeline-ops-schedule-skip-reason-code"
                    >
                      {fmt(reasonCode) === "-" ? "UNKNOWN" : reasonCode}
                    </td>
                    <td
                      className="py-1.5 pr-2 text-slate-600 max-w-xs"
                      data-testid="visual-pipeline-ops-schedule-skip-reason-desc"
                    >
                      {description}
                    </td>
                    <td className="py-1.5 pr-2 font-mono text-slate-600 whitespace-nowrap">
                      {fmt(item.created_at)}
                    </td>
                    <td className="py-1.5">
                      <div className="flex flex-col gap-1">
                        {canOpenRun && (
                          <button
                            type="button"
                            className="text-[10px] font-medium text-violet-800 border border-violet-200 bg-white rounded px-2 py-0.5 hover:bg-violet-50 w-fit"
                            data-testid="visual-pipeline-ops-schedule-skip-detail-button"
                            onClick={() =>
                              onOpenDetail?.(String(item.pipeline_id), String(item.visual_run_id))
                            }
                          >
                            상세
                          </button>
                        )}
                        {!canOpenRun && canSelectPipeline && (
                          <button
                            type="button"
                            className="text-[10px] font-medium text-slate-700 border border-slate-200 bg-white rounded px-2 py-0.5 hover:bg-slate-50 w-fit"
                            data-testid="visual-pipeline-ops-schedule-skip-pipeline-button"
                            onClick={() => onSelectPipeline?.(String(item.pipeline_id))}
                          >
                            Pipeline
                          </button>
                        )}
                        {!canOpenRun && !canSelectPipeline && (
                          <span className="text-[10px] text-slate-400">-</span>
                        )}
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
