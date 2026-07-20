import type { ComponentCatalogItem } from "@/types/visualPipeline";

interface VpComponentPaletteProps {
  active: ComponentCatalogItem[];
  disabled: ComponentCatalogItem[];
  loading?: boolean;
  error?: string;
  onAdd: (component: ComponentCatalogItem) => void;
}

export function VpComponentPalette({ active, disabled, loading, error, onAdd }: VpComponentPaletteProps) {
  if (loading) {
    return (
      <div className="w-44 shrink-0 bg-white border border-slate-200 rounded-lg p-3 text-xs text-slate-400">
        카탈로그 로딩 중…
      </div>
    );
  }
  if (error) {
    return (
      <div className="w-44 shrink-0 bg-red-50 border border-red-200 rounded-lg p-3 text-xs text-red-700">
        {error}
      </div>
    );
  }

  const colorMap: Record<string, string> = {
    VP_REST_API_SOURCE: "border-blue-300 bg-blue-50 hover:border-blue-400",
    VP_TRANSFORM: "border-emerald-300 bg-emerald-50 hover:border-emerald-400",
    VP_UPSERT_LOAD: "border-violet-300 bg-violet-50 hover:border-violet-400",
    VP_CRON_SCHEDULE: "border-amber-300 bg-amber-50 hover:border-amber-400",
  };

  return (
    <div className="w-44 shrink-0 bg-white border border-slate-200 rounded-lg flex flex-col overflow-hidden max-h-[560px]">
      <div className="px-3 py-2 border-b border-slate-100 bg-slate-50">
        <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">Component Palette</span>
      </div>
      <div className="flex-1 overflow-y-auto py-2 px-2 space-y-1">
        <div className="text-[9px] font-bold text-slate-400 uppercase px-1 mb-1">ACTIVE</div>
        {active.map((c) => (
          <button
            key={c.component_type}
            type="button"
            title={c.description}
            onClick={() => onAdd(c)}
            className={`w-full text-left p-2 rounded border cursor-pointer transition-all text-xs ${
              colorMap[c.component_type] ?? "border-slate-200 bg-white hover:bg-slate-50"
            }`}
          >
            <div className="font-semibold text-slate-700 text-[10px] leading-tight">{c.display_name}</div>
            <div className="font-mono text-[9px] text-slate-400 mt-0.5 truncate">{c.component_type}</div>
          </button>
        ))}
        <div className="text-[9px] font-bold text-slate-400 uppercase px-1 mt-2 mb-1">DISABLED</div>
        {disabled.map((c) => (
          <div
            key={c.component_type}
            title={c.disabled_reason ?? "Coming later"}
            className="p-2 rounded border border-slate-200 bg-slate-50 opacity-60 cursor-not-allowed relative"
          >
            <div className="font-semibold text-slate-400 text-[10px]">{c.display_name}</div>
            <div className="font-mono text-[9px] text-slate-300 mt-0.5 truncate">{c.component_type}</div>
            <span className="absolute top-1 right-1 text-[8px] bg-slate-200 text-slate-500 px-1 rounded font-bold">Later</span>
          </div>
        ))}
      </div>
    </div>
  );
}
