import { useEffect, useState } from "react";
import { VpConfigFieldShell } from "@/components/visualPipeline/config/VpConfigFieldShell";

const INPUT_CLASS =
  "h-8 px-2.5 text-xs border border-slate-300 rounded-md w-full focus:outline-none focus:ring-1 focus:ring-blue-500 bg-white disabled:bg-slate-50 disabled:text-slate-400";

function valueToDraft(value: unknown): string {
  if (value === undefined || value === null) return "";
  if (Array.isArray(value)) {
    return value.map((v) => String(v).trim()).filter(Boolean).join(", ");
  }
  return String(value);
}

function parseColumnList(text: string): string[] {
  return text
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean);
}

interface VpColumnListFieldProps {
  fieldKey: string;
  label: string;
  value: unknown;
  placeholder?: string;
  help?: string;
  required?: boolean;
  disabled?: boolean;
  warning?: string;
  onChange: (patch: Record<string, unknown>) => void;
}

export function VpColumnListField({
  fieldKey,
  label,
  value,
  placeholder,
  help,
  required,
  disabled,
  warning,
  onChange,
}: VpColumnListFieldProps) {
  const [draft, setDraft] = useState(() => valueToDraft(value));

  useEffect(() => {
    setDraft(valueToDraft(value));
  }, [value, fieldKey]);

  const handleChange = (text: string) => {
    setDraft(text);
    const trimmed = text.trim();
    if (trimmed === "") {
      onChange({ [fieldKey]: undefined });
      return;
    }
    onChange({ [fieldKey]: parseColumnList(text) });
  };

  return (
    <VpConfigFieldShell fieldKey={fieldKey} label={label} required={required} help={help} warning={warning}>
      <input
        type="text"
        value={draft}
        onChange={(e) => handleChange(e.target.value)}
        placeholder={placeholder}
        disabled={disabled}
        className={INPUT_CLASS}
      />
    </VpConfigFieldShell>
  );
}
