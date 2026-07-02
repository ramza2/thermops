import type { PipelineFlow, PipelineNodeSchema } from "@/types/pipelineBuilder";
import { nodeStateClass, nodeStateLabel, nodeTypeLabel } from "@/utils/pipelineBuilderFormat";

interface PipelineFlowChartProps {
  flow?: PipelineFlow;
  selectedNodeId?: string | null;
  onSelectNode: (nodeId: string) => void;
}

export function PipelineFlowChart({ flow, selectedNodeId, onSelectNode }: PipelineFlowChartProps) {
  const nodes = [...(flow?.nodes || [])].sort((a, b) => (a.order || 0) - (b.order || 0));
  if (!nodes.length) {
    return <p className="text-sm text-slate-400 p-4">파이프라인 흐름 정보가 없습니다.</p>;
  }

  return (
    <div className="overflow-x-auto pb-2">
      <div className="text-xs text-slate-500 mb-2">파이프라인 흐름 (Flow Chart)</div>
      <div className="flex items-stretch gap-2 min-w-max px-1 py-2">
        {nodes.map((node, idx) => (
          <div key={node.node_id} className="flex items-center gap-2">
            <NodeCard
              node={node}
              selected={selectedNodeId === node.node_id}
              onClick={() => onSelectNode(node.node_id)}
            />
            {idx < nodes.length - 1 && (
              <div className="text-slate-300 text-lg shrink-0" aria-hidden>
                →
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

function NodeCard({
  node,
  selected,
  onClick,
}: {
  node: PipelineNodeSchema;
  selected: boolean;
  onClick: () => void;
}) {
  const summary = summarizeConfig(node.config);
  return (
    <button
      type="button"
      onClick={onClick}
      className={`text-left w-40 shrink-0 rounded-lg border-2 p-3 transition-shadow hover:shadow-md ${nodeStateClass(node.config_state)} ${selected ? "ring-2 ring-blue-500" : ""}`}
    >
      <div className="text-[10px] text-slate-500 uppercase">{nodeTypeLabel(node.component_type)}</div>
      <div className="font-semibold text-sm text-slate-800 mt-0.5">{node.label}</div>
      <div className="text-[10px] mt-1 text-slate-600">
        {node.required ? "필수" : "선택"} · {nodeStateLabel(node.config_state)}
      </div>
      {summary && <div className="text-[10px] mt-1 text-slate-500 truncate" title={summary}>{summary}</div>}
      {(node.error_count || 0) > 0 && (
        <div className="text-[10px] text-red-600 mt-1">오류 {node.error_count}</div>
      )}
      {(node.warning_count || 0) > 0 && (
        <div className="text-[10px] text-amber-700 mt-1">경고 {node.warning_count}</div>
      )}
    </button>
  );
}

function summarizeConfig(config?: Record<string, unknown>): string {
  if (!config) return "";
  const parts = Object.entries(config)
    .filter(([, v]) => v !== null && v !== undefined && v !== "")
    .slice(0, 2)
    .map(([k, v]) => `${k}=${Array.isArray(v) ? v.join(",") : String(v)}`);
  return parts.join(" · ");
}
