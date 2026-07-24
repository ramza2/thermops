import { Clock } from "lucide-react";
import type { VisualPipelineScheduleActivationResponse } from "@/types/visualPipeline";

interface VpScheduleActivationPanelProps {
  result: VisualPipelineScheduleActivationResponse | null;
  loading?: boolean;
  activating?: boolean;
  deactivating?: boolean;
  error?: string | null;
  canActivateHint?: string | null;
  staleActiveWarning?: boolean;
  expanded: boolean;
  onToggle: () => void;
  onDeactivate?: () => void;
}

function statusTone(status: string | undefined): string {
  if (status === "ACTIVE") return "bg-emerald-50 border-emerald-200 text-emerald-700";
  if (status === "INACTIVE") return "bg-slate-50 border-slate-200 text-slate-600";
  if (status === "PAUSED") return "bg-amber-50 border-amber-200 text-amber-800";
  if (status === "ERROR") return "bg-red-50 border-red-200 text-red-700";
  return "bg-slate-50 border-slate-200 text-slate-600";
}

export function VpScheduleActivationPanel({
  result,
  loading,
  activating,
  deactivating,
  error,
  canActivateHint,
  staleActiveWarning,
  expanded,
  onToggle,
  onDeactivate,
}: VpScheduleActivationPanelProps) {
  const isActive = result?.activation_status === "ACTIVE";

  return (
    <div
      className="mt-3 bg-white border border-slate-200 rounded-lg shadow-sm overflow-hidden"
      data-testid="visual-pipeline-schedule-activation-panel"
    >
      <button
        type="button"
        className="w-full flex items-center justify-between px-3 py-2.5 text-left hover:bg-slate-50"
        onClick={onToggle}
      >
        <div className="flex items-center gap-2 min-w-0">
          <Clock className="w-3.5 h-3.5 text-slate-500 shrink-0" />
          <span className="text-xs font-bold text-slate-700">Schedule Activation</span>
          {result?.activation_status && (
            <span
              className={`text-[10px] font-bold px-1.5 py-0.5 rounded border ${statusTone(result.activation_status)}`}
              data-testid="visual-pipeline-schedule-activation-status"
            >
              {result.activation_status}
            </span>
          )}
          {(loading || activating || deactivating) && (
            <span className="text-[10px] text-slate-400">처리 중…</span>
          )}
        </div>
        <span className="text-[10px] text-slate-400">{expanded ? "접기" : "펼치기"}</span>
      </button>

      {expanded && (
        <div className="px-3 pb-3 border-t border-slate-100 space-y-2.5">
          {error && (
            <p className="text-xs text-red-600 bg-red-50 border border-red-100 rounded-md px-2.5 py-2">
              {error}
            </p>
          )}
          {!result && !loading && !error && (
            <p className="text-xs text-slate-500">
              아직 Schedule Activation 이력이 없습니다. 조건 충족 후 스케줄 활성화 버튼으로 시작할 수
              있습니다.
            </p>
          )}
          {canActivateHint && !isActive && (
            <p className="text-[11px] text-slate-500 bg-slate-50 border border-slate-100 rounded-md px-2.5 py-2">
              {canActivateHint}
            </p>
          )}
          {staleActiveWarning && isActive && (
            <p className="text-[11px] text-amber-800 bg-amber-50 border border-amber-100 rounded-md px-2.5 py-2">
              그래프가 STALE 상태입니다. 활성 스케줄은 유지되지만 재컴파일/재반영을 권장합니다. (자동
              비활성은 후속)
            </p>
          )}
          {result && (
            <>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-[11px]">
                <div>
                  <span className="text-slate-400">activation_id</span>
                  <p className="font-mono text-slate-700" data-testid="visual-pipeline-schedule-activation-id">
                    {result.activation_id}
                  </p>
                </div>
                <div>
                  <span className="text-slate-400">r10_schedule_id</span>
                  <p className="font-mono text-slate-700">{result.r10_schedule_id}</p>
                </div>
                <div>
                  <span className="text-slate-400">cron</span>
                  <p className="font-mono text-slate-700">
                    {result.cron_expression ?? "-"} · {result.timezone ?? "-"}
                  </p>
                </div>
                <div>
                  <span className="text-slate-400">next_due_at</span>
                  <p className="font-mono text-slate-700" data-testid="visual-pipeline-schedule-next-due">
                    {result.next_due_at ?? "-"}
                  </p>
                </div>
                <div>
                  <span className="text-slate-400">last_triggered_at</span>
                  <p className="font-mono text-slate-700">{result.last_triggered_at ?? "-"}</p>
                </div>
                <div>
                  <span className="text-slate-400">trigger_count</span>
                  <p
                    className="font-mono text-slate-700"
                    data-testid="visual-pipeline-schedule-trigger-count"
                  >
                    {result.trigger_count ?? 0}
                  </p>
                </div>
              </div>
              <div className="text-[11px] bg-slate-50 border border-slate-100 rounded-md px-2.5 py-2 text-slate-600 space-y-0.5">
                <p>Activation은 run_load를 직접 실행하지 않습니다.</p>
                <p>vp-schedule-worker가 due 시 PENDING scheduled run을 생성합니다.</p>
                <p>vp-run-worker가 PENDING run을 실행합니다. R10 active_yn=false 유지.</p>
                <p>due run은 즉시 생성되지 않을 수 있습니다. Run Panel에서 확인하세요.</p>
              </div>
              {isActive && onDeactivate && (
                <button
                  type="button"
                  className="inline-flex items-center px-2.5 py-1.5 text-xs font-medium rounded-md border border-slate-300 text-slate-700 hover:bg-slate-50 disabled:opacity-50"
                  onClick={onDeactivate}
                  disabled={deactivating || activating}
                  data-testid="visual-pipeline-schedule-deactivate-button"
                >
                  {deactivating ? "비활성화 중…" : "비활성화"}
                </button>
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
}
