import { useCallback, useEffect, useState } from "react";
import { ChevronDown, ChevronRight, RefreshCw } from "lucide-react";
import { getFeatureBuildJobLineage, getFeatureLineageByDatasetVersion } from "@/api/featureRegistry";
import { fetchApi } from "@/api/client";
import { Button } from "@/components/Button";
import { DataTable } from "@/components/DataTable";
import { SelectInput } from "@/components/SearchPanel";
import type { FeatureBuildResult, FeatureLineageItem } from "@/types/featureRegistry";
import type { FeatureDatasetRange } from "@/utils/predictionPeriod";
import {
  CalcMemoText,
} from "@/components/FeatureRegistryPanel";
import {
  formatCalcMethod,
  formatDateTimeShort,
  formatLeakageSafe,
  formatList,
  formatLookbackHours,
} from "@/utils/featureRegistryFormat";

type LineageSource = "dataset" | "job";

interface FeatureLineageSectionProps {
  featureSetId: string;
  buildResult?: FeatureBuildResult | null;
}

export function FeatureLineageSection({ featureSetId, buildResult }: FeatureLineageSectionProps) {
  const [datasetRange, setDatasetRange] = useState<FeatureDatasetRange | null>(null);
  const [source, setSource] = useState<LineageSource>("dataset");
  const [datasetVersionId, setDatasetVersionId] = useState("");
  const [jobId, setJobId] = useState("");
  const [items, setItems] = useState<FeatureLineageItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [loadError, setLoadError] = useState("");
  const [expandedId, setExpandedId] = useState<number | null>(null);

  const lineageError =
    buildResult?.lineage_error
    ?? buildResult?.result_summary?.lineage_error
    ?? null;

  const loadDatasetRange = useCallback(async () => {
    try {
      const range = await fetchApi<FeatureDatasetRange>(
        `/feature-sets/${encodeURIComponent(featureSetId)}/dataset-range`,
      );
      setDatasetRange(range);
      if (range.dataset_version_id) {
        setDatasetVersionId(range.dataset_version_id);
      }
      return range;
    } catch {
      setDatasetRange(null);
      return null;
    }
  }, [featureSetId]);

  const loadLineage = useCallback(async (src: LineageSource, dsv: string, jid: string) => {
    setLoading(true);
    setLoadError("");
    try {
      if (src === "job" && jid) {
        const res = await getFeatureBuildJobLineage(jid);
        setItems(res.items || []);
        if (res.dataset_version_id) setDatasetVersionId(res.dataset_version_id);
      } else if (dsv) {
        const res = await getFeatureLineageByDatasetVersion(dsv);
        setItems(res.items || []);
      } else {
        setItems([]);
      }
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
      const range = await loadDatasetRange();

      if (buildResult?.job_id) {
        setJobId(buildResult.job_id);
        if (buildResult.dataset_version_id) {
          setDatasetVersionId(buildResult.dataset_version_id);
        }
        setSource("job");
        await loadLineage("job", buildResult.dataset_version_id || "", buildResult.job_id);
        return;
      }

      if (range?.dataset_version_id) {
        setDatasetVersionId(range.dataset_version_id);
        setSource("dataset");
        await loadLineage("dataset", range.dataset_version_id, "");
      }
    };

    init();
  }, [featureSetId, buildResult?.job_id, buildResult?.dataset_version_id, loadDatasetRange, loadLineage]);

  const handleSourceChange = (next: string) => {
    const src = next as LineageSource;
    setSource(src);
    loadLineage(src, datasetVersionId, jobId);
  };

  const handleRefresh = () => {
    loadLineage(source, datasetVersionId, jobId);
  };

  const hasDataset = Boolean(datasetRange?.exists && datasetRange.dataset_version_id);
  const hasJob = Boolean(jobId);

  return (
    <div className="bg-white rounded-lg border border-slate-200 p-4 mt-6">
      <div className="flex flex-wrap items-start justify-between gap-3 mb-3">
        <div>
          <h3 className="text-sm font-semibold text-slate-800">Feature Lineage</h3>
          <p className="text-xs text-slate-500 mt-1 max-w-2xl">
            Feature 생성 결과(dataset_version_id) 기준으로 각 Feature가 어떤 원천 데이터와 계산 방식으로
            만들어졌는지 보여줍니다. 조회 전용 감사/추적 정보이며 편집할 수 없습니다.
          </p>
        </div>
        <Button
          variant="secondary"
          icon={<RefreshCw className="w-3.5 h-3.5" />}
          onClick={handleRefresh}
          disabled={loading}
        >
          새로고침
        </Button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mb-4 text-sm">
        <div>
          <label className="block text-xs text-slate-500 mb-1">조회 기준</label>
          <SelectInput
            value={source}
            onChange={handleSourceChange}
            options={[
              { value: "dataset", label: "Dataset Version (dataset_version_id)" },
              { value: "job", label: "Feature Build Job (job_id)" },
            ]}
          />
        </div>
        <div>
          <label className="block text-xs text-slate-500 mb-1">Dataset Version ID</label>
          <input
            className="w-full border border-slate-200 rounded px-2 py-1.5 text-xs font-mono"
            value={datasetVersionId}
            onChange={(e) => setDatasetVersionId(e.target.value)}
            onBlur={() => source === "dataset" && datasetVersionId && loadLineage("dataset", datasetVersionId, "")}
            placeholder={hasDataset ? datasetRange?.dataset_version_id || "" : "DSV-..."}
          />
        </div>
        <div>
          <label className="block text-xs text-slate-500 mb-1">Build Job ID</label>
          <input
            className="w-full border border-slate-200 rounded px-2 py-1.5 text-xs font-mono"
            value={jobId}
            onChange={(e) => setJobId(e.target.value)}
            onBlur={() => source === "job" && jobId && loadLineage("job", datasetVersionId, jobId)}
            placeholder={hasJob ? jobId : "FBJ-..."}
          />
        </div>
      </div>

      {buildResult && (
        <div className="mb-3 text-xs text-slate-600 bg-slate-50 border border-slate-200 rounded p-2 space-y-0.5">
          <p>
            <span className="text-slate-500">최근 Build:</span>{" "}
            <span className="font-mono">{buildResult.job_id}</span>
            {buildResult.dataset_version_id && (
              <>
                {" · "}
                <span className="font-mono">{buildResult.dataset_version_id}</span>
              </>
            )}
          </p>
          <p>
            <span className="text-slate-500">Lineage:</span>{" "}
            {(buildResult.lineage_count ?? buildResult.result_summary?.lineage_count ?? 0).toLocaleString()}건 저장
          </p>
        </div>
      )}

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
          <p className="font-medium text-slate-700">아직 이 Feature Set의 Lineage가 없습니다.</p>
          <p className="text-xs mt-2">
            상단의 <strong>Feature 생성</strong> 작업을 실행하면 dataset_version_id 기준으로 Lineage가 저장됩니다.
          </p>
          {!hasDataset && (
            <p className="text-xs mt-1 text-slate-400">
              현재 저장된 Feature Dataset이 없습니다. Feature 생성 후 다시 조회하세요.
            </p>
          )}
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
              render: (r) => formatCalcMethod(r.calc_method as string),
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
          <p className="text-xs font-medium text-slate-600 mb-2">Lineage JSON (lineage_id={expandedId})</p>
          <pre className="text-[11px] font-mono overflow-x-auto whitespace-pre-wrap break-all text-slate-700">
            {JSON.stringify(
              items.find((i) => i.lineage_id === expandedId)?.lineage_json ?? items.find((i) => i.lineage_id === expandedId),
              null,
              2,
            )}
          </pre>
        </div>
      )}
    </div>
  );
}