import { ChevronDown, Database } from "lucide-react";
import type {
  VisualPipelineMaterializationIssue,
  VisualPipelineMaterializationResponse,
} from "@/types/visualPipeline";

interface VpMaterializationPanelProps {
  result: VisualPipelineMaterializationResponse | null;
  loading?: boolean;
  error?: string | null;
  dirtyHint?: boolean;
  compileReady?: boolean;
  expanded: boolean;
  onToggle: () => void;
}

const SEV_STYLE: Record<string, string> = {
  ERROR: "bg-red-50 border-red-200 text-red-700",
  WARNING: "bg-amber-50 border-amber-200 text-amber-800",
  INFO: "bg-sky-50 border-sky-200 text-sky-700",
};

function statusTone(status: string | undefined): string {
  if (status === "SUCCESS") return "bg-emerald-50 border-emerald-200 text-emerald-700";
  if (status === "FAILED") return "bg-red-50 border-red-200 text-red-700";
  return "bg-slate-50 border-slate-200 text-slate-600";
}

function IssueRow({ issue }: { issue: VisualPipelineMaterializationIssue }) {
  return (
    <div className={`rounded-md border px-2.5 py-2 text-xs ${SEV_STYLE[issue.severity] ?? "bg-slate-50 border-slate-200"}`}>
      <div className="flex flex-wrap items-center gap-1.5">
        <span className="font-bold uppercase text-[9px] tracking-wide">{issue.severity}</span>
        <span className="font-mono text-[10px] opacity-80">{issue.code}</span>
      </div>
      <p className="mt-1 text-[11px] leading-snug">{issue.message}</p>
    </div>
  );
}

export function VpMaterializationPanel({
  result,
  loading,
  error,
  dirtyHint,
  compileReady,
  expanded,
  onToggle,
}: VpMaterializationPanelProps) {
  const issues = result?.issues ?? [];
  const warnings = result?.warnings ?? [];

  return (
    <div
      className="mt-3 bg-white border border-slate-200 rounded-lg shadow-sm overflow-hidden"
      data-testid="visual-pipeline-materialization-panel"
    >
      <button
        type="button"
        className="w-full px-4 py-2.5 border-b border-slate-100 bg-slate-50 flex items-center justify-between text-left hover:bg-slate-100/80 transition-colors"
        onClick={onToggle}
      >
        <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider flex items-center gap-1.5">
          <Database className="w-3.5 h-3.5" /> Materialization Result
        </span>
        <span className="flex items-center gap-2">
          {loading && <span className="text-[10px] text-blue-600 animate-pulse">불러오는 중…</span>}
          {result && (
            <span
              className={`text-[10px] font-bold uppercase tracking-wide border rounded px-1.5 py-0.5 ${statusTone(result.materialization_status)}`}
              data-testid="visual-pipeline-materialization-status"
            >
              {result.materialization_status}
            </span>
          )}
          <span className="text-[10px] text-slate-400">{expanded ? "접기" : "펼치기"}</span>
          <ChevronDown className={`w-3.5 h-3.5 text-slate-400 transition-transform ${expanded ? "rotate-180" : ""}`} />
        </span>
      </button>

      {expanded && (
        <div className="px-4 py-3 space-y-3">
          <p className="text-[11px] text-slate-600 leading-relaxed bg-slate-50 border border-slate-100 rounded-md px-2.5 py-2">
            R10 Operation / Transform Config / Write Policy / Schedule 설정 row를 upsert합니다. 외부 API 호출, 적재 실행,
            스케줄 활성화는 수행하지 않습니다.
          </p>

          {dirtyHint && (
            <p className="text-[11px] text-amber-800 bg-amber-50 border border-amber-100 rounded-md px-2.5 py-2">
              미저장 변경사항이 있습니다. Materialize는 저장된 그래프 + persisted SUCCESS Compile + IN_SYNC 상태에서만
              실행할 수 있습니다.
            </p>
          )}

          {!dirtyHint && compileReady === false && (
            <p className="text-[11px] text-slate-600 bg-slate-50 border border-slate-100 rounded-md px-2.5 py-2">
              persisted SUCCESS Compile 결과와 IN_SYNC 상태가 필요합니다. 먼저 Compile을 완료하세요.
            </p>
          )}

          {loading && !result && (
            <p className="text-xs text-slate-500">Materialization 결과를 불러오는 중…</p>
          )}

          {error && (
            <p className="text-xs text-red-700 bg-red-50 border border-red-100 rounded-md px-2.5 py-2">{error}</p>
          )}

          {!loading && !error && !result && (
            <p className="text-xs text-slate-500">아직 Materialization 결과가 없습니다.</p>
          )}

          {result && (
            <>
              <p className="text-[11px] text-slate-600 leading-relaxed">
                {result.materialization_status === "SUCCESS"
                  ? "R10 설정 row가 생성/갱신되었습니다. Run·스케줄 활성화·외부 호출·적재 실행은 수행되지 않았습니다."
                  : "Materialization에 실패했습니다. 아래 이슈를 확인하세요."}
              </p>

              <div className="flex flex-wrap gap-1.5">
                {result.materialization_result_id && (
                  <span className="inline-flex items-center gap-1 text-[10px] font-mono bg-slate-50 border border-slate-200 rounded-md px-2 py-1">
                    <span className="text-slate-400">result_id</span>
                    <span
                      className="font-semibold text-slate-700"
                      data-testid="visual-pipeline-materialization-result-id"
                    >
                      {result.materialization_result_id}
                    </span>
                  </span>
                )}
                {result.compile_result_id && (
                  <span className="inline-flex items-center gap-1 text-[10px] font-mono bg-slate-50 border border-slate-200 rounded-md px-2 py-1">
                    <span className="text-slate-400">compile_id</span>
                    <span className="font-semibold text-slate-700">{result.compile_result_id}</span>
                  </span>
                )}
                {result.materialization_version && (
                  <span className="inline-flex items-center gap-1 text-[10px] font-mono bg-slate-50 border border-slate-200 rounded-md px-2 py-1">
                    <span className="text-slate-400">version</span>
                    <span className="font-semibold text-slate-700">{result.materialization_version}</span>
                  </span>
                )}
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-2 text-[10px] font-mono text-slate-600">
                <div className="bg-slate-50 border border-slate-100 rounded-md px-2 py-1.5 truncate">
                  graph_hash: {result.graph_version_hash ?? "-"}
                </div>
                <div className="bg-slate-50 border border-slate-100 rounded-md px-2 py-1.5">
                  materialized_at: {result.materialized_at ?? "-"}
                </div>
              </div>

              <div className="text-[11px] bg-violet-50 border border-violet-100 rounded-md px-2.5 py-2 space-y-1">
                <div className="text-[9px] font-bold text-violet-500 uppercase tracking-wide">Safety policy</div>
                <div className="font-mono text-[10px] text-violet-900">
                  activation=
                  <span data-testid="visual-pipeline-materialization-activation">
                    {result.activation ?? "NOT_REQUESTED"}
                  </span>
                  {" · "}
                  run_created=
                  <span data-testid="visual-pipeline-materialization-run-created">
                    {String(result.run_created ?? false)}
                  </span>
                </div>
                <p className="text-[10px] text-violet-800 leading-snug">
                  Schedule은 inactive로 유지됩니다. Manual Run은 Run Now로 실행할 수 있으며, 스케줄 활성화는 후속
                  범위입니다.
                </p>
              </div>

              {result.objects && Object.keys(result.objects).length > 0 && (
                <div className="text-[11px] bg-slate-50 border border-slate-100 rounded-md px-2.5 py-2">
                  <div className="text-[9px] font-bold text-slate-400 uppercase tracking-wide mb-1">Objects</div>
                  <div className="font-mono text-[10px] text-slate-700 break-all">
                    {Object.keys(result.objects).join(", ")}
                  </div>
                </div>
              )}

              {(result.created && Object.keys(result.created).length > 0) ||
              (result.updated && Object.keys(result.updated).length > 0) ? (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-2 text-[10px] font-mono text-slate-600">
                  {result.created && Object.keys(result.created).length > 0 && (
                    <div className="bg-emerald-50/50 border border-emerald-100 rounded-md px-2 py-1.5">
                      created: {Object.keys(result.created).join(", ")}
                    </div>
                  )}
                  {result.updated && Object.keys(result.updated).length > 0 && (
                    <div className="bg-sky-50/50 border border-sky-100 rounded-md px-2 py-1.5">
                      updated: {Object.keys(result.updated).join(", ")}
                    </div>
                  )}
                </div>
              ) : null}

              {issues.length > 0 && (
                <div>
                  <div className="text-[9px] font-bold text-slate-400 uppercase tracking-wide mb-1.5">Issues</div>
                  <div className="space-y-1.5">
                    {issues.map((issue, idx) => (
                      <IssueRow key={`${issue.code}-${idx}`} issue={issue} />
                    ))}
                  </div>
                </div>
              )}

              {warnings.length > 0 && (
                <div>
                  <div className="text-[9px] font-bold text-slate-400 uppercase tracking-wide mb-1.5">Warnings</div>
                  <ul className="space-y-1 text-[10px] text-amber-800">
                    {warnings.map((w, idx) => (
                      <li key={idx} className="font-mono bg-amber-50 border border-amber-100 rounded px-2 py-1">
                        {typeof w === "string" ? w : JSON.stringify(w)}
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {result.error_message && (
                <p className="text-xs text-red-700 bg-red-50 border border-red-100 rounded-md px-2.5 py-2">
                  {result.error_message}
                </p>
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
}
