import { memo } from "react";
import { Handle, Position, type NodeProps } from "@xyflow/react";
import { makePortHandleId, NODE_STYLE } from "@/utils/visualPipelineGraph";

export interface VpNodeData {
  label?: string;
  component_type?: string;
  description?: string;
  input_ports?: string[];
  output_ports?: string[];
  [key: string]: unknown;
}

function VpFlowNodeComponent({ id, data, selected }: NodeProps) {
  const d = data as VpNodeData;
  const componentType = d.component_type ?? "VP_TRANSFORM";
  const style = NODE_STYLE[componentType] ?? {
    border: "border-slate-400",
    header: "bg-slate-500",
    tint: "bg-slate-50",
    accentDot: "bg-slate-400",
    minimap: "#64748b",
  };
  const inputs = d.input_ports ?? [];
  const outputs = d.output_ports ?? [];
  const typeShort = componentType.replace(/^VP_/, "");

  return (
    <div
      data-testid={id ? `visual-pipeline-node-${id}` : "visual-pipeline-node"}
      className={`w-[168px] rounded-lg border-2 shadow-sm overflow-hidden ${style.tint} ${
        selected
          ? "border-blue-500 ring-2 ring-blue-200 shadow-md shadow-blue-100"
          : style.border
      }`}
    >
      <div className={`${style.header} px-2.5 py-1.5 flex items-center gap-1.5`}>
        <span className="w-1.5 h-1.5 rounded-full bg-white/80 shrink-0" />
        <span className="text-white text-[10px] font-bold tracking-wide truncate leading-tight">
          {d.label ?? typeShort}
        </span>
      </div>
      <div className="px-2.5 py-2 space-y-1.5 bg-white/70">
        <span className="inline-block font-mono text-[9px] text-slate-500 bg-slate-100 border border-slate-200 rounded px-1.5 py-0.5 truncate max-w-full">
          {componentType}
        </span>
        {d.description && (
          <p className="text-[10px] text-slate-500 leading-snug line-clamp-2">{d.description}</p>
        )}
        {(inputs.length > 0 || outputs.length > 0) && (
          <div className="pt-1 space-y-1.5 border-t border-slate-100 relative">
            {inputs.length > 0 && (
              <div>
                <div className="text-[8px] font-bold uppercase tracking-wider text-slate-400 mb-0.5">In</div>
                <div className="flex flex-wrap gap-1">
                  {inputs.map((p, i) => (
                    <span
                      key={`inl-${p}`}
                      className="inline-flex items-center gap-1 text-[9px] font-mono text-slate-600 bg-slate-50 border border-slate-200 rounded-full px-1.5 py-0.5"
                    >
                      <span className="w-1.5 h-1.5 rounded-full bg-slate-300 shrink-0" />
                      {p}
                      <Handle
                        type="target"
                        position={Position.Left}
                        id={makePortHandleId("input", p)}
                        className="!w-2.5 !h-2.5 !bg-slate-400 !border-2 !border-white"
                        style={{ top: 72 + i * 18 }}
                      />
                    </span>
                  ))}
                </div>
              </div>
            )}
            {outputs.length > 0 && (
              <div>
                <div className="text-[8px] font-bold uppercase tracking-wider text-slate-400 mb-0.5 text-right">Out</div>
                <div className="flex flex-wrap gap-1 justify-end">
                  {outputs.map((p, i) => (
                    <span
                      key={`outl-${p}`}
                      className="inline-flex items-center gap-1 text-[9px] font-mono text-slate-600 bg-white border border-slate-200 rounded-full px-1.5 py-0.5"
                    >
                      {p}
                      <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${style.accentDot}`} />
                      <Handle
                        type="source"
                        position={Position.Right}
                        id={makePortHandleId("output", p)}
                        className="!w-2.5 !h-2.5 !border-2 !border-white"
                        style={{ top: 72 + i * 18, background: style.minimap }}
                      />
                    </span>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
        {inputs.length === 0 && outputs.length === 0 && (
          <>
            <Handle type="target" position={Position.Left} className="!w-2.5 !h-2.5 !bg-slate-400 !border-2 !border-white" />
            <Handle
              type="source"
              position={Position.Right}
              className="!w-2.5 !h-2.5 !border-2 !border-white"
              style={{ background: style.minimap }}
            />
          </>
        )}
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
