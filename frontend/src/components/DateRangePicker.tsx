interface DateRangePickerProps {
  from: string;
  to: string;
  onChange: (from: string, to: string) => void;
}

export function DateRangePicker({ from, to, onChange }: DateRangePickerProps) {
  const inputClass = "flex-1 min-w-0 w-0 border border-slate-200 rounded-md px-2 py-1.5 text-sm bg-slate-50";
  return (
    <div className="flex items-center gap-1.5 min-w-0 w-full">
      <input
        type="date"
        value={from}
        onChange={(e) => onChange(e.target.value, to)}
        className={inputClass}
      />
      <span className="text-slate-400 text-xs shrink-0">~</span>
      <input
        type="date"
        value={to}
        onChange={(e) => onChange(from, e.target.value)}
        className={inputClass}
      />
    </div>
  );
}

export function defaultDateRange(days = 7): { from: string; to: string } {
  const to = new Date();
  const from = new Date();
  from.setDate(from.getDate() - days);
  return {
    from: from.toISOString().slice(0, 10),
    to: to.toISOString().slice(0, 10),
  };
}
