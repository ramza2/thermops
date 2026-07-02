import { useState } from "react";
import { Link } from "react-router-dom";
import { ChevronDown, ChevronRight, ExternalLink } from "lucide-react";
import type { FeatureBuildResult, FeatureBuildJobSummary } from "@/types/featureRegistry";
import {
  LEGACY_JOB_DIAGNOSTICS_NOTE,
  formatDiagnosticCode,
  formatNullRatio,
  getDiagnosticSeverityLabel,
  getRecipeBuildStatusBadgeClass,
  getRecipeBuildStatusLabel,
  mapTemplateFeatureStatusToBadge,
} from "@/utils/featureRecipeFormat";

interface TemplateFeatureStatus {
  feature_name?: string;
  recipe_id?: string;
  recipe_type?: string;
  status?: string;
  message?: string;
  null_ratio?: number;
  warning_codes?: string[];
  error_codes?: string[];
  source_columns?: string[];
}

interface TemplateDiagnostic {
  feature_name?: string;
  severity?: string;
  code?: string;
  message?: string;
}

interface Props {
  buildResult?: FeatureBuildResult | null;
  jobSummary?: FeatureBuildJobSummary | null;
  datasetVersionId?: string | null;
}

const LAG_ROLLING_NOTE =
  "LAG/ROLLING Feature의 초기 null은 이력 부족으로 발생할 수 있습니다.";
const TIME_GAP_NOTE =
  "time gap warning은 row step 기반 계산과 실제 시간 간격의 차이를 의미합니다.";

export function RecipeBuildDiagnosticsPanel({
  buildResult,
  jobSummary,
  datasetVersionId: propDsv,
}: Props) {
  const [open, setOpen] = useState(true);
  const [codesOpen, setCodesOpen] = useState(false);
  const rs = (buildResult?.result_summary ?? jobSummary?.result_summary) as
    | FeatureBuildResult["result_summary"]
    | undefined;

  const hasTemplateFields = Boolean(
    rs?.template_feature_count || rs?.template_generated_feature_count,
  );
  const hasLegacyOnly = !hasTemplateFields && Boolean(
    (rs?.template_recipe_features as string[] | undefined)?.length,
  );

  if (!hasTemplateFields && !hasLegacyOnly) {
    return null;
  }

  const counts = (rs?.template_build_status_counts || {}) as Record<string, number>;
  const byFeature = (rs?.template_build_status_by_feature || {}) as Record<string, TemplateFeatureStatus>;
  const diagnostics = (rs?.template_build_diagnostics || []) as TemplateDiagnostic[];
  const features = Object.values(byFeature);
  const dsv = propDsv
    ?? buildResult?.dataset_version_id
    ?? buildResult?.result_summary?.dataset_version_id
    ?? jobSummary?.dataset_version_id
    ?? null;
  const diagnosticsLimited = hasLegacyOnly || features.length === 0;

  return (
    <div className="mt-3 border border-violet-200 rounded-lg bg-violet-50/50 text-xs">
      <button
        type="button"
        className="w-full flex items-center gap-2 px-3 py-2 font-medium text-violet-900 hover:bg-violet-50"
        onClick={() => setOpen((v) => !v)}
      >
        {open ? <ChevronDown className="w-3.5 h-3.5" /> : <ChevronRight className="w-3.5 h-3.5" />}
        Recipe Engine Build 상세
      </button>
      {open && (
        <div className="px-3 pb-3 space-y-3 border-t border-violet-100">
          {diagnosticsLimited && (
            <p className="text-violet-800 bg-violet-100/80 border border-violet-200 rounded p-2 mt-2">
              {LEGACY_JOB_DIAGNOSTICS_NOTE}
            </p>
          )}

          {hasTemplateFields && (
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 pt-2">
              <StatCard label="생성" value={counts.generated ?? rs?.template_generated_feature_count ?? 0} tone="emerald" />
              <StatCard label="경고" value={counts.warning ?? 0} tone="amber" />
              <StatCard label="실패" value={counts.failed ?? 0} tone="red" />
              <StatCard label="미지원" value={counts.unsupported ?? 0} tone="slate" />
            </div>
          )}

          <p className="text-violet-800">{LAG_ROLLING_NOTE}</p>
          <p className="text-violet-700">{TIME_GAP_NOTE}</p>

          {features.length > 0 && (
            <div className="overflow-x-auto">
              <table className="w-full text-left border border-violet-100 rounded bg-white">
                <thead>
                  <tr className="text-[10px] text-slate-500 border-b">
                    <th className="p-2">Feature</th>
                    <th className="p-2">Type</th>
                    <th className="p-2">Status</th>
                    <th className="p-2">null%</th>
                    <th className="p-2">경고/오류</th>
                    <th className="p-2">액션</th>
                  </tr>
                </thead>
                <tbody>
                  {features.map((f) => {
                    const badge = mapTemplateFeatureStatusToBadge(f.status);
                    const codes = [...(f.warning_codes || []), ...(f.error_codes || [])];
                    return (
                      <tr key={f.feature_name} className="border-b border-slate-50">
                        <td className="p-2 font-mono">{f.feature_name}</td>
                        <td className="p-2">{f.recipe_type}</td>
                        <td className="p-2">
                          <span className={`inline-flex px-1 py-0.5 rounded border text-[10px] ${getRecipeBuildStatusBadgeClass(badge)}`}>
                            {f.status ?? getRecipeBuildStatusLabel(badge)}
                          </span>
                        </td>
                        <td className="p-2">{formatNullRatio(f.null_ratio)}</td>
                        <td className="p-2 text-[10px]" title={codes.map(formatDiagnosticCode).join(", ")}>
                          {codes.map(formatDiagnosticCode).join(", ") || "-"}
                        </td>
                        <td className="p-2 space-x-2 whitespace-nowrap">
                          {f.recipe_id && (
                            <Link to={`/feature-recipes/${f.recipe_id}`} className="text-blue-600 hover:underline">
                              Recipe
                            </Link>
                          )}
                          {f.recipe_id && dsv && (
                            <Link
                              to={`/feature-recipes/${f.recipe_id}?compare_dsv=${encodeURIComponent(dsv)}`}
                              className="text-violet-700 hover:underline"
                            >
                              비교
                            </Link>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}

          {diagnostics.length > 0 && (
            <div>
              <div className="font-medium text-slate-700 mb-1">진단</div>
              <ul className="space-y-1">
                {diagnostics.slice(0, 10).map((d, i) => (
                  <li
                    key={`${d.code}-${i}`}
                    className={`rounded px-2 py-1 ${d.severity === "ERROR" ? "bg-red-50 text-red-800" : "bg-amber-50 text-amber-800"}`}
                    title={formatDiagnosticCode(d.code)}
                  >
                    <span className="font-mono text-[10px]">
                      [{getDiagnosticSeverityLabel(d.severity)}] {d.code}
                    </span>
                    {d.feature_name && <span className="ml-1 font-mono">({d.feature_name})</span>}
                    {" — "}
                    {d.message}
                  </li>
                ))}
              </ul>
            </div>
          )}

          <button
            type="button"
            className="flex items-center gap-1 text-violet-800 hover:text-violet-950"
            onClick={() => setCodesOpen((v) => !v)}
          >
            {codesOpen ? <ChevronDown className="w-3 h-3" /> : <ChevronRight className="w-3 h-3" />}
            진단 코드 도움말
          </button>
          {codesOpen && (
            <ul className="text-[10px] text-slate-600 bg-white border border-violet-100 rounded p-2 space-y-0.5">
              {["INSUFFICIENT_HISTORY", "TIME_GAP_DETECTED", "LEAKAGE_RISK", "SOURCE_COLUMN_MISSING", "UNSUPPORTED_RECIPE_TYPE"].map((code) => (
                <li key={code}>
                  <span className="font-mono">{code}</span>: {formatDiagnosticCode(code)}
                </li>
              ))}
            </ul>
          )}

          {dsv && (
            <p className="text-slate-500 flex items-center gap-1">
              <ExternalLink className="w-3 h-3" />
              dataset_version_id: <span className="font-mono">{dsv}</span>
            </p>
          )}
        </div>
      )}
    </div>
  );
}

function StatCard({
  label,
  value,
  tone,
}: {
  label: string;
  value: number;
  tone: "emerald" | "amber" | "red" | "slate";
}) {
  const cls =
    tone === "emerald"
      ? "bg-emerald-50 border-emerald-200 text-emerald-800"
      : tone === "amber"
        ? "bg-amber-50 border-amber-200 text-amber-800"
        : tone === "red"
          ? "bg-red-50 border-red-200 text-red-800"
          : "bg-slate-50 border-slate-200 text-slate-700";
  return (
    <div className={`rounded border p-2 ${cls}`}>
      <div className="text-[10px] opacity-80">{label}</div>
      <div className="text-lg font-semibold">{value}</div>
    </div>
  );
}
