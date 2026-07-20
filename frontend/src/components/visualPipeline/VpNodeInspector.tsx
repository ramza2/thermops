import { Trash2 } from "lucide-react";
import type { Node } from "@xyflow/react";
import { Button } from "@/components/Button";
import type { ComponentCatalogItem } from "@/types/visualPipeline";
import { placeholderConfigJson } from "@/utils/visualPipelineGraph";

interface VpNodeInspectorProps {
  node: Node | null;
  catalogItem: ComponentCatalogItem | null;
  onLabelChange: (label: string) => void;
  onDelete: () => void;
}

export function VpNodeInspector({ node, catalogItem, onLabelChange, onDelete }: VpNodeInspectorProps) {
  if (!node) {
    return (
      <div className="w-52 shrink-0 bg-white border border-slate-200 rounded-lg flex flex-col overflow-hidden min-h-[320px]">
        <div className="px-3 py-2 border-b border-slate-100 bg-slate-50">
          <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">Node Inspector</span>
        </div>
        <div className="flex-1 flex flex-col items-center justify-center p-4 text-center text-slate-400 text-xs">
          노드를 선택하면 상세 정보가 표시됩니다.
        </div>
      </div>
    );
  }

  const componentType = String(node.type ?? node.data?.component_type ?? "");
  const label = String(node.data?.label ?? "");
  const inputs = catalogItem?.input_ports?.map((p) => p.port_id) ?? [];
  const outputs = catalogItem?.output_ports?.map((p) => p.port_id) ?? [];

  const rows: [string, string][] = [
    ["node_id", node.id],
    ["component_type", componentType],
    ["category", catalogItem?.category ?? "-"],
    ["status", catalogItem?.status ?? "ACTIVE"],
  ];

  return (
    <div className="w-52 shrink-0 bg-white border border-slate-200 rounded-lg flex flex-col overflow-hidden max-h-[560px]">
      <div className="px-3 py-2 border-b border-slate-100 bg-slate-50">
        <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">Node Inspector</span>
      </div>
      <div className="flex-1 overflow-y-auto p-3 space-y-3 text-xs">
        <div>
          <div className="text-[9px] font-bold text-slate-400 uppercase mb-1.5">노드 정보</div>
          {rows.map(([k, v]) => (
            <div key={k} className="flex justify-between py-1 border-b border-slate-100 last:border-0 gap-2">
              <span className="text-[10px] text-slate-400 font-mono shrink-0">{k}</span>
              <span className="text-[10px] font-medium text-slate-700 font-mono text-right break-all">{v}</span>
            </div>
          ))}
        </div>
        <div>
          <div className="text-[9px] font-bold text-slate-400 uppercase mb-1.5">Ports</div>
          {inputs.map((p) => (
            <div key={`in-${p}`} className="text-[10px] font-mono text-slate-500">IN: {p}</div>
          ))}
          {outputs.map((p) => (
            <div key={`out-${p}`} className="text-[10px] font-mono text-slate-500">OUT: {p}</div>
          ))}
        </div>
        <div>
          <div className="text-[9px] font-bold text-slate-400 uppercase mb-1.5">Config (placeholder)</div>
          <pre className="bg-slate-50 border border-slate-200 rounded p-2 text-[9px] font-mono text-slate-600 whitespace-pre-wrap leading-relaxed">
            {placeholderConfigJson(componentType)}
          </pre>
          <p className="text-[9px] text-amber-700 mt-1">S3: 상세 Form 미구현 (S4+)</p>
        </div>
        <div>
          <div className="text-[9px] font-bold text-slate-400 uppercase mb-1.5">Label 수정</div>
          <input
            value={label}
            onChange={(e) => onLabelChange(e.target.value)}
            className="h-7 px-2 text-xs border border-slate-300 rounded w-full focus:outline-none focus:ring-1 focus:ring-blue-500"
          />
        </div>
        <Button variant="danger" icon={<Trash2 className="w-3 h-3" />} onClick={onDelete} className="w-full justify-center text-xs">
          노드 삭제
        </Button>
      </div>
    </div>
  );
}
