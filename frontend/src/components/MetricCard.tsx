import { ReactNode } from "react";

export function MetricCard({ title, value, subtitle, icon }: { title: string; value: string | number; subtitle?: string; icon?: ReactNode }) {
  return (
    <div className="bg-white rounded-lg border border-slate-200 p-4 shadow-sm">
      <div className="flex items-start justify-between">
        <div>
          <p className="text-xs text-slate-500 font-medium uppercase tracking-wide">{title}</p>
          <p className="text-2xl font-bold mt-1 text-slate-900">{value}</p>
          {subtitle && <p className="text-xs text-slate-400 mt-1">{subtitle}</p>}
        </div>
        {icon && <div className="text-blue-600 opacity-80">{icon}</div>}
      </div>
    </div>
  );
}
