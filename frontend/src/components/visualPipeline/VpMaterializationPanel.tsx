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
  variant?: "standalone" | "dock";
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
  variant = "standalone",
}: VpMaterializationPanelProps) {
  const issues = result?.issues ?? [];
  const warnings = result?.warnings ?? [];
  const isDock = variant === "dock";
  const bodyOpen = isDock || expanded;

  return (
    <div
      className={`${isDock ? "" : "mt-3"} bg-white border border-slate-200 rounded-lg shadow-sm overflow-hidden`}
      data-testid="visual-pipeline-materialization-panel"
    >
      {!isDock && (
        <button
          type="button"
          className="w-full px-4 py-2.5 border-b border-slate-100 bg-slate-50 flex items-center justify-between text-left hover:bg-slate-100/80 transition-colors"
          onClick={onToggle}
        >
          <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider flex items-center gap-1.5">
            <Database className="w-3.5 h-3.5" /> 실행 설정 반영 결과
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
      )}

      {isDock && result && (
        <div className="px-4 py-2 border-b border-slate-100 bg-slate-50 flex items-center gap-2">
          <span
            className={`text-[10px] font-bold uppercase tracking-wide border rounded px-1.5 py-0.5 ${statusTone(result.materialization_status)}`}
            data-testid="visual-pipeline-materialization-status"
          >
            {result.materialization_status}
          </span>
          {loading && <span className="text-[10px] text-blue-600 animate-pulse">불러오는 중…</span>}
        </div>
      )}

      {bodyOpen && (
        <div className="px-4 py-3 space-y-3">
          <p className="text-[11px] text-slate-600 leading-relaxed bg-slate-50 border border-slate-100 rounded-md px-2.5 py-2">
            현재 Visual Pipeline 그래프의 Compile 결과를 실행 설정으로 반영합니다. 외부 API 호출, 데이터 적재,
            스케줄 활성화는 수행하지 않습니다.
          </p>

          {dirtyHint && (
            <p className="text-[11px] text-amber-800 bg-amber-50 border border-amber-100 rounded-md px-2.5 py-2">
              저장되지 않은 변경사항이 있습니다. 저장 후 다시 Compile한 뒤 실행 설정을 반영해 주세요.
            </p>
          )}

          {!dirtyHint && compileReady === false && (
            <p className="text-[11px] text-slate-600 bg-slate-50 border border-slate-100 rounded-md px-2.5 py-2">
              먼저 Compile을 성공시켜야 실행 설정을 반영할 수 있습니다.
            </p>
          )}

          {loading && !result && (
            <p className="text-xs text-slate-500">실행 설정 반영 결과를 불러오는 중…</p>
          )}

          {error && (
            <p className="text-xs text-red-700 bg-red-50 border border-red-100 rounded-md px-2.5 py-2">{error}</p>
          )}

          {!loading && !error && !result && (
            <p className="text-xs text-slate-500">아직 실행 설정 반영 결과가 없습니다.</p>
          )}

          {result && (
            <>
              <p className="text-[11px] text-slate-600 leading-relaxed">
                {result.materialization_status === "SUCCESS"
                  ? "실행 설정이 생성/갱신되었습니다. 즉시 실행·스케줄 활성화·외부 API 호출·데이터 적재는 수행되지 않았습니다."
                  : "실행 설정 반영에 실패했습니다. 아래 이슈를 확인하세요."}
              </p>

              {isDock && (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-2 text-[10px] font-mono text-slate-600">
                  {result.materialization_result_id && (
                    <div className="bg-slate-50 border border-slate-100 rounded-md px-2 py-1.5 truncate">
                      result_id:{" "}
                      <span data-testid="visual-pipeline-materialization-result-id">
                        {result.materialization_result_id}
                      </span>
                    </div>
                  )}
                  <div className="bg-slate-50 border border-slate-100 rounded-md px-2 py-1.5">
                    activation:{" "}
                    <span data-testid="visual-pipeline-materialization-activation">
                      {result.activation ?? "NOT_REQUESTED"}
                    </span>
                  </div>
                  <div className="bg-slate-50 border border-slate-100 rounded-md px-2 py-1.5">
                    run_created:{" "}
                    <span data-testid="visual-pipeline-materialization-run-created">
                      {String(result.run_created ?? false)}
                    </span>
                  </div>
                </div>
              )}

              {isDock ? (
                <details className="text-[10px] text-slate-600">
                  <summary className="cursor-pointer text-[9px] font-bold text-slate-400 uppercase tracking-wide py-1">
                    Hash / objects / issues
                  </summary>
                  <div className="mt-2 space-y-2">
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-2 font-mono">
                      <div className="bg-slate-50 border border-slate-100 rounded-md px-2 py-1.5 truncate">
                        graph_hash: {result.graph_version_hash ?? "-"}
                      </div>
                      <div className="bg-slate-50 border border-slate-100 rounded-md px-2 py-1.5">
                        materialized_at: {result.materialized_at ?? "-"}
                      </div>
                    </div>
                    {result.objects && Object.keys(result.objects).length > 0 && (
                      <div className="font-mono break-all">objects: {Object.keys(result.objects).join(", ")}</div>
                    )}
                    {issues.length > 0 && (
                      <div className="space-y-1.5">
                        {issues.map((issue, idx) => (
                          <IssueRow key={`${issue.code}-${idx}`} issue={issue} />
                        ))}
                      </div>
                    )}
                  </div>
                </details>
              ) : (
                <>
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
                <div className="text-[9px] font-bold text-violet-500 uppercase tracking-wide">안전 정책</div>
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
                  스케줄은 자동 실행되지 않은 상태로 유지됩니다. 즉시 실행 또는 스케줄 활성화는 별도 단계에서
                  진행합니다.
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
            </>
          )}
        </div>
      )}
    </div>
  );
}
