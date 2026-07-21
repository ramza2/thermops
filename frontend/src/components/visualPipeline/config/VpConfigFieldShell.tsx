import type { ReactNode } from "react";

interface VpConfigFieldShellProps {
  fieldKey: string;
  label: string;
  required?: boolean;
  help?: string;
  warning?: string;
  children: ReactNode;
}

export function VpConfigFieldShell({
  fieldKey,
  label,
  required,
  help,
  warning,
  children,
}: VpConfigFieldShellProps) {
  return (
    <div className="space-y-1" data-testid={`visual-pipeline-inspector-config-field-${fieldKey}`}>
      <label className="flex items-center gap-1 text-[10px] font-medium text-slate-600">
        <span>{label}</span>
        {required && <span className="text-red-500">*</span>}
      </label>
      {children}
      {help && <p className="text-[9px] text-slate-400 leading-relaxed">{help}</p>}
      {warning && <p className="text-[9px] text-amber-700 leading-relaxed">{warning}</p>}
    </div>
  );
}
