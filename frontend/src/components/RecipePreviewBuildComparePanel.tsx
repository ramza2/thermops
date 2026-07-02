import type { RecipePreviewBuildCompareResponse } from "@/types/featureRecipes";
import {
  COMPARE_HELP_NOTE,
  COMPARE_LIMITED_NOTE,
  LAG_ROLLING_COMPARE_NOTE,
  formatCompareSummary,
} from "@/utils/featureRecipeFormat";
import { DataTable } from "@/components/DataTable";

interface Props {
  result: RecipePreviewBuildCompareResponse | null;
  loading?: boolean;
  error?: string;
}

export function RecipePreviewBuildComparePanel({ result, loading, error }: Props) {
  if (loading) {
    return <p className="text-xs text-slate-500">Preview/Build 비교 실행 중...</p>;
  }
  if (error) {
    return <p className="text-xs text-red-700 bg-red-50 border border-red-200 rounded p-2">{error}</p>;
  }
  if (!result) return null;

  const summary = result.summary;

  return (
    <div className="space-y-3 text-xs">
      <div className="text-slate-600 bg-slate-50 border border-slate-200 rounded p-2 space-y-1">
        <p>{COMPARE_HELP_NOTE}</p>
        <p>{COMPARE_LIMITED_NOTE}</p>
        <p>{LAG_ROLLING_COMPARE_NOTE}</p>
      </div>

      <div className="flex flex-wrap gap-2 items-center">
        <span
          className={`px-2 py-0.5 rounded border ${
            result.comparable
              ? "bg-emerald-50 text-emerald-800 border-emerald-200"
              : "bg-amber-50 text-amber-800 border-amber-200"
          }`}
        >
          {result.comparable ? "비교 가능" : "비교 제한"}
        </span>
        <span className="text-slate-600">정책: {result.comparison_policy}</span>
        {result.dataset_version_id && (
          <span className="font-mono text-slate-500">{result.dataset_version_id}</span>
        )}
      </div>

      <p className="text-slate-700">
        <strong>{formatCompareSummary(summary)}</strong>
      </p>

      {(result.warnings?.length ?? 0) > 0 && (
        <ul className="text-amber-800 bg-amber-50 border border-amber-200 rounded p-2 space-y-1">
          {result.warnings.map((w) => (
            <li key={w}>{w}</li>
          ))}
          {!result.comparable && (
            <li>대안: Build 샘플만 확인하거나 Recipe Preview를 다시 실행하세요.</li>
          )}
        </ul>
      )}

      {result.items.length > 0 && (
        <DataTable
          columns={[
            { key: "entity_key", header: "Entity" },
            {
              key: "time_key",
              header: "Time",
              render: (r) => String(r.time_key ?? "-").slice(0, 19),
            },
            {
              key: "preview_value",
              header: "Preview",
              render: (r) => formatCellValue(r.preview_value),
            },
            {
              key: "build_value",
              header: "Build",
              render: (r) => formatCellValue(r.build_value),
            },
            {
              key: "diff",
              header: "diff",
              render: (r) => {
                const d = r.diff as number | null;
                if (d == null) return "-";
                return d.toFixed(6);
              },
            },
            {
              key: "match",
              header: "일치",
              render: (r) => (r.match ? "✓" : "✗"),
            },
          ]}
          data={result.items.slice(0, 50) as unknown as Record<string, unknown>[]}
        />
      )}
    </div>
  );
}

function formatCellValue(value: unknown): string {
  if (value == null) return "null";
  if (typeof value === "number") {
    return Number.isInteger(value) ? String(value) : value.toFixed(4);
  }
  return String(value);
}
