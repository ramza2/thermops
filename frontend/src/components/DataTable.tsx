import { ReactNode } from "react";

export interface Column<T> {
  key: string;
  header: string;
  render?: (row: T) => ReactNode;
  width?: string;
}

interface DataTableProps<T> {
  columns: Column<T>[];
  data: T[];
  onRowClick?: (row: T) => void;
  loading?: boolean;
}

export function DataTable<T extends Record<string, unknown>>({ columns, data, onRowClick, loading }: DataTableProps<T>) {
  if (loading) {
    return <div className="bg-white rounded-lg border p-8 text-center text-slate-400">로딩 중...</div>;
  }
  if (!data.length) {
    return <div className="bg-white rounded-lg border p-8 text-center text-slate-400">데이터가 없습니다.</div>;
  }
  return (
    <div className="bg-white rounded-lg border border-slate-200 overflow-hidden shadow-sm">
      <table className="w-full text-sm">
        <thead className="bg-slate-50 border-b">
          <tr>
            {columns.map((c) => (
              <th key={c.key} className="px-4 py-2.5 text-left text-xs font-semibold text-slate-500 uppercase" style={{ width: c.width }}>{c.header}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.map((row, i) => (
            <tr key={i} onClick={() => onRowClick?.(row)} className={`border-b last:border-0 ${onRowClick ? "cursor-pointer hover:bg-blue-50" : ""}`}>
              {columns.map((c) => (
                <td key={c.key} className="px-4 py-2.5 text-slate-700">
                  {c.render ? c.render(row) : String(row[c.key] ?? "")}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
