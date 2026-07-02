import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ChevronDown, ChevronRight, RefreshCw } from "lucide-react";
import { getFeatureBuildJobLineage, getFeatureLineageByDatasetVersion } from "@/api/featureRegistry";
import { getFeatureBuildJobs, pickDefaultBuildJob } from "@/api/featureBuildJobs";
import { fetchApi } from "@/api/client";
import { Button } from "@/components/Button";
import { DataTable } from "@/components/DataTable";
import { SelectInput } from "@/components/SearchPanel";
import { StatusBadge } from "@/components/StatusBadge";
import type {
  FeatureBuildJobSummary,
  FeatureBuildResult,
  FeatureLineageItem,
} from "@/types/featureRegistry";
import type { FeatureDatasetRange } from "@/utils/predictionPeriod";
import { CalcMemoText } from "@/components/FeatureRegistryPanel";
import {
  formatBuildJobOptionLabel,
  formatBuildJobStatusLabel,
  formatCalcMethod,
  formatDateTimeShort,
  formatLeakageSafe,
  formatLineageCountLabel,
  formatList,
  formatLookbackHours,
} from "@/utils/featureRegistryFormat";

interface FeatureLineageSectionProps {
  featureSetId: string;
  buildResult?: FeatureBuildResult | null;
}

export function FeatureLineageSection({ featureSetId, buildResult }: FeatureLineageSectionProps) {
  const [buildJobs, setBuildJobs] = useState<FeatureBuildJobSummary[]>([]);
  const [buildJobsError, setBuildJobsError] = useState("");
  const [buildJobsLoading, setBuildJobsLoading] = useState(false);
  const [selectedJobId, setSelectedJobId] = useState<string>("");
  const [datasetRange, setDatasetRange] = useState<FeatureDatasetRange | null>(null);
  const [datasetVersionId, setDatasetVersionId] = useState("");
  const [manualJobId, setManualJobId] = useState("");
  const [advancedOpen, setAdvancedOpen] = useState(false);
  const [items, setItems] = useState<FeatureLineageItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [loadError, setLoadError] = useState("");
  const [expandedId, setExpandedId] = useState<number | null>(null);

  const selectedJob = buildJobs.find((j) => j.job_id === selectedJobId) ?? null;

  const loadBuildJobs = useCallback(async () => {
    setBuildJobsLoading(true);
    setBuildJobsError("");
    try {
      const res = await getFeatureBuildJobs({ feature_set_id: featureSetId, limit: 10, offset: 0 });
      setBuildJobs(res.items || []);
      return res.items || [];
    } catch {
      setBuildJobsError("Feature Build Job 이력을 불러오지 못했습니다. 고급 조회를 사용하세요.");
      setBuildJobs([]);
      return [];
    } finally {
      setBuildJobsLoading(false);
    }
  }, [featureSetId]);

  const loadDatasetRange = useCallback(async () => {
    try {
      const range = await fetchApi<FeatureDatasetRange>(
        `/feature-sets/${encodeURIComponent(featureSetId)}/dataset-range`,
      );
      setDatasetRange(range);
      return range;
    } catch {
      setDatasetRange(null);
      return null;
    }
  }, [featureSetId]);

  const loadLineageByJob = useCallback(async (jobId: string) => {
    if (!jobId) {
      setItems([]);
      return;
    }
    setLoading(true);
    setLoadError("");
    try {
      const res = await getFeatureBuildJobLineage(jobId);
      setItems(res.items || []);
      if (res.dataset_version_id) setDatasetVersionId(res.dataset_version_id);
    } catch {
      setLoadError("Lineage를 불러오지 못했습니다.");
      setItems([]);
    } finally {
      setLoading(false);
    }
  }, []);

  const loadLineageByDataset = useCallback(async (dsv: string) => {
    if (!dsv) {
      setItems([]);
      return;
    }
    setLoading(true);
    setLoadError("");
    try {
      const res = await getFeatureLineageByDatasetVersion(dsv);
      setItems(res.items || []);
    } catch {
      setLoadError("Lineage를 불러오지 못했습니다.");
      setItems([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!featureSetId) return;

    const init = async () => {
      const [jobs, range] = await Promise.all([loadBuildJobs(), loadDatasetRange()]);

      if (buildResult?.job_id) {
        setSelectedJobId(buildResult.job_id);
        if (buildResult.dataset_version_id) setDatasetVersionId(buildResult.dataset_version_id);
        await loadLineageByJob(buildResult.job_id);
        return;
      }

      const defaultJob = pickDefaultBuildJob(jobs);
      if (defaultJob) {
        setSelectedJobId(defaultJob.job_id);
        if (defaultJob.dataset_version_id) setDatasetVersionId(defaultJob.dataset_version_id);
        await loadLineageByJob(defaultJob.job_id);
        return;
      }

      if (range?.dataset_version_id) {
        setDatasetVersionId(range.dataset_version_id);
        await loadLineageByDataset(range.dataset_version_id);
      }
    };

    init();
  }, [
    featureSetId,
    buildResult?.job_id,
    buildResult?.dataset_version_id,
    loadBuildJobs,
    loadDatasetRange,
    loadLineageByJob,
    loadLineageByDataset,
  ]);

  const handleSelectJob = async (jobId: string) => {
    setSelectedJobId(jobId);
    const job = buildJobs.find((j) => j.job_id === jobId);
    if (job?.dataset_version_id) setDatasetVersionId(job.dataset_version_id);
    await loadLineageByJob(jobId);
  };

  const handleRefresh = async () => {
    const jobs = await loadBuildJobs();
    if (selectedJobId) {
      await loadLineageByJob(selectedJobId);
      return;
    }
    const defaultJob = pickDefaultBuildJob(jobs);
    if (defaultJob) {
      setSelectedJobId(defaultJob.job_id);
      await loadLineageByJob(defaultJob.job_id);
    } else if (datasetVersionId) {
      await loadLineageByDataset(datasetVersionId);
    }
  };

  const lineageError = selectedJob?.lineage_error
    ?? buildResult?.lineage_error
    ?? buildResult?.result_summary?.lineage_error
    ?? null;

  return (
    <div className="bg-white rounded-lg border border-slate-200 p-4 mt-6">
      <div className="flex flex-wrap items-start justify-between gap-3 mb-3">
        <div>
          <h3 className="text-sm font-semibold text-slate-800">Feature Lineage</h3>
          <p className="text-xs text-slate-500 mt-1 max-w-2xl">
            Feature 생성 결과(dataset_version_id) 기준으로 각 Feature가 어떤 원천 데이터와 계산 방식으로
            만들어졌는지 보여줍니다. 최근 Feature Build 이력에서 Job을 선택해 Lineage를 조회할 수 있습니다.
          </p>
        </div>
        <Button
          variant="secondary"
          icon={<RefreshCw className="w-3.5 h-3.5" />}
          onClick={handleRefresh}
          disabled={loading || buildJobsLoading}
        >
          새로고침
        </Button>
      </div>

      <div className="mb-4">
        <h4 className="text-xs font-semibold text-slate-700 mb-2">최근 Feature Build 이력</h4>
        {buildJobsError && (
          <div className="text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded p-2 mb-2">
            {buildJobsError}
          </div>
        )}
        {buildJobsLoading && buildJobs.length === 0 && (
          <p className="text-xs text-slate-400">Build Job 이력 로딩 중...</p>
        )}
        {!buildJobsLoading && buildJobs.length === 0 && !buildJobsError && (
          <p className="text-xs text-slate-500 bg-slate-50 border border-slate-200 rounded p-3">
            아직 Feature Build 이력이 없습니다. 상단 <strong>Feature 생성</strong>을 실행하세요.
          </p>
        )}
        {buildJobs.length > 0 && (
          <div className="space-y-2 mb-3">
            <label className="block text-xs text-slate-500">Lineage 조회 대상</label>
            <SelectInput
              value={selectedJobId}
              onChange={handleSelectJob}
              options={buildJobs.map((j) => ({
                value: j.job_id,
                label: formatBuildJobOptionLabel(j),
              }))}
            />
          </div>
        )}
        {buildJobs.length > 0 && (
          <div className="grid gap-2 sm:grid-cols-2">
            {buildJobs.slice(0, 4).map((job) => {
              const selected = job.job_id === selectedJobId;
              const statusClass =
                job.status === "FAILED"
                  ? "border-red-200 bg-red-50"
                  : job.status === "WARNING"
                    ? "border-amber-200 bg-amber-50"
                    : job.status === "RUNNING"
                      ? "border-blue-200 bg-blue-50"
                      : selected
                        ? "border-emerald-300 bg-emerald-50"
                        : "border-slate-200 bg-slate-50";
              return (
                <button
                  key={job.job_id}
                  type="button"
                  onClick={() => handleSelectJob(job.job_id)}
                  className={`text-left rounded-lg border p-3 text-xs transition-colors ${statusClass} ${
                    selected ? "ring-1 ring-emerald-400" : "hover:border-slate-300"
                  }`}
                >
                  <div className="flex items-center justify-between gap-2 mb-1">
                    <span className="font-medium text-slate-800">{formatDateTimeShort(job.started_at)}</span>
                    <StatusBadge status={job.status} />
                  </div>
                  <p className="text-slate-600">
                    {formatBuildJobStatusLabel(job.status)}
                    {selected && <span className="ml-2 text-emerald-700 font-medium">· 선택됨</span>}
                  </p>
                  <p className="font-mono text-[10px] text-slate-500 mt-1 truncate">
                    {job.dataset_version_id || "Dataset Version 없음"}
                  </p>
                  <p className="mt-1 text-slate-600">
                    Rows: {(job.row_count ?? job.inserted_count ?? 0).toLocaleString()}
                    {" · "}
                    {formatLineageCountLabel(job.lineage_count, job.lineage_error)}
                  </p>
                  {job.lineage_error && (
                    <p className="text-amber-800 mt-1">Lineage 저장 오류 있음</p>
                  )}
                </button>
              );
            })}
          </div>
        )}
      </div>

      <div className="mb-4 border border-slate-200 rounded-lg">
        <button
          type="button"
          className="w-full flex items-center gap-2 px-3 py-2 text-xs font-medium text-slate-600 hover:bg-slate-50"
          onClick={() => setAdvancedOpen((v) => !v)}
        >
          {advancedOpen ? <ChevronDown className="w-3.5 h-3.5" /> : <ChevronRight className="w-3.5 h-3.5" />}
          고급 조회 (Dataset Version / Build Job ID 직접 입력)
        </button>
        {advancedOpen && (
          <div className="px-3 pb-3 grid grid-cols-1 md:grid-cols-2 gap-3 border-t border-slate-100 pt-3">
            <div>
              <label className="block text-xs text-slate-500 mb-1">Dataset Version ID</label>
              <input
                className="w-full border border-slate-200 rounded px-2 py-1.5 text-xs font-mono"
                value={datasetVersionId}
                onChange={(e) => setDatasetVersionId(e.target.value)}
                placeholder={datasetRange?.dataset_version_id || "DSV-..."}
              />
              <Button
                variant="ghost"
                className="mt-1 text-xs"
                onClick={() => loadLineageByDataset(datasetVersionId)}
              >
                Dataset 기준 조회
              </Button>
            </div>
            <div>
              <label className="block text-xs text-slate-500 mb-1">Build Job ID</label>
              <input
                className="w-full border border-slate-200 rounded px-2 py-1.5 text-xs font-mono"
                value={manualJobId}
                onChange={(e) => setManualJobId(e.target.value)}
                placeholder="FBJ-..."
              />
              <Button
                variant="ghost"
                className="mt-1 text-xs"
                onClick={() => {
                  setSelectedJobId(manualJobId);
                  loadLineageByJob(manualJobId);
                }}
              >
                Job 기준 조회
              </Button>
            </div>
          </div>
        )}
      </div>

      {lineageError && (
        <div className="mb-3 text-xs text-amber-800 bg-amber-50 border border-amber-200 rounded p-3">
          <p className="font-medium">Lineage 저장 실패</p>
          <p className="mt-1">Feature 데이터는 생성되었지만 Lineage 저장 중 오류가 발생했습니다.</p>
          <p className="mt-1 font-mono text-[11px] break-all">{lineageError}</p>
        </div>
      )}

      {loadError && (
        <div className="mb-3 text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded p-2">
          {loadError}
        </div>
      )}

      {!loading && !loadError && items.length === 0 && (
        <div className="text-sm text-slate-500 bg-slate-50 border border-slate-200 rounded p-4">
          <p className="font-medium text-slate-700">선택한 Build Job에 Lineage가 없습니다.</p>
          <p className="text-xs mt-2">
            Feature 생성을 실행하거나 다른 Build Job을 선택하세요. FAILED·RUNNING 상태에서는 Lineage가 없을 수
            있습니다.
          </p>
        </div>
      )}

      {(loading || items.length > 0) && (
        <DataTable
          loading={loading}
          columns={[
            { key: "feature_name", header: "Feature명", width: "140px" },
            {
              key: "calc_method",
              header: "계산 방식",
              render: (r) => {
                const method = r.calc_method as string;
                const recipeMeta = (r.lineage_json as { recipe?: Record<string, unknown> } | undefined)?.recipe;
                return (
                  <div className="space-y-1">
                    <span
                      className={`inline-flex text-[10px] px-1 rounded border ${
                        method === "TEMPLATE"
                          ? "bg-violet-50 text-violet-800 border-violet-200"
                          : "bg-slate-50 text-slate-700 border-slate-200"
                      }`}
                    >
                      {formatCalcMethod(method)}
                    </span>
                    {method === "TEMPLATE" && recipeMeta && (
                      <div className="text-[10px] font-mono text-violet-700">
                        {String(recipeMeta.recipe_type)} · {String(recipeMeta.recipe_id)}
                      </div>
                    )}
                  </div>
                );
              },
            },
            {
              key: "calc_expression",
              header: "계산식 메모",
              render: (r) => <CalcMemoText expression={r.calc_expression as string | null} />,
            },
            {
              key: "source_tables",
              header: "원천 테이블",
              render: (r) => (
                <span className="text-xs font-mono">{formatList(r.source_tables as string[])}</span>
              ),
            },
            {
              key: "source_columns",
              header: "원천 컬럼",
              render: (r) => (
                <span className="text-xs font-mono">{formatList(r.source_columns as string[])}</span>
              ),
            },
            { key: "time_key", header: "기준 시각", render: (r) => String(r.time_key || "-") },
            {
              key: "partition_keys",
              header: "파티션",
              render: (r) => formatList(r.partition_keys as string[]),
            },
            {
              key: "lookback_hours",
              header: "Lookback",
              render: (r) => formatLookbackHours(r.lookback_hours as number | null),
            },
            {
              key: "leakage_safe",
              header: "누수 방지",
              render: (r) => formatLeakageSafe(r.leakage_safe as boolean | null),
            },
            {
              key: "build_start_at",
              header: "원천 데이터 기간",
              render: (r) => (
                <span className="text-xs whitespace-nowrap">
                  {formatDateTimeShort(r.build_start_at as string)}
                  {" ~ "}
                  {formatDateTimeShort(r.build_end_at as string)}
                </span>
              ),
            },
            {
              key: "created_at",
              header: "생성 시각",
              render: (r) => formatDateTimeShort(r.created_at as string),
            },
            {
              key: "json",
              header: "JSON",
              render: (r) => {
                const id = r.lineage_id as number;
                const open = expandedId === id;
                return (
                  <button
                    type="button"
                    className="text-xs text-blue-600 hover:underline inline-flex items-center gap-0.5"
                    onClick={(e) => {
                      e.stopPropagation();
                      setExpandedId(open ? null : id);
                    }}
                  >
                    {open ? <ChevronDown className="w-3 h-3" /> : <ChevronRight className="w-3 h-3" />}
                    {open ? "접기" : "보기"}
                  </button>
                );
              },
            },
          ]}
          data={items as unknown as Record<string, unknown>[]}
        />
      )}

      {expandedId != null && (
        <div className="mt-3 border border-slate-200 rounded bg-slate-50 p-3">
          {(() => {
            const row = items.find((i) => i.lineage_id === expandedId);
            const recipeMeta = (row?.lineage_json as { recipe?: Record<string, unknown> } | undefined)?.recipe;
            if (row?.calc_method === "TEMPLATE" && recipeMeta) {
              return (
                <div className="mb-3 text-xs text-violet-800 bg-violet-50 border border-violet-100 rounded p-2 space-y-1">
                  <p className="font-medium">TEMPLATE Recipe Lineage</p>
                  <p>recipe_id: <span className="font-mono">{String(recipeMeta.recipe_id)}</span></p>
                  <p>recipe_type: {String(recipeMeta.recipe_type)}</p>
                  <p>params: <span className="font-mono">{JSON.stringify(recipeMeta.params)}</span></p>
                  <p>entity_keys: {String((recipeMeta.entity_keys as string[])?.join(", ") || (row.partition_keys as string[])?.join(", "))}</p>
                  <p>time_key: {String(recipeMeta.time_key ?? row.time_key ?? "-")}</p>
                  <p>source_columns: {String((row.source_columns as string[])?.join(", ") || "-")}</p>
                  {recipeMeta.recipe_status != null && (
                    <p>source_recipe_status: {String(recipeMeta.recipe_status)}</p>
                  )}
                  {recipeMeta.recipe_id != null && (
                    <Link to={`/feature-recipes/${String(recipeMeta.recipe_id)}`} className="text-blue-600 hover:underline">
                      Recipe 상세 보기
                    </Link>
                  )}
                </div>
              );
            }
            return null;
          })()}
          <p className="text-xs font-medium text-slate-600 mb-2">Lineage JSON (lineage_id={expandedId})</p>
          <pre className="text-[11px] font-mono overflow-x-auto whitespace-pre-wrap break-all text-slate-700">
            {JSON.stringify(
              items.find((i) => i.lineage_id === expandedId)?.lineage_json
                ?? items.find((i) => i.lineage_id === expandedId),
              null,
              2,
            )}
          </pre>
        </div>
      )}
    </div>
  );
}
