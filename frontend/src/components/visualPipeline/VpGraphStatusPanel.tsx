import { ChevronDown, GitBranch } from "lucide-react";
import type { VisualPipelineDetail, VisualPipelineGraph } from "@/types/visualPipeline";
import { graphCounts } from "@/utils/visualPipelineGraph";

interface VpGraphStatusPanelProps {
  pipeline: VisualPipelineDetail | null;
  graph: VisualPipelineGraph;
  dirty: boolean;
  lastSavedAt?: string | null;
  expanded: boolean;
  onToggle: () => void;
}

export function VpGraphStatusPanel({
  pipeline,
  graph,
  dirty,
  lastSavedAt,
  expanded,
  onToggle,
}: VpGraphStatusPanelProps) {
  const counts = graphCounts(graph);
  const preview = JSON.stringify(
    {
      nodes: counts.nodes,
      edges: counts.edges,
      viewport: graph.viewport,
    },
    null,
    2,
  );

  const meta: [string, string][] = [
    ["pipeline_id", pipeline?.pipeline_id ?? "-"],
    ["pipeline_kind", pipeline?.pipeline_kind ?? "VISUAL_DATA_LOAD"],
    ["template_id", pipeline?.template_id ?? "-"],
    ["current_sync_status", pipeline?.current_sync_status ?? "NOT_COMPILED"],
    ["node_count", String(counts.nodes)],
    ["edge_count", String(counts.edges)],
    ["dirty", dirty ? "true" : "false"],
    ["last_saved", lastSavedAt ?? "-"],
  ];

  return (
    <div className="mt-3 bg-white border border-slate-200 rounded-lg overflow-hidden">
      <button
        type="button"
        className="w-full px-4 py-2 border-b border-slate-100 bg-slate-50 flex items-center justify-between text-left"
        onClick={onToggle}
      >
        <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider flex items-center gap-1.5">
          <GitBranch className="w-3 h-3" /> Graph Status Panel
        </span>
        <ChevronDown className={`w-3 h-3 text-slate-400 transition-transform ${expanded ? "rotate-180" : ""}`} />
      </button>
      <div className="px-4 py-3 flex flex-wrap gap-x-6 gap-y-2 text-xs font-mono">
        {meta.map(([k, v]) => (
          <div key={k} className="flex gap-1.5">
            <span className="text-slate-400">{k}:</span>
            <span
              className={`font-semibold ${
                (k === "current_sync_status" || (k === "dirty" && v === "true")) ? "text-amber-600" : "text-slate-700"
              }`}
            >
              {v}
            </span>
          </div>
        ))}
      </div>
      {expanded && (
        <div className="px-4 pb-3 border-t border-slate-100">
          <div className="text-[9px] font-bold text-slate-400 uppercase tracking-wide mb-1.5 mt-2">
            Graph JSON Preview
          </div>
          <pre className="bg-slate-50 border border-slate-200 rounded p-3 text-[10px] font-mono text-slate-600 leading-relaxed overflow-x-auto">
            {preview}
          </pre>
        </div>
      )}
    </div>
  );
}
