import { ChevronDown, Layers } from "lucide-react";
import type {
  VisualPipelineCompileIssue,
  VisualPipelineCompileResponse,
} from "@/types/visualPipeline";

interface VpCompilePanelProps {
  result: VisualPipelineCompileResponse | null;
  loading?: boolean;
  error?: string | null;
  dirtyHint?: boolean;
  expanded: boolean;
  onToggle: () => void;
  onSelectNode?: (nodeId: string) => void;
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

function IssueRow({
  issue,
  onSelectNode,
}: {
  issue: VisualPipelineCompileIssue;
  onSelectNode?: (nodeId: string) => void;
}) {
  return (
    <div className={`rounded-md border px-2.5 py-2 text-xs ${SEV_STYLE[issue.severity] ?? "bg-slate-50 border-slate-200"}`}>
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-1.5">
            <span className="font-bold uppercase text-[9px] tracking-wide">{issue.severity}</span>
            {issue.phase && (
              <span className="font-bold uppercase text-[8px] tracking-wide bg-white/70 border border-current/20 rounded px-1 py-0.5 opacity-80">
                {issue.phase}
              </span>
            )}
            <span className="font-mono text-[10px] opacity-80">{issue.code}</span>
            {issue.field_key && (
              <span className="font-mono text-[9px] opacity-70">field={issue.field_key}</span>
            )}
          </div>
          <p className="mt-1 text-[11px] leading-snug">{issue.message}</p>
          {issue.hint && <p className="mt-1 text-[10px] opacity-80">{issue.hint}</p>}
          {(issue.component_type || issue.node_id) && (
            <p className="mt-1 font-mono text-[10px] opacity-70">
              {[issue.component_type, issue.node_id].filter(Boolean).join(" · ")}
            </p>
          )}
        </div>
        {issue.node_id && onSelectNode && (
          <button
            type="button"
            className="shrink-0 text-[10px] font-medium underline underline-offset-2"
            onClick={() => onSelectNode(issue.node_id!)}
          >
            선택
          </button>
        )}
      </div>
    </div>
  );
}

export function VpCompilePanel({
  result,
  loading,
  error,
  dirtyHint,
  expanded,
  onToggle,
  onSelectNode,
}: VpCompilePanelProps) {
  const artifact = result?.compiled_artifact;
  const meta = artifact?.metadata;
  const steps = artifact?.steps ?? [];
  const allIssues = result?.issues ?? [];
  const wrapperIssues = allIssues.filter((i) => i.code === "COMPILE_VALIDATION_FAILED");
  const detailIssues = allIssues.filter((i) => i.code !== "COMPILE_VALIDATION_FAILED");

  return (
    <div
      className="mt-3 bg-white border border-slate-200 rounded-lg shadow-sm overflow-hidden"
      data-testid="visual-pipeline-compile-panel"
    >
      <button
        type="button"
        className="w-full px-4 py-2.5 border-b border-slate-100 bg-slate-50 flex items-center justify-between text-left hover:bg-slate-100/80 transition-colors"
        onClick={onToggle}
      >
        <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider flex items-center gap-1.5">
          <Layers className="w-3.5 h-3.5" /> Compile Result
        </span>
        <span className="flex items-center gap-2">
          {loading && <span className="text-[10px] text-blue-600 animate-pulse">컴파일 중…</span>}
          {result && (
            <span
              className={`text-[10px] font-bold uppercase tracking-wide border rounded px-1.5 py-0.5 ${statusTone(result.compile_status)}`}
              data-testid="visual-pipeline-compile-status"
            >
              {result.compile_status}
            </span>
          )}
          <span className="text-[10px] text-slate-400">{expanded ? "접기" : "펼치기"}</span>
          <ChevronDown className={`w-3.5 h-3.5 text-slate-400 transition-transform ${expanded ? "rotate-180" : ""}`} />
        </span>
      </button>

      {expanded && (
        <div className="px-4 py-3 space-y-3" data-testid="visual-pipeline-compile-panel-body">
          {dirtyHint && (
            <p className="text-[11px] text-amber-800 bg-amber-50 border border-amber-100 rounded-md px-2.5 py-2">
              미저장 변경사항은 Compile에 반영되지 않습니다. Preview/Compile은 저장된 그래프 기준입니다.
            </p>
          )}

          {loading && !result && (
            <p className="text-xs text-slate-500">컴파일 결과를 불러오는 중…</p>
          )}

          {error && (
            <p className="text-xs text-red-700 bg-red-50 border border-red-100 rounded-md px-2.5 py-2" data-testid="visual-pipeline-compile-error">
              {error}
            </p>
          )}

          {!loading && !error && !result && (
            <p className="text-xs text-slate-500" data-testid="visual-pipeline-compile-empty">
              아직 컴파일 결과가 없습니다.
            </p>
          )}

          {result && (
            <>
              <p className="text-[11px] text-slate-600 leading-relaxed">
                {result.compile_status === "SUCCESS"
                  ? result.persisted
                    ? "컴파일 결과가 저장되었습니다. 실제 적재 실행이나 스케줄 활성화는 수행되지 않습니다."
                    : "컴파일 미리보기가 생성되었습니다. DB 저장·스케줄 활성화·외부 API 호출은 수행되지 않습니다."
                  : "컴파일에 실패했습니다. 아래 이슈를 확인하세요."}
              </p>

              <div className="flex flex-wrap gap-1.5">
                <span className="inline-flex items-center gap-1 text-[10px] font-mono bg-slate-50 border border-slate-200 rounded-md px-2 py-1">
                  <span className="text-slate-400">persisted</span>
                  <span
                    className="font-semibold text-slate-700"
                    data-testid="visual-pipeline-compile-persisted"
                  >
                    {String(result.persisted)}
                  </span>
                </span>
                {result.compile_result_id && (
                  <span className="inline-flex items-center gap-1 text-[10px] font-mono bg-slate-50 border border-slate-200 rounded-md px-2 py-1">
                    <span className="text-slate-400">result_id</span>
                    <span className="font-semibold text-slate-700" data-testid="visual-pipeline-compile-result-id">
                      {result.compile_result_id}
                    </span>
                  </span>
                )}
                {result.compile_version && (
                  <span className="inline-flex items-center gap-1 text-[10px] font-mono bg-slate-50 border border-slate-200 rounded-md px-2 py-1">
                    <span className="text-slate-400">version</span>
                    <span className="font-semibold text-slate-700">{result.compile_version}</span>
                  </span>
                )}
                {meta?.pattern && (
                  <span className="inline-flex items-center gap-1 text-[10px] font-mono bg-violet-50 border border-violet-100 text-violet-800 rounded-md px-2 py-1">
                    <span className="text-violet-400">pattern</span>
                    <span className="font-semibold" data-testid="visual-pipeline-compile-pattern">
                      {meta.pattern}
                    </span>
                  </span>
                )}
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-2 text-[10px] font-mono text-slate-600">
                <div className="bg-slate-50 border border-slate-100 rounded-md px-2 py-1.5 truncate">
                  graph_hash: {result.graph_version_hash ?? "-"}
                </div>
                <div className="bg-slate-50 border border-slate-100 rounded-md px-2 py-1.5 truncate">
                  config_hash: {result.config_hash ?? "-"}
                </div>
                <div className="bg-slate-50 border border-slate-100 rounded-md px-2 py-1.5">
                  compiled_at: {result.compiled_at ?? "-"}
                </div>
                <div className="bg-slate-50 border border-slate-100 rounded-md px-2 py-1.5">
                  validation: {result.validation_level ?? "STRICT"}
                </div>
              </div>

              {meta && (
                <div className="text-[10px] text-slate-600 space-y-0.5 font-mono">
                  <div>source={meta.source_node_id ?? "-"} · transform={meta.transform_node_id ?? "-"} · load={meta.load_node_id ?? "-"} · schedule={meta.schedule_node_id ?? "-"}</div>
                </div>
              )}

              {steps.length > 0 && (
                <div>
                  <div className="text-[9px] font-bold text-slate-400 uppercase tracking-wide mb-1.5">Steps</div>
                  <ul className="space-y-1" data-testid="visual-pipeline-compile-steps">
                    {steps.map((step) => (
                      <li
                        key={step.step_id}
                        className="text-[11px] font-mono bg-slate-50 border border-slate-100 rounded-md px-2 py-1.5 text-slate-700"
                      >
                        <span className="font-semibold">{step.type}</span>
                        {" · "}
                        {step.step_id}
                        {step.adapter ? ` · ${step.adapter}` : ""}
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {artifact?.schedule && (
                <div className="text-[11px] bg-slate-50 border border-slate-100 rounded-md px-2.5 py-2" data-testid="visual-pipeline-compile-schedule">
                  <div className="text-[9px] font-bold text-slate-400 uppercase tracking-wide mb-1">Schedule</div>
                  <div className="font-mono text-[10px] text-slate-700">
                    {String(artifact.schedule.cron_expression ?? "-")} · {String(artifact.schedule.timezone ?? "-")} · activation=
                    {String(artifact.schedule.activation ?? "NOT_REQUESTED")}
                  </div>
                </div>
              )}

              {artifact?.write_policy && Object.keys(artifact.write_policy).length > 0 && (
                <div className="text-[11px] bg-slate-50 border border-slate-100 rounded-md px-2.5 py-2">
                  <div className="text-[9px] font-bold text-slate-400 uppercase tracking-wide mb-1">Write policy</div>
                  <div className="font-mono text-[10px] text-slate-700">
                    table={String(artifact.write_policy.target_table ?? "-")} · mode=
                    {String(artifact.write_policy.write_mode ?? "-")}
                  </div>
                </div>
              )}

              {(wrapperIssues.length > 0 || detailIssues.length > 0) && (
                <div data-testid="visual-pipeline-compile-issues">
                  <div className="text-[9px] font-bold text-slate-400 uppercase tracking-wide mb-1.5">Issues</div>
                  {wrapperIssues.map((issue, idx) => (
                    <p key={`w-${idx}`} className="text-[11px] text-red-700 mb-2 font-medium">
                      {issue.message}
                    </p>
                  ))}
                  <div className="space-y-1.5">
                    {detailIssues.map((issue, idx) => (
                      <IssueRow key={`${issue.code}-${idx}`} issue={issue} onSelectNode={onSelectNode} />
                    ))}
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
}
