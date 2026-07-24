import { ChevronDown, Play } from "lucide-react";
import type { VisualPipelineRunIssue, VisualPipelineRunResponse } from "@/types/visualPipeline";

interface VpRunPanelProps {
  result: VisualPipelineRunResponse | null;
  loading?: boolean;
  polling?: boolean;
  cancelling?: boolean;
  error?: string | null;
  pollError?: string | null;
  canRunHint?: string | null;
  expanded: boolean;
  onToggle: () => void;
  onCancel?: () => void;
}

const SEV_STYLE: Record<string, string> = {
  ERROR: "bg-red-50 border-red-200 text-red-700",
  WARNING: "bg-amber-50 border-amber-200 text-amber-800",
  INFO: "bg-sky-50 border-sky-200 text-sky-700",
};

function statusTone(status: string | undefined): string {
  if (status === "SUCCESS") return "bg-emerald-50 border-emerald-200 text-emerald-700";
  if (status === "PARTIAL") return "bg-amber-50 border-amber-200 text-amber-800";
  if (status === "FAILED" || status === "CANCELLED") return "bg-red-50 border-red-200 text-red-700";
  if (status === "PENDING" || status === "RUNNING") return "bg-sky-50 border-sky-200 text-sky-700";
  return "bg-slate-50 border-slate-200 text-slate-600";
}

function statusLabel(status: string | undefined): string {
  switch (status) {
    case "PENDING":
      return "대기 중";
    case "RUNNING":
      return "실행 중";
    case "SUCCESS":
      return "성공";
    case "PARTIAL":
      return "부분 성공";
    case "FAILED":
      return "실패";
    case "CANCELLED":
      return "취소됨";
    default:
      return status ?? "-";
  }
}

function formatDuration(startedAt?: string | null, finishedAt?: string | null): string | null {
  if (!startedAt) return null;
  const start = Date.parse(startedAt);
  if (Number.isNaN(start)) return null;
  const end = finishedAt ? Date.parse(finishedAt) : Date.now();
  if (Number.isNaN(end) || end < start) return null;
  const sec = Math.round((end - start) / 1000);
  if (sec < 60) return `${sec}s`;
  const m = Math.floor(sec / 60);
  const s = sec % 60;
  return `${m}m ${s}s`;
}

function IssueRow({ issue }: { issue: VisualPipelineRunIssue }) {
  const severity = String(issue.severity ?? "ERROR");
  return (
    <div className={`rounded-md border px-2.5 py-2 text-xs ${SEV_STYLE[severity] ?? "bg-slate-50 border-slate-200"}`}>
      <div className="flex flex-wrap items-center gap-1.5">
        <span className="font-bold uppercase text-[9px] tracking-wide">{severity}</span>
        <span className="font-mono text-[10px] opacity-80">{String(issue.code ?? "")}</span>
      </div>
      <p className="mt-1 text-[11px] leading-snug">{String(issue.message ?? "")}</p>
    </div>
  );
}

function asCount(value: unknown): string {
  if (typeof value === "number") return String(value);
  if (value == null) return "-";
  return String(value);
}

export function VpRunPanel({
  result,
  loading,
  polling,
  cancelling,
  error,
  pollError,
  canRunHint,
  expanded,
  onToggle,
  onCancel,
}: VpRunPanelProps) {
  const issues = result?.issues ?? [];
  const summary = (result?.result ?? null) as Record<string, unknown> | null;
  const duration = formatDuration(result?.started_at, result?.finished_at);
  const active =
    result?.run_status === "PENDING" || result?.run_status === "RUNNING" || Boolean(polling);
  const isPending = result?.run_status === "PENDING";
  const isRunning = result?.run_status === "RUNNING";
  const isCancelled = result?.run_status === "CANCELLED";

  return (
    <div
      className="mt-3 bg-white border border-slate-200 rounded-lg shadow-sm overflow-hidden"
      data-testid="visual-pipeline-run-panel"
    >
      <button
        type="button"
        className="w-full px-4 py-2.5 border-b border-slate-100 bg-slate-50 flex items-center justify-between text-left hover:bg-slate-100/80 transition-colors"
        onClick={onToggle}
      >
        <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider flex items-center gap-1.5">
          <Play className="w-3.5 h-3.5" /> Run
        </span>
        <span className="flex items-center gap-2">
          {(loading || polling) && (
            <span
              className="text-[10px] text-blue-600 animate-pulse"
              data-testid="visual-pipeline-run-polling-indicator"
            >
              {polling ? "상태 확인 중…" : "불러오는 중…"}
            </span>
          )}
          {result && (
            <span
              className={`text-[10px] font-bold uppercase tracking-wide border rounded px-1.5 py-0.5 ${statusTone(result.run_status)}`}
              data-testid="visual-pipeline-run-status"
              title={statusLabel(result.run_status)}
            >
              {result.run_status}
            </span>
          )}
          <span className="text-[10px] text-slate-400">{expanded ? "접기" : "펼치기"}</span>
          <ChevronDown className={`w-3.5 h-3.5 text-slate-400 transition-transform ${expanded ? "rotate-180" : ""}`} />
        </span>
      </button>

      {expanded && (
        <div className="px-4 py-3 space-y-3">
          <p className="text-[11px] text-slate-600 leading-relaxed bg-slate-50 border border-slate-100 rounded-md px-2.5 py-2">
            Run은 Manual 또는 Scheduled로 구분됩니다. Manual은 Run Now로, Scheduled는 Schedule Activation 후
            vp-schedule-worker가 PENDING을 생성하고 vp-run-worker가 실행합니다.
          </p>

          {canRunHint && (
            <p className="text-[11px] text-slate-600 bg-slate-50 border border-slate-100 rounded-md px-2.5 py-2">
              {canRunHint}
            </p>
          )}

          {error && (
            <p className="text-xs text-red-700 bg-red-50 border border-red-100 rounded-md px-2.5 py-2">{error}</p>
          )}

          {pollError && (
            <p className="text-xs text-amber-800 bg-amber-50 border border-amber-100 rounded-md px-2.5 py-2">
              상태 조회: {pollError}
            </p>
          )}

          {loading && !result && (
            <p className="text-xs text-slate-500">최근 Manual Run 결과를 불러오는 중…</p>
          )}

          {!loading && !error && !result && (
            <p className="text-xs text-slate-500">아직 Manual Run 결과가 없습니다. Run Now로 실행할 수 있습니다.</p>
          )}

          {result && (
            <>
              <div className="flex flex-wrap gap-1.5">
                <span className="inline-flex items-center gap-1 text-[10px] font-mono bg-slate-50 border border-slate-200 rounded-md px-2 py-1">
                  <span className="text-slate-400">visual_run_id</span>
                  <span className="font-semibold text-slate-700" data-testid="visual-pipeline-run-id">
                    {result.visual_run_id}
                  </span>
                </span>
                <span className="inline-flex items-center gap-1 text-[10px] font-mono bg-slate-50 border border-slate-200 rounded-md px-2 py-1">
                  <span className="text-slate-400">mode</span>
                  <span className="font-semibold text-slate-700" data-testid="visual-pipeline-run-mode">
                    {result.mode}
                  </span>
                </span>
                <span className="inline-flex items-center gap-1 text-[10px] font-mono bg-slate-50 border border-slate-200 rounded-md px-2 py-1">
                  <span className="text-slate-400">execution_mode</span>
                  <span className="font-semibold text-slate-700">{result.execution_mode}</span>
                </span>
                {result.load_run_id && (
                  <span className="inline-flex items-center gap-1 text-[10px] font-mono bg-slate-50 border border-slate-200 rounded-md px-2 py-1">
                    <span className="text-slate-400">load_run_id</span>
                    <span
                      className="font-semibold text-slate-700"
                      data-testid="visual-pipeline-run-load-run-id"
                    >
                      {result.load_run_id}
                    </span>
                  </span>
                )}
                {result.activation_id && (
                  <span className="inline-flex items-center gap-1 text-[10px] font-mono bg-slate-50 border border-slate-200 rounded-md px-2 py-1">
                    <span className="text-slate-400">activation_id</span>
                    <span
                      className="font-semibold text-slate-700"
                      data-testid="visual-pipeline-run-activation-id"
                    >
                      {result.activation_id}
                    </span>
                  </span>
                )}
                {result.scheduled_for && (
                  <span className="inline-flex items-center gap-1 text-[10px] font-mono bg-slate-50 border border-slate-200 rounded-md px-2 py-1">
                    <span className="text-slate-400">scheduled_for</span>
                    <span
                      className="font-semibold text-slate-700"
                      data-testid="visual-pipeline-run-scheduled-for"
                    >
                      {result.scheduled_for}
                    </span>
                  </span>
                )}
                {result.r10_schedule_id && (
                  <span className="inline-flex items-center gap-1 text-[10px] font-mono bg-slate-50 border border-slate-200 rounded-md px-2 py-1">
                    <span className="text-slate-400">r10_schedule_id</span>
                    <span className="font-semibold text-slate-700">{result.r10_schedule_id}</span>
                  </span>
                )}
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-2 text-[10px] font-mono text-slate-600">
                <div className="bg-slate-50 border border-slate-100 rounded-md px-2 py-1.5">
                  started_at: {result.started_at ?? "-"}
                </div>
                <div className="bg-slate-50 border border-slate-100 rounded-md px-2 py-1.5">
                  finished_at: {result.finished_at ?? "-"}
                  {duration ? ` · ${duration}` : ""}
                </div>
              </div>

              {summary && Object.keys(summary).length > 0 && (
                <div
                  className="text-[11px] bg-slate-50 border border-slate-100 rounded-md px-2.5 py-2 space-y-1"
                  data-testid="visual-pipeline-run-result"
                >
                  <div className="text-[9px] font-bold text-slate-400 uppercase tracking-wide">Result summary</div>
                  <div className="font-mono text-[10px] text-slate-700 grid grid-cols-1 md:grid-cols-2 gap-1">
                    <div>operation_id: {String(summary.operation_id ?? "-")}</div>
                    <div>write_policy_id: {String(summary.write_policy_id ?? "-")}</div>
                    <div>transform_config_id: {String(summary.transform_config_id ?? "-")}</div>
                    <div>target_table: {String(summary.target_table ?? "-")}</div>
                    <div>fetched: {asCount(summary.fetched_count)}</div>
                    <div>inserted: {asCount(summary.inserted_count)}</div>
                    <div>updated: {asCount(summary.updated_count)}</div>
                    <div>skipped: {asCount(summary.skipped_count)}</div>
                    <div>failed: {asCount(summary.failed_count)}</div>
                  </div>
                </div>
              )}

              {issues.length > 0 && (
                <div data-testid="visual-pipeline-run-issues">
                  <div className="text-[9px] font-bold text-slate-400 uppercase tracking-wide mb-1.5">Issues</div>
                  <div className="space-y-1.5">
                    {issues.map((issue, idx) => (
                      <IssueRow key={`${String(issue.code)}-${idx}`} issue={issue} />
                    ))}
                  </div>
                </div>
              )}

              {isCancelled && (
                <p
                  className="text-xs text-slate-700 bg-slate-50 border border-slate-200 rounded-md px-2.5 py-2"
                  data-testid="visual-pipeline-run-cancelled-message"
                >
                  실행 전에 취소되었습니다. (RUNNING 중 중단은 후속 지원)
                </p>
              )}

              {isPending && onCancel && (
                <button
                  type="button"
                  className="inline-flex items-center px-2.5 py-1.5 text-xs font-medium rounded-md border border-slate-300 text-slate-700 hover:bg-slate-50 disabled:opacity-50"
                  onClick={onCancel}
                  disabled={Boolean(cancelling) || Boolean(polling && !isPending)}
                  data-testid="visual-pipeline-run-cancel-button"
                >
                  {cancelling ? "취소 중…" : "대기 Run 취소"}
                </button>
              )}

              {isRunning && (
                <p className="text-[11px] text-slate-500 bg-slate-50 border border-slate-100 rounded-md px-2.5 py-2">
                  실행 중(RUNNING) 취소는 현재 지원하지 않습니다.
                </p>
              )}

              {result.error_message && result.run_status === "FAILED" && (
                <p className="text-xs text-red-700 bg-red-50 border border-red-100 rounded-md px-2.5 py-2">
                  {result.error_message}
                </p>
              )}

              <div
                className="text-[11px] bg-violet-50 border border-violet-100 rounded-md px-2.5 py-2 space-y-1"
                data-testid="visual-pipeline-run-safety"
              >
                <div className="text-[9px] font-bold text-violet-500 uppercase tracking-wide">Safety policy</div>
                <div className="font-mono text-[10px] text-violet-900">
                  schedule_active_changed={String(result.schedule_active_changed ?? false)}
                  {" · "}
                  current_sync_status_changed={String(result.current_sync_status_changed ?? false)}
                </div>
                <p className="text-[10px] text-violet-800 leading-snug">
                  Schedule Activation 미수행 · due worker 미연결
                </p>
              </div>

              {active && (
                <p className="text-[10px] text-slate-500 leading-snug bg-slate-50 border border-slate-100 rounded-md px-2.5 py-2">
                  Background PoC 특성상 서버 재시작 시 PENDING/RUNNING 상태가 멈출 수 있습니다. 후속 worker 단계에서
                  복구 정책을 보강합니다.
                </p>
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
}
