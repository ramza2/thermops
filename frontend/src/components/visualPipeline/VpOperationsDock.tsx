import { useMemo, type ReactNode } from "react";
import { ChevronDown, ChevronUp } from "lucide-react";

export type VpOperationsDockTab =
  | "graph"
  | "compile"
  | "materialization"
  | "run"
  | "history"
  | "validation";

export interface VpOperationsDockTabBadge {
  label: string;
  tone?: "neutral" | "success" | "warning" | "error" | "info";
}

interface VpOperationsDockProps {
  expanded: boolean;
  activeTab: VpOperationsDockTab;
  onToggleExpanded: () => void;
  onTabChange: (tab: VpOperationsDockTab) => void;
  tabBadges?: Partial<Record<VpOperationsDockTab, VpOperationsDockTabBadge | null>>;
  graphPanel: ReactNode;
  compilePanel: ReactNode;
  materializationPanel: ReactNode;
  runPanel: ReactNode;
  historyPanel: ReactNode;
  validationPanel: ReactNode;
}

const TABS: { id: VpOperationsDockTab; label: string }[] = [
  { id: "graph", label: "Graph" },
  { id: "compile", label: "Compile" },
  { id: "materialization", label: "실행 설정" },
  { id: "run", label: "실행" },
  { id: "history", label: "History" },
  { id: "validation", label: "Validation" },
];

const BADGE_TONE: Record<NonNullable<VpOperationsDockTabBadge["tone"]>, string> = {
  neutral: "bg-slate-100 border-slate-200 text-slate-600",
  success: "bg-emerald-50 border-emerald-200 text-emerald-700",
  warning: "bg-amber-50 border-amber-200 text-amber-800",
  error: "bg-red-50 border-red-200 text-red-700",
  info: "bg-sky-50 border-sky-200 text-sky-700",
};

function TabBadge({ badge }: { badge?: VpOperationsDockTabBadge | null }) {
  if (!badge?.label) return null;
  const tone = badge.tone ?? "neutral";
  return (
    <span
      className={`text-[9px] font-bold uppercase tracking-wide border rounded px-1 py-0.5 ${BADGE_TONE[tone]}`}
    >
      {badge.label}
    </span>
  );
}

export function VpOperationsDock({
  expanded,
  activeTab,
  onToggleExpanded,
  onTabChange,
  tabBadges = {},
  graphPanel,
  compilePanel,
  materializationPanel,
  runPanel,
  historyPanel,
  validationPanel,
}: VpOperationsDockProps) {
  const activePanel = useMemo(() => {
    switch (activeTab) {
      case "graph":
        return graphPanel;
      case "compile":
        return compilePanel;
      case "materialization":
        return materializationPanel;
      case "run":
        return runPanel;
      case "history":
        return historyPanel;
      case "validation":
        return validationPanel;
      default:
        return graphPanel;
    }
  }, [
    activeTab,
    graphPanel,
    compilePanel,
    materializationPanel,
    runPanel,
    historyPanel,
    validationPanel,
  ]);

  return (
    <div
      className="shrink-0 bg-white border border-slate-200 rounded-lg shadow-sm overflow-hidden flex flex-col"
      data-testid="visual-studio-operations-dock"
      data-expanded={expanded ? "true" : "false"}
    >
      <div className="flex items-center gap-2 px-2 py-1.5 border-b border-slate-100 bg-slate-50">
        <button
          type="button"
          className="inline-flex items-center gap-1 text-[10px] font-bold text-slate-500 uppercase tracking-wider shrink-0 hover:text-slate-700"
          onClick={onToggleExpanded}
          data-testid="visual-studio-operations-dock-toggle"
          aria-expanded={expanded}
        >
          Operations
          {expanded ? <ChevronDown className="w-3.5 h-3.5" /> : <ChevronUp className="w-3.5 h-3.5 rotate-180" />}
        </button>
        <div className="flex flex-wrap items-center gap-1 min-w-0 flex-1">
          {TABS.map((tab) => {
            const active = activeTab === tab.id;
            const badge = tabBadges[tab.id];
            return (
              <button
                key={tab.id}
                type="button"
                className={`inline-flex items-center gap-1 px-2 py-1 rounded-md text-[10px] font-medium border transition-colors ${
                  active
                    ? "bg-white border-slate-300 text-slate-800 shadow-sm"
                    : "bg-transparent border-transparent text-slate-500 hover:bg-white/70 hover:text-slate-700"
                }`}
                onClick={() => {
                  if (!expanded) onToggleExpanded();
                  onTabChange(tab.id);
                }}
                data-testid={`visual-studio-operations-dock-tab-${tab.id}`}
              >
                {tab.label}
                {!active && <TabBadge badge={badge} />}
              </button>
            );
          })}
        </div>
        <span className="text-[10px] text-slate-400 shrink-0 hidden sm:inline">
          {expanded ? "접기" : "펼치기"}
        </span>
      </div>

      {!expanded && (
        <div
          className="px-3 py-2 text-[11px] text-slate-500 flex flex-wrap items-center gap-2"
          data-testid="visual-studio-operations-dock-summary"
        >
          {TABS.map((tab) => {
            const badge = tabBadges[tab.id];
            if (!badge?.label) return null;
            return (
              <span key={tab.id} className="inline-flex items-center gap-1">
                <span className="text-slate-400">{tab.label}:</span>
                <TabBadge badge={badge} />
              </span>
            );
          })}
        </div>
      )}

      {expanded && (
        <div
          className="max-h-[40vh] overflow-y-auto"
          data-testid="visual-studio-operations-dock-body"
        >
          <div
            className="p-3"
            data-testid={`visual-studio-operations-dock-panel-${activeTab}`}
          >
            {activePanel}
          </div>
        </div>
      )}
    </div>
  );
}
