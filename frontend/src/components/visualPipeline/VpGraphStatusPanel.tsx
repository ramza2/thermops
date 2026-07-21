import { ChevronDown, GitBranch } from "lucide-react";
import { StatusBadge } from "@/components/StatusBadge";
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
  const fullPreview = JSON.stringify(graph, null, 2);

  return (
    <div className="mt-3 bg-white border border-slate-200 rounded-lg shadow-sm overflow-hidden">
      <button
        type="button"
        className="w-full px-4 py-2.5 border-b border-slate-100 bg-slate-50 flex items-center justify-between text-left hover:bg-slate-100/80 transition-colors"
        onClick={onToggle}
      >
        <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider flex items-center gap-1.5">
          <GitBranch className="w-3.5 h-3.5" /> Graph Status Panel
        </span>
        <span className="flex items-center gap-2">
          <span className="text-[10px] text-slate-400">{expanded ? "JSON 접기" : "JSON 펼치기"}</span>
          <ChevronDown className={`w-3.5 h-3.5 text-slate-400 transition-transform ${expanded ? "rotate-180" : ""}`} />
        </span>
      </button>

      <div className="px-4 py-3 flex flex-wrap items-center gap-2">
        <span className="inline-flex items-center gap-1.5 text-[10px] font-mono bg-slate-50 border border-slate-200 rounded-md px-2 py-1">
          <span className="text-slate-400">pipeline_id</span>
          <span className="font-semibold text-slate-700">{pipeline?.pipeline_id ?? "-"}</span>
        </span>
        <span className="inline-flex items-center gap-1.5 text-[10px] font-mono bg-slate-50 border border-slate-200 rounded-md px-2 py-1">
          <span className="text-slate-400">kind</span>
          <span className="font-semibold text-slate-700">{pipeline?.pipeline_kind ?? "VISUAL_DATA_LOAD"}</span>
        </span>
        <span className="inline-flex items-center gap-1.5 text-[10px] font-mono bg-slate-50 border border-slate-200 rounded-md px-2 py-1">
          <span className="text-slate-400">template</span>
          <span className="font-semibold text-slate-700">{pipeline?.template_id ?? "-"}</span>
        </span>
        <StatusBadge status={pipeline?.current_sync_status ?? "NOT_COMPILED"} />
        <span className="inline-flex items-center gap-1 text-[10px] font-mono bg-blue-50 border border-blue-100 text-blue-700 rounded-full px-2 py-0.5">
          nodes {counts.nodes}
        </span>
        <span className="inline-flex items-center gap-1 text-[10px] font-mono bg-blue-50 border border-blue-100 text-blue-700 rounded-full px-2 py-0.5">
          edges {counts.edges}
        </span>
        <span
          className={`inline-flex items-center gap-1 text-[10px] font-medium rounded-full px-2 py-0.5 border ${
            dirty
              ? "bg-amber-50 border-amber-200 text-amber-700"
              : "bg-emerald-50 border-emerald-200 text-emerald-700"
          }`}
        >
          {dirty ? "● dirty" : "✓ saved"}
        </span>
        <span className="text-[10px] font-mono text-slate-400 ml-auto">
          last_saved: {lastSavedAt ?? "-"}
        </span>
      </div>

      {expanded && (
        <div className="px-4 pb-3 border-t border-slate-100">
          <div className="text-[9px] font-bold text-slate-400 uppercase tracking-wide mb-1.5 mt-2.5">
            Graph JSON Preview
          </div>
          <pre className="bg-slate-900 text-slate-100 border border-slate-700 rounded-md p-3 text-[10px] font-mono leading-relaxed overflow-x-auto max-h-56">
            {fullPreview}
          </pre>
        </div>
      )}
    </div>
  );
}
