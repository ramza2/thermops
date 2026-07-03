import { ReactNode } from "react";
import { Search } from "lucide-react";
import { Button } from "./Button";

interface Field {
  label: string;
  element: ReactNode;
  /** 기본 1. 조회 기간 등 넓은 필드는 2 이상 권장 */
  colSpan?: 1 | 2 | 3;
}

function colSpanClass(colSpan?: Field["colSpan"]): string {
  if (colSpan === 2) return "col-span-2";
  if (colSpan === 3) return "col-span-3";
  return "";
}

export function SearchPanel({ fields, onSearch, onReset }: { fields: Field[]; onSearch: () => void; onReset?: () => void }) {
  return (
    <div className="bg-white rounded-lg border border-slate-200 p-4 mb-4 shadow-sm">
      <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-3 items-end">
        {fields.map((f) => (
          <div key={f.label} className={`min-w-0 ${colSpanClass(f.colSpan)}`}>
            <label className="block text-xs text-slate-500 mb-1">{f.label}</label>
            {f.element}
          </div>
        ))}
        <div className="flex gap-2">
          <Button icon={<Search className="w-4 h-4" />} onClick={onSearch}>조회</Button>
          {onReset && <Button variant="secondary" onClick={onReset}>초기화</Button>}
        </div>
      </div>
    </div>
  );
}

export function SelectInput({ value, onChange, options }: { value: string; onChange: (v: string) => void; options: { value: string; label: string }[] }) {
  return (
    <select value={value} onChange={(e) => onChange(e.target.value)} className="w-full border border-slate-200 rounded-md px-2 py-1.5 text-sm bg-slate-50">
      {options.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
    </select>
  );
}

export function TextInput({
  value,
  onChange,
  placeholder,
  list,
}: {
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
  list?: string;
}) {
  return (
    <input
      value={value}
      onChange={(e) => onChange(e.target.value)}
      placeholder={placeholder}
      list={list}
      className="w-full border border-slate-200 rounded-md px-2 py-1.5 text-sm bg-slate-50"
    />
  );
}
