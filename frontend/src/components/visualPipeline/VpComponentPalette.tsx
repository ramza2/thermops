import type { ComponentCatalogItem } from "@/types/visualPipeline";
import { NODE_STYLE } from "@/utils/visualPipelineGraph";

interface VpComponentPaletteProps {
  active: ComponentCatalogItem[];
  disabled: ComponentCatalogItem[];
  loading?: boolean;
  error?: string;
  onAdd: (component: ComponentCatalogItem) => void;
}

const PALETTE_BORDER: Record<string, string> = {
  VP_REST_API_SOURCE: "border-blue-400 bg-blue-50 hover:border-blue-500 hover:shadow-sm",
  VP_TRANSFORM: "border-amber-400 bg-amber-50 hover:border-amber-500 hover:shadow-sm",
  VP_UPSERT_LOAD: "border-emerald-400 bg-emerald-50 hover:border-emerald-500 hover:shadow-sm",
  VP_CRON_SCHEDULE: "border-indigo-400 bg-indigo-50 hover:border-indigo-500 hover:shadow-sm",
};

export function VpComponentPalette({ active, disabled, loading, error, onAdd }: VpComponentPaletteProps) {
  if (loading) {
    return (
      <div className="w-[260px] shrink-0 bg-white border border-slate-200 rounded-lg shadow-sm p-3 text-xs text-slate-400">
        카탈로그 로딩 중…
      </div>
    );
  }
  if (error) {
    return (
      <div className="w-[260px] shrink-0 bg-red-50 border border-red-200 rounded-lg shadow-sm p-3 text-xs text-red-700">
        {error}
      </div>
    );
  }

  return (
    <div
      className="w-[260px] shrink-0 bg-white border border-slate-200 rounded-lg shadow-sm flex flex-col overflow-hidden max-h-[min(720px,calc(100vh-12rem))]"
      data-testid="visual-pipeline-palette"
    >
      <div className="px-3 py-2.5 border-b border-slate-100 bg-slate-50">
        <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">Component Palette</span>
        <p className="text-[10px] text-slate-400 mt-0.5">클릭하여 Canvas에 추가</p>
      </div>
      <div className="flex-1 overflow-y-auto py-2.5 px-2.5 space-y-2">
        <div className="flex items-center justify-between px-0.5 mb-1">
          <span className="text-[9px] font-bold text-slate-400 uppercase tracking-wide">ACTIVE</span>
          <span className="text-[9px] font-mono text-slate-400">{active.length}</span>
        </div>
        {active.map((c) => {
          const accent = NODE_STYLE[c.component_type]?.accentDot ?? "bg-slate-400";
          return (
            <button
              key={c.component_type}
              type="button"
              title={`${c.description ?? c.display_name}\n클릭하여 추가`}
              onClick={() => onAdd(c)}
              className={`w-full text-left p-2.5 rounded-lg border-2 cursor-pointer transition-all ${
                PALETTE_BORDER[c.component_type] ?? "border-slate-200 bg-white hover:bg-slate-50"
              }`}
            >
              <div className="flex items-start justify-between gap-1">
                <div className="font-semibold text-slate-800 text-[11px] leading-tight">{c.display_name}</div>
                <span className="text-[8px] font-bold uppercase tracking-wide text-slate-500 bg-white/80 border border-slate-200 rounded px-1 py-0.5 shrink-0">
                  {c.category}
                </span>
              </div>
              <div className="font-mono text-[9px] text-slate-500 mt-1 truncate">{c.component_type}</div>
              {c.description && (
                <p className="text-[10px] text-slate-500 mt-1 line-clamp-2 leading-snug">{c.description}</p>
              )}
              <div className="flex flex-wrap gap-1 mt-2">
                <span className="inline-flex items-center gap-1 text-[9px] font-mono text-slate-600 bg-white border border-slate-200 rounded-full px-1.5 py-0.5">
                  <span className="w-1.5 h-1.5 rounded-full bg-slate-300" />
                  in {c.input_ports?.length ?? 0}
                </span>
                <span className="inline-flex items-center gap-1 text-[9px] font-mono text-slate-600 bg-white border border-slate-200 rounded-full px-1.5 py-0.5">
                  <span className={`w-1.5 h-1.5 rounded-full ${accent}`} />
                  out {c.output_ports?.length ?? 0}
                </span>
              </div>
            </button>
          );
        })}

        <div className="flex items-center justify-between px-0.5 mt-3 mb-1">
          <span className="text-[9px] font-bold text-slate-400 uppercase tracking-wide">DISABLED</span>
          <span className="text-[9px] font-mono text-slate-400">{disabled.length}</span>
        </div>
        {disabled.map((c) => (
          <div
            key={c.component_type}
            title={c.disabled_reason ?? "Coming later"}
            className="p-2.5 rounded-lg border border-slate-200 bg-slate-50 opacity-75 cursor-not-allowed relative"
          >
            <span className="absolute top-1.5 right-1.5 text-[8px] font-bold bg-slate-200 text-slate-500 px-1.5 py-0.5 rounded">
              Coming later
            </span>
            <div className="font-semibold text-slate-500 text-[11px] pr-16">{c.display_name}</div>
            <div className="font-mono text-[9px] text-slate-400 mt-0.5 truncate">{c.component_type}</div>
            {c.disabled_reason && (
              <p className="text-[10px] text-slate-400 mt-1 line-clamp-2">{c.disabled_reason}</p>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
