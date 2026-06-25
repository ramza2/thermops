import { ReactNode } from "react";

export function ChartCard({ title, subtitle, children, action }: { title: string; subtitle?: string; children: ReactNode; action?: ReactNode }) {
  return (
    <div className="bg-white rounded-lg border border-slate-200 shadow-sm">
      <div className="flex items-center justify-between px-4 py-3 border-b">
        <div>
          <h3 className="text-sm font-semibold text-slate-800">{title}</h3>
          {subtitle && <p className="text-xs text-slate-500 mt-0.5">{subtitle}</p>}
        </div>
        {action}
      </div>
      <div className="p-4">{children}</div>
    </div>
  );
}
