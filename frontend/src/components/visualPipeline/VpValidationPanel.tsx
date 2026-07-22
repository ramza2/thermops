import { AlertTriangle, CheckCircle2, ChevronDown, Info, ShieldAlert, ShieldCheck } from "lucide-react";
import type { VisualPipelineValidationIssue, VisualPipelineValidationResponse } from "@/types/visualPipeline";

interface VpValidationPanelProps {
  result: VisualPipelineValidationResponse | null;
  loading?: boolean;
  expanded: boolean;
  onToggle: () => void;
  onSelectNode?: (nodeId: string) => void;
}

const SEV_STYLE: Record<string, string> = {
  ERROR: "bg-red-50 border-red-200 text-red-700",
  WARNING: "bg-amber-50 border-amber-200 text-amber-800",
  INFO: "bg-sky-50 border-sky-200 text-sky-700",
  OK: "bg-emerald-50 border-emerald-200 text-emerald-700",
};

function IssueRow({
  issue,
  onSelectNode,
}: {
  issue: VisualPipelineValidationIssue;
  onSelectNode?: (nodeId: string) => void;
}) {
  const nodeId = issue.node_id || issue.source_node_id;
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
          {(issue.source_node_id || issue.target_node_id || issue.source_port) && (
            <p className="mt-1 font-mono text-[10px] opacity-70">
              {issue.source_handle || `${issue.source_component_type ?? issue.source_node_id}${issue.source_port ? `.${issue.source_port}` : ""}`}
              {" → "}
              {issue.target_handle || `${issue.target_component_type ?? issue.target_node_id}${issue.target_port ? `.${issue.target_port}` : ""}`}
              {issue.data_type || issue.source_data_type
                ? ` · ${issue.data_type || issue.source_data_type}`
                : ""}
            </p>
          )}
          {issue.phase === "CONFIG" && issue.component_type && (
            <p className="mt-1 font-mono text-[10px] opacity-70">
              {issue.component_type}
              {issue.node_id ? ` · ${issue.node_id}` : ""}
            </p>
          )}
        </div>
        {nodeId && onSelectNode && (
          <button
            type="button"
            className="shrink-0 text-[10px] font-medium underline underline-offset-2"
            onClick={() => onSelectNode(nodeId)}
          >
            선택
          </button>
        )}
      </div>
    </div>
  );
}

export function VpValidationPanel({
  result,
  loading,
  expanded,
  onToggle,
  onSelectNode,
}: VpValidationPanelProps) {
  const severity = result?.severity ?? "OK";
  const summary = result?.summary;

  return (
    <div
      className="mt-3 bg-white border border-slate-200 rounded-lg shadow-sm overflow-hidden"
      data-testid="visual-pipeline-validation-panel"
    >
      <button
        type="button"
        className="w-full px-4 py-2.5 border-b border-slate-100 bg-slate-50 flex items-center justify-between text-left hover:bg-slate-100/80 transition-colors"
        onClick={onToggle}
      >
        <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider flex items-center gap-1.5">
          <ShieldCheck className="w-3.5 h-3.5" /> Graph Validation
        </span>
        <span className="flex items-center gap-2">
          {loading && <span className="text-[10px] text-blue-600 animate-pulse">검증 중…</span>}
          {result && (
            <span className={`text-[10px] font-bold rounded-full px-2 py-0.5 border ${SEV_STYLE[severity]}`}>
              {severity}
            </span>
          )}
          <ChevronDown className={`w-3.5 h-3.5 text-slate-400 transition-transform ${expanded ? "rotate-180" : ""}`} />
        </span>
      </button>

      <div className="px-4 py-3">
        {!result && !loading && (
          <div className="text-xs text-slate-500 leading-relaxed">
            <p className="font-medium text-slate-600">아직 Graph 검증을 실행하지 않았습니다.</p>
            <p className="mt-1 text-[11px] text-slate-400">
              현재 Canvas 상태를 기준으로 노드, 연결, 포트 호환성을 확인합니다. Toolbar의 「Graph 검증」을 사용하세요.
            </p>
          </div>
        )}

        {result && (
          <div className="space-y-2">
            <div className="flex flex-wrap items-center gap-2 text-[11px]">
              {severity === "OK" && (
                <span className="inline-flex items-center gap-1 text-emerald-700">
                  <CheckCircle2 className="w-3.5 h-3.5" /> 현재 Graph는 기본 검증을 통과했습니다.
                </span>
              )}
              {severity === "WARNING" && (
                <span className="inline-flex items-center gap-1 text-amber-700">
                  <AlertTriangle className="w-3.5 h-3.5" /> 저장은 가능하지만 실행/컴파일 전 확인이 필요한 항목이 있습니다.
                </span>
              )}
              {severity === "ERROR" && (
                <span className="inline-flex items-center gap-1 text-red-700">
                  <ShieldAlert className="w-3.5 h-3.5" /> Graph 구조 오류가 있습니다. 저장은 가능하지만 실행/컴파일 대상이 될 수 없습니다.
                </span>
              )}
              {severity === "INFO" && (
                <span className="inline-flex items-center gap-1 text-sky-700">
                  <Info className="w-3.5 h-3.5" /> 안내 항목이 있습니다.
                </span>
              )}
            </div>
            {summary && (
              <div className="flex flex-wrap gap-1.5">
                <span className="text-[10px] font-mono bg-slate-50 border border-slate-200 rounded-full px-2 py-0.5">
                  nodes {summary.node_count}
                </span>
                <span className="text-[10px] font-mono bg-slate-50 border border-slate-200 rounded-full px-2 py-0.5">
                  edges {summary.edge_count}
                </span>
                <span className="text-[10px] font-mono bg-red-50 border border-red-100 text-red-700 rounded-full px-2 py-0.5">
                  errors {summary.error_count}
                </span>
                <span className="text-[10px] font-mono bg-amber-50 border border-amber-100 text-amber-700 rounded-full px-2 py-0.5">
                  warnings {summary.warning_count}
                </span>
                <span className="text-[10px] font-mono bg-sky-50 border border-sky-100 text-sky-700 rounded-full px-2 py-0.5">
                  info {summary.info_count}
                </span>
                <span className="text-[10px] font-mono text-slate-400 ml-auto">
                  level {result.validation_level}
                </span>
              </div>
            )}
          </div>
        )}
      </div>

      {expanded && result && (
        <div className="px-4 pb-3 border-t border-slate-100 space-y-2 max-h-64 overflow-y-auto">
          <div className="text-[9px] font-bold text-slate-400 uppercase tracking-wide mt-2.5 mb-1">Issues</div>
          {result.issues.length === 0 ? (
            <p className="text-xs text-slate-400 py-2">이슈가 없습니다.</p>
          ) : (
            result.issues.map((issue, idx) => (
              <IssueRow key={`${issue.code}-${idx}`} issue={issue} onSelectNode={onSelectNode} />
            ))
          )}
        </div>
      )}
    </div>
  );
}
