import { useEffect, useState } from "react";
import { VpConfigFieldShell } from "@/components/visualPipeline/config/VpConfigFieldShell";

const JSON_WARNING =
  "JSON 형식이 올바르지 않습니다. 저장은 가능하지만 S5-5 검증에서 오류가 될 수 있습니다.";

function valueToDraft(value: unknown): string {
  if (value === undefined || value === null) return "";
  if (typeof value === "object") {
    try {
      return JSON.stringify(value, null, 2);
    } catch {
      return "";
    }
  }
  return String(value);
}

interface VpJsonTextareaFieldProps {
  fieldKey: string;
  label: string;
  value: unknown;
  placeholder?: string;
  help?: string;
  advanced?: boolean;
  disabled?: boolean;
  warning?: string;
  onChange: (patch: Record<string, unknown>) => void;
}

export function VpJsonTextareaField({
  fieldKey,
  label,
  value,
  placeholder,
  help,
  advanced,
  disabled,
  warning,
  onChange,
}: VpJsonTextareaFieldProps) {
  const [draft, setDraft] = useState(() => valueToDraft(value));
  const [parseWarning, setParseWarning] = useState<string | undefined>();

  useEffect(() => {
    setDraft(valueToDraft(value));
    setParseWarning(undefined);
  }, [value, fieldKey]);

  const handleChange = (text: string) => {
    setDraft(text);
    const trimmed = text.trim();
    if (trimmed === "") {
      setParseWarning(undefined);
      onChange({ [fieldKey]: undefined });
      return;
    }
    try {
      const parsed = JSON.parse(trimmed) as unknown;
      if (parsed === null || typeof parsed !== "object" || Array.isArray(parsed)) {
        setParseWarning(JSON_WARNING);
        return;
      }
      setParseWarning(undefined);
      onChange({ [fieldKey]: parsed });
    } catch {
      setParseWarning(JSON_WARNING);
    }
  };

  return (
    <VpConfigFieldShell
      fieldKey={fieldKey}
      label={advanced ? `${label} (advanced)` : label}
      help={help}
      warning={parseWarning || warning}
    >
      <textarea
        value={draft}
        onChange={(e) => handleChange(e.target.value)}
        placeholder={placeholder}
        disabled={disabled}
        rows={4}
        className="w-full px-2.5 py-2 text-[10px] font-mono border border-slate-300 rounded-md focus:outline-none focus:ring-1 focus:ring-blue-500 bg-white resize-y min-h-[72px] disabled:bg-slate-50 disabled:text-slate-400"
      />
    </VpConfigFieldShell>
  );
}
