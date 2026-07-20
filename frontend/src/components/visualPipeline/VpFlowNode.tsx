import { memo } from "react";
import { Handle, Position, type NodeProps } from "@xyflow/react";
import { NODE_STYLE } from "@/utils/visualPipelineGraph";

export interface VpNodeData {
  label?: string;
  component_type?: string;
  description?: string;
  input_ports?: string[];
  output_ports?: string[];
  [key: string]: unknown;
}

function VpFlowNodeComponent({ data, selected }: NodeProps) {
  const d = data as VpNodeData;
  const componentType = d.component_type ?? "VP_TRANSFORM";
  const style = NODE_STYLE[componentType] ?? { border: "border-slate-400", header: "bg-slate-500" };
  const inputs = d.input_ports ?? [];
  const outputs = d.output_ports ?? [];

  return (
    <div
      className={`rounded-lg border-2 bg-white shadow-sm min-w-[148px] max-w-[168px] ${
        selected ? "border-blue-500 shadow-md" : style.border
      }`}
    >
      <div className={`${style.header} rounded-t px-2 py-1.5`}>
        <span className="text-white text-[10px] font-bold uppercase tracking-wide truncate block">
          {componentType.replace("VP_", "")}
        </span>
      </div>
      <div className="px-2 py-1.5">
        <div className="text-xs font-semibold text-slate-700 leading-tight">{d.label ?? componentType}</div>
        {d.description && (
          <div className="text-[10px] text-slate-400 mt-0.5 truncate">{d.description}</div>
        )}
      </div>
      <div className="px-2 pb-2 space-y-0.5 relative">
        {inputs.map((p, i) => (
          <Handle
            key={`in-${p}`}
            type="target"
            position={Position.Left}
            id={p}
            style={{ top: 48 + i * 14, background: "#94a3b8" }}
          />
        ))}
        {outputs.map((p, i) => (
          <Handle
            key={`out-${p}`}
            type="source"
            position={Position.Right}
            id={p}
            style={{ top: 48 + i * 14, background: "#60a5fa" }}
          />
        ))}
        {inputs.map((p) => (
          <div key={`inl-${p}`} className="flex items-center gap-1 text-[9px] text-slate-400">
            <span className="w-2 h-2 rounded-full bg-slate-300 border border-slate-400 shrink-0" />
            <span className="font-mono truncate">{p}</span>
          </div>
        ))}
        {outputs.map((p) => (
          <div key={`outl-${p}`} className="flex items-center justify-end gap-1 text-[9px] text-slate-400">
            <span className="font-mono truncate">{p}</span>
            <span className="w-2 h-2 rounded-full bg-blue-300 border border-blue-400 shrink-0" />
          </div>
        ))}
      </div>
    </div>
  );
}

export const VpFlowNode = memo(VpFlowNodeComponent);

export function buildNodeTypes(): Record<string, typeof VpFlowNode> {
  const types: Record<string, typeof VpFlowNode> = {};
  for (const t of ["VP_REST_API_SOURCE", "VP_TRANSFORM", "VP_UPSERT_LOAD", "VP_CRON_SCHEDULE"]) {
    types[t] = VpFlowNode;
  }
  return types;
}
