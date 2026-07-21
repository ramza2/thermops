import { Box, Trash2 } from "lucide-react";
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
      <div
        className="w-[320px] shrink-0 bg-white border border-slate-200 rounded-lg shadow-sm flex flex-col overflow-hidden min-h-[320px]"
        data-testid="visual-pipeline-inspector"
      >
        <div className="px-3 py-2.5 border-b border-slate-100 bg-slate-50">
          <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">Node Inspector</span>
        </div>
        <div className="flex-1 flex flex-col items-center justify-center p-6 text-center text-slate-400">
          <Box className="w-8 h-8 mb-3 text-slate-300" />
          <p className="text-xs font-medium text-slate-500">노드를 선택하세요</p>
          <p className="text-[10px] mt-1.5 leading-relaxed max-w-[200px]">
            Canvas에서 노드를 클릭하면 속성·포트·placeholder config를 확인할 수 있습니다.
          </p>
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
    <div
      className="w-[320px] shrink-0 bg-white border border-slate-200 rounded-lg shadow-sm flex flex-col overflow-hidden max-h-[min(720px,calc(100vh-12rem))]"
      data-testid="visual-pipeline-inspector"
    >
      <div className="px-3 py-2.5 border-b border-slate-100 bg-slate-50">
        <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">Node Inspector</span>
        <p className="text-[10px] text-slate-400 mt-0.5 truncate">{label || componentType}</p>
      </div>
      <div className="flex-1 overflow-y-auto p-3 space-y-3 text-xs">
        <section className="rounded-lg border border-slate-100 bg-slate-50/60 p-2.5">
          <div className="text-[9px] font-bold text-slate-400 uppercase tracking-wide mb-2">노드 정보</div>
          {rows.map(([k, v]) => (
            <div key={k} className="flex justify-between py-1.5 border-b border-slate-100 last:border-0 gap-2">
              <span className="text-[10px] text-slate-400 font-mono shrink-0">{k}</span>
              <span className="text-[10px] font-medium text-slate-700 font-mono text-right break-all">{v}</span>
            </div>
          ))}
        </section>

        <section className="rounded-lg border border-slate-100 p-2.5">
          <div className="text-[9px] font-bold text-slate-400 uppercase tracking-wide mb-2">Label</div>
          <input
            value={label}
            onChange={(e) => onLabelChange(e.target.value)}
            className="h-8 px-2.5 text-xs border border-slate-300 rounded-md w-full focus:outline-none focus:ring-1 focus:ring-blue-500 bg-white"
          />
        </section>

        <section className="rounded-lg border border-slate-100 p-2.5">
          <div className="text-[9px] font-bold text-slate-400 uppercase tracking-wide mb-2">Ports</div>
          <div className="space-y-1">
            {inputs.map((p) => (
              <div key={`in-${p}`} className="flex items-center gap-1.5 text-[10px] font-mono text-slate-600">
                <span className="w-1.5 h-1.5 rounded-full bg-slate-300" />
                <span className="text-slate-400 w-6">IN</span>
                {p}
              </div>
            ))}
            {outputs.map((p) => (
              <div key={`out-${p}`} className="flex items-center gap-1.5 text-[10px] font-mono text-slate-600">
                <span className="w-1.5 h-1.5 rounded-full bg-blue-400" />
                <span className="text-slate-400 w-6">OUT</span>
                {p}
              </div>
            ))}
            {inputs.length === 0 && outputs.length === 0 && (
              <p className="text-[10px] text-slate-400">포트 정보 없음</p>
            )}
          </div>
        </section>

        <section className="rounded-lg border border-slate-100 p-2.5">
          <div className="text-[9px] font-bold text-slate-400 uppercase tracking-wide mb-2">Config (placeholder)</div>
          <pre className="bg-slate-900 text-slate-100 border border-slate-700 rounded-md p-2.5 text-[10px] font-mono whitespace-pre-wrap leading-relaxed overflow-x-auto">
            {placeholderConfigJson(componentType)}
          </pre>
          <p className="text-[9px] text-amber-700 mt-1.5">상세 Form은 이후 단계에서 구현됩니다.</p>
        </section>

        <Button variant="danger" icon={<Trash2 className="w-3 h-3" />} onClick={onDelete} className="w-full justify-center text-xs">
          노드 삭제
        </Button>
      </div>
    </div>
  );
}
