import { useCallback, useEffect, useState } from "react";
import { ChevronDown, ChevronRight, Play, RefreshCw } from "lucide-react";
import { fetchApi } from "@/api/client";
import { getFeatureQualityRun, getFeatureQualityRuns, runFeatureQualityCheck } from "@/api/featureQuality";
import { Button } from "@/components/Button";
import { DataTable } from "@/components/DataTable";
import { SelectInput } from "@/components/SearchPanel";
import { StatusBadge } from "@/components/StatusBadge";
import type { FeatureQualityFeatureResult, FeatureQualityRun } from "@/types/featureQuality";
import type { FeatureRegistrationStatus } from "@/types/featureRegistration";
import {
  FEATURE_QUALITY_REGISTRATION_HINT,
  LEGACY_REPLACE_AFTER_HINT,
  registrationStatusClass,
  registrationStatusLabelExtended,
} from "@/utils/featureRegistrationFormat";
import type { FeatureDatasetRange } from "@/utils/predictionPeriod";
import {
  formatNumber,
  formatPercent,
  formatQualityStatusLabel,
  formatScore,
} from "@/utils/featureQualityFormat";
import { formatDateTimeShort } from "@/utils/featureRegistryFormat";

interface FeatureQualitySectionProps {
  featureSetId: string;
  datasetVersionId?: string | null;
  hasLegacyFeatures?: boolean;
}

export function FeatureQualitySection({
  featureSetId,
  datasetVersionId: propDsv,
  hasLegacyFeatures = false,
}: FeatureQualitySectionProps) {
  const [datasetVersionId, setDatasetVersionId] = useState(propDsv || "");
  const [runs, setRuns] = useState<FeatureQualityRun[]>([]);
  const [selectedRunId, setSelectedRunId] = useState("");
  const [detail, setDetail] = useState<FeatureQualityRun | null>(null);
  const [runsLoading, setRunsLoading] = useState(false);
  const [detailLoading, setDetailLoading] = useState(false);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState("");
  const [issuesOpen, setIssuesOpen] = useState(false);
  const [jsonOpen, setJsonOpen] = useState(false);

  const loadDatasetRange = useCallback(async () => {
    if (propDsv) {
      setDatasetVersionId(propDsv);
      return propDsv;
    }
    try {
      const range = await fetchApi<FeatureDatasetRange>(
        `/feature-sets/${encodeURIComponent(featureSetId)}/dataset-range`,
      );
      const dsv = range.dataset_version_id || "";
      setDatasetVersionId(dsv);
      return dsv;
    } catch {
      setDatasetVersionId("");
      return "";
    }
  }, [featureSetId, propDsv]);

  const loadRuns = useCallback(async () => {
    setRunsLoading(true);
    setError("");
    try {
      const res = await getFeatureQualityRuns({
        feature_set_id: featureSetId,
        limit: 10,
        offset: 0,
        include_summary: true,
      });
      setRuns(res.items || []);
      return res.items || [];
    } catch {
      setError("Feature 품질 점검 이력을 불러오지 못했습니다.");
      setRuns([]);
      return [];
    } finally {
      setRunsLoading(false);
    }
  }, [featureSetId]);

  const loadDetail = useCallback(async (runId: string) => {
    if (!runId) {
      setDetail(null);
      return;
    }
    setDetailLoading(true);
    try {
      const res = await getFeatureQualityRun(runId);
      setDetail(res);
    } catch {
      setDetail(null);
    } finally {
      setDetailLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadDatasetRange();
    void loadRuns();
  }, [loadDatasetRange, loadRuns]);

  useEffect(() => {
    if (propDsv) setDatasetVersionId(propDsv);
  }, [propDsv]);

  useEffect(() => {
    if (selectedRunId) void loadDetail(selectedRunId);
  }, [selectedRunId, loadDetail]);

  useEffect(() => {
    if (runs.length && !selectedRunId) {
      setSelectedRunId(runs[0].run_id);
    }
  }, [runs, selectedRunId]);

  const handleRun = async () => {
    const dsv = datasetVersionId || (await loadDatasetRange());
    if (!dsv) {
      setError("아직 Feature Dataset이 없습니다. 먼저 Feature 생성 작업을 실행하세요.");
      return;
    }
    setRunning(true);
    setError("");
    try {
      const res = await runFeatureQualityCheck({
        feature_set_id: featureSetId,
        dataset_version_id: dsv,
      });
      setSelectedRunId(res.run_id);
      setDetail(res);
      await loadRuns();
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Feature 품질 점검 실행에 실패했습니다.";
      setError(msg);
    } finally {
      setRunning(false);
    }
  };

  const rs = detail?.result_summary;
  const featureRows = rs?.features ?? [];
  const issueSamples = rs?.issue_samples ?? [];
  const agg = rs?.summary ?? detail?.summary;
  const displayStatus = rs?.status ?? detail?.status ?? "-";
  const displayScore = rs?.score ?? detail?.score;

  return (
    <div className="bg-white rounded-lg border border-slate-200 p-4 mt-6 space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 className="text-sm font-semibold text-slate-800">Feature 품질 검증</h3>
          <p className="text-xs text-slate-500 mt-1 max-w-2xl">
            Feature 생성 결과(feature_json)가 학습·예측에 적합한지 점검합니다.
            원천 데이터 품질 점검과는 별도로, Feature 값의 누락·범위·이상치·분포를 확인합니다.
          </p>
          <p className="text-xs text-amber-700 mt-2 max-w-2xl">{FEATURE_QUALITY_REGISTRATION_HINT}</p>
          {hasLegacyFeatures && (
            <p className="text-xs text-orange-700 mt-1 max-w-2xl">{LEGACY_REPLACE_AFTER_HINT}</p>
          )}
        </div>
        <div className="flex gap-2">
          <Button
            variant="secondary"
            icon={<RefreshCw className="w-4 h-4" />}
            onClick={() => { void loadRuns(); void loadDatasetRange(); }}
            disabled={runsLoading}
          >
            새로고침
          </Button>
          <Button
            icon={<Play className="w-4 h-4" />}
            onClick={() => void handleRun()}
            disabled={running || !datasetVersionId}
          >
            {running ? "점검 중..." : "Feature 품질 점검 실행"}
          </Button>
        </div>
      </div>

      <div className="text-xs text-slate-600 space-y-1">
        <p>
          <span className="text-slate-500">dataset_version_id:</span>{" "}
          {datasetVersionId ? (
            <span className="font-mono">{datasetVersionId}</span>
          ) : (
            <span className="text-amber-700">없음 — Feature 생성 후 점검할 수 있습니다.</span>
          )}
        </p>
      </div>

      {error && <p className="text-xs text-red-600">{error}</p>}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div>
          <label className="block text-xs text-slate-500 mb-1">최근 점검 이력</label>
          <SelectInput
            value={selectedRunId}
            onChange={setSelectedRunId}
            options={runs.map((r) => ({
              value: r.run_id,
              label: `${r.run_id} · ${formatQualityStatusLabel(r.status)} · ${formatScore(r.score)}점`,
            }))}
          />
        </div>
      </div>

      {detailLoading && <p className="text-xs text-slate-500">상세 결과 불러오는 중...</p>}

      {detail && !detailLoading && (
        <>
          <div className="flex flex-wrap items-center gap-3 text-sm">
            <StatusBadge status={displayStatus} />
            <span>점수 <strong>{formatScore(displayScore)}</strong></span>
            <span className="text-slate-500">row {detail.row_count?.toLocaleString() ?? "-"}</span>
            <span className="text-slate-500">feature {detail.feature_count ?? "-"}</span>
            {rs?.site_count != null && (
              <span className="text-slate-500">site {rs.site_count}</span>
            )}
          </div>

          {rs?.time_range && (
            <p className="text-xs text-slate-500">
              기간: {formatDateTimeShort(rs.time_range.min_feature_at)} ~{" "}
              {formatDateTimeShort(rs.time_range.max_feature_at)}
            </p>
          )}

          {agg && (
            <div className="grid grid-cols-2 sm:grid-cols-5 gap-2 text-xs">
              <Metric label="key 누락 row" value={agg.missing_key_count} />
              <Metric label="null" value={agg.null_count} />
              <Metric label="invalid" value={agg.invalid_count} />
              <Metric label="범위 위반" value={agg.range_violation_count} />
              <Metric label="이상치" value={agg.outlier_count} />
            </div>
          )}

          {(rs?.registration_summary || agg?.catalog_only_feature_count != null) && (
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs">
              <Metric
                label="카탈로그 전용"
                value={rs?.registration_summary?.catalog_only_feature_count ?? agg?.catalog_only_feature_count}
              />
              <Metric
                label="레거시 별칭"
                value={rs?.registration_summary?.legacy_alias_feature_count ?? agg?.legacy_alias_feature_count}
              />
              <Metric
                label="비계산 Feature"
                value={rs?.registration_summary?.non_computable_feature_count ?? agg?.non_computable_feature_count}
              />
              <Metric
                label="Registry 미등록"
                value={rs?.registration_summary?.registry_missing_feature_count ?? agg?.registry_missing_feature_count}
              />
            </div>
          )}

          {rs?.build_coverage && (rs.build_coverage.missing_feature_count ?? 0) > 0 && (
            <div className="text-xs text-amber-800 bg-amber-50 border border-amber-200 rounded p-2">
              Feature Build 기준 미생성 Feature {rs.build_coverage.missing_feature_count}건
              {(rs.build_coverage.catalog_only_features?.length ?? 0) > 0 && (
                <span> · 카탈로그 전용: {rs.build_coverage.catalog_only_features?.join(", ")}</span>
              )}
              {(rs.build_coverage.legacy_alias_features?.length ?? 0) > 0 && (
                <span> · 레거시: {rs.build_coverage.legacy_alias_features?.join(", ")}</span>
              )}
            </div>
          )}

          {(detail.errors?.length ?? rs?.errors?.length) ? (
            <div className="text-xs text-red-700 bg-red-50 rounded p-2">
              {(detail.errors ?? rs?.errors ?? []).map((e) => (
                <p key={e}>{e}</p>
              ))}
            </div>
          ) : null}

          {(detail.warnings?.length ?? rs?.warnings?.length) ? (
            <div className="text-xs text-amber-800 bg-amber-50 rounded p-2">
              {(detail.warnings ?? rs?.warnings ?? []).map((w) => (
                <p key={w}>{w}</p>
              ))}
            </div>
          ) : null}

          <DataTable
            columns={[
              { key: "feature_name", header: "Feature명" },
              {
                key: "registration_status",
                header: "등록 상태",
                render: (r) => (
                  <QualityRegistrationBadge row={r as unknown as FeatureQualityFeatureResult} />
                ),
              },
              {
                key: "status",
                header: "품질 상태",
                render: (r) => <StatusBadge status={String(r.status)} />,
              },
              { key: "count", header: "count" },
              {
                key: "null_ratio",
                header: "null %",
                render: (r) => formatPercent(Number(r.null_ratio)),
              },
              { key: "invalid_count", header: "invalid" },
              { key: "range_violation_count", header: "범위" },
              { key: "outlier_count", header: "outlier" },
              {
                key: "min",
                header: "min",
                render: (r) => formatNumber(Number(r.min)),
              },
              {
                key: "mean",
                header: "mean",
                render: (r) => formatNumber(Number(r.mean)),
              },
              {
                key: "p50",
                header: "p50",
                render: (r) => formatNumber(Number(r.p50)),
              },
              {
                key: "max",
                header: "max",
                render: (r) => formatNumber(Number(r.max)),
              },
              {
                key: "std",
                header: "std",
                render: (r) => formatNumber(Number(r.std)),
              },
            ]}
            data={featureRows as unknown as Record<string, unknown>[]}
          />

          <button
            type="button"
            className="flex items-center gap-1 text-xs text-slate-600 hover:text-slate-900"
            onClick={() => setIssuesOpen((v) => !v)}
          >
            {issuesOpen ? <ChevronDown className="w-3 h-3" /> : <ChevronRight className="w-3 h-3" />}
            이슈 샘플 ({issueSamples.length}건)
          </button>
          {issuesOpen && issueSamples.length > 0 && (
            <div className="text-xs overflow-x-auto">
              <table className="w-full border-collapse">
                <thead>
                  <tr className="text-left text-slate-500 border-b">
                    <th className="py-1 pr-2">Feature</th>
                    <th className="py-1 pr-2">등록 상태</th>
                    <th className="py-1 pr-2">유형</th>
                    <th className="py-1 pr-2">site</th>
                    <th className="py-1 pr-2">시각</th>
                    <th className="py-1 pr-2">값</th>
                    <th className="py-1">메시지</th>
                  </tr>
                </thead>
                <tbody>
                  {(issueSamples as unknown as Record<string, unknown>[]).map((s, i) => (
                    <tr key={i} className="border-b border-slate-100">
                      <td className="py-1 pr-2 font-mono">{String(s.feature_name)}</td>
                      <td className="py-1 pr-2">
                        {s.registration_status ? (
                          <span
                            className={`inline-flex text-[10px] px-1 rounded border ${registrationStatusClass(String(s.registration_status) as FeatureRegistrationStatus)}`}
                          >
                            {registrationStatusLabelExtended({
                              registration_status: String(s.registration_status),
                              recommended_name: s.recommended_name as string | null,
                            })}
                          </span>
                        ) : (
                          "-"
                        )}
                      </td>
                      <td className="py-1 pr-2">{String(s.issue_type)}</td>
                      <td className="py-1 pr-2">{String(s.site_id)}</td>
                      <td className="py-1 pr-2">{formatDateTimeShort(s.feature_at as string)}</td>
                      <td className="py-1 pr-2">{String(s.value ?? "-")}</td>
                      <td className="py-1">
                        {String(s.registration_message || s.message)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          <button
            type="button"
            className="flex items-center gap-1 text-xs text-slate-600 hover:text-slate-900"
            onClick={() => setJsonOpen((v) => !v)}
          >
            {jsonOpen ? <ChevronDown className="w-3 h-3" /> : <ChevronRight className="w-3 h-3" />}
            원본 JSON
          </button>
          {jsonOpen && (
            <pre className="text-xs bg-slate-50 p-3 rounded overflow-auto max-h-64">
              {JSON.stringify(detail.result_summary ?? detail, null, 2)}
            </pre>
          )}
        </>
      )}
    </div>
  );
}

function Metric({ label, value }: { label: string; value?: number | null }) {
  return (
    <div className="bg-slate-50 rounded p-2">
      <p className="text-slate-500">{label}</p>
      <p className="font-medium text-slate-800">{value?.toLocaleString() ?? "-"}</p>
    </div>
  );
}

function QualityRegistrationBadge({ row }: { row: FeatureQualityFeatureResult }) {
  const rs = row.registration_status;
  if (!rs) return <span className="text-xs text-slate-400">-</span>;
  const warn = rs === "CATALOG_ONLY" || rs === "LEGACY_ALIAS" || row.computable === false;
  return (
    <span
      className={`inline-flex text-[11px] px-1.5 py-0.5 rounded border ${registrationStatusClass(rs as FeatureRegistrationStatus)} ${warn ? "font-medium" : ""}`}
      title={row.registration_message || undefined}
    >
      {registrationStatusLabelExtended({
        registration_status: rs,
        recommended_name: row.recommended_name,
      })}
    </span>
  );
}
