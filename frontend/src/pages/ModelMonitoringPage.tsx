import { useEffect, useState } from "react";
import { Line, LineChart, CartesianGrid, ResponsiveContainer, Tooltip, Legend, XAxis, YAxis } from "recharts";
import { fetchApi } from "@/api/client";
import { ChartCard } from "@/components/ChartCard";
import { MetricCard } from "@/components/MetricCard";
import { DataTable } from "@/components/DataTable";
import { DateRangePicker, defaultDateRange } from "@/components/DateRangePicker";
import { SearchPanel, SelectInput } from "@/components/SearchPanel";
import { EmptyState, LoadingState, ErrorState } from "@/components/Pagination";
import { PageHeader } from "@/layouts/MainLayout";
import { MENU_GROUPS, PAGE_DESCRIPTIONS, PAGE_TITLES } from "@/constants/displayLabels";
import {
  monitoringTrendChartTitle,
  normalizeTrendResponse,
  type TrendResponse,
} from "@/utils/trend";

interface PerformanceMetric {
  site_id: string;
  site_name: string;
  mape: number | null;
  mae: number | null;
  rmse: number | null;
  r2: number | null;
  sample_count: number | null;
  max_abs_error: number | null;
  eval_type: string | null;
}

interface PerformanceData {
  model_name: string;
  model_version: string;
  eval_type: string | null;
  period: { from: string; to: string };
  metrics: PerformanceMetric[];
}

interface Site {
  site_id: string;
  site_name: string;
}

interface ModelSummary {
  model_name: string;
  latest_version: string | null;
}

interface ModelVersion {
  model_version_id: string;
  model_name: string;
  version: string;
}

function buildTrendParams(
  dateRange: { from: string; to: string },
  filters: { site_id: string; model_name: string; model_version_id: string },
): Record<string, unknown> {
  const params: Record<string, unknown> = {
    start_at: `${dateRange.from}T00:00:00`,
    end_at: `${dateRange.to}T23:59:59`,
    limit: 500,
  };
  if (filters.site_id) params.site_id = filters.site_id;
  if (filters.model_version_id) params.model_version_id = filters.model_version_id;
  else if (filters.model_name) params.model_name = filters.model_name;
  return params;
}

export default function ModelMonitoringPage() {
  const [trendData, setTrendData] = useState<TrendResponse>({ data_source: "EMPTY", items: [], count: 0 });
  const [perf, setPerf] = useState<PerformanceData | null>(null);
  const [sites, setSites] = useState<Site[]>([]);
  const [models, setModels] = useState<ModelSummary[]>([]);
  const [versions, setVersions] = useState<ModelVersion[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [dateRange, setDateRange] = useState(defaultDateRange(7));
  const [filters, setFilters] = useState({ site_id: "", model_name: "", model_version_id: "" });

  useEffect(() => {
    Promise.all([
      fetchApi<Site[]>("/sites").catch(() => []),
      fetchApi<ModelSummary[]>("/models").catch(() => []),
    ]).then(([s, m]) => {
      setSites(s);
      setModels(m);
    });
  }, []);

  useEffect(() => {
    if (!filters.model_name) {
      setVersions([]);
      return;
    }
    fetchApi<ModelVersion[]>(`/models/${filters.model_name}/versions`)
      .then(setVersions)
      .catch(() => setVersions([]));
  }, [filters.model_name]);

  const load = async (range = dateRange, f = filters) => {
    setLoading(true);
    setError("");
    try {
      const trendParams = buildTrendParams(range, f);
      const perfParams: Record<string, unknown> = { eval_type: "PREDICTION_ACTUAL_MATCH" };
      if (f.site_id) perfParams.site_id = f.site_id;
      if (f.model_version_id) perfParams.model_version_id = f.model_version_id;
      else if (f.model_name) perfParams.model_name = f.model_name;

      const [tr, pm] = await Promise.all([
        fetchApi<unknown>("/dashboard/prediction-trend", trendParams),
        fetchApi<PerformanceData>("/performance-metrics", perfParams),
      ]);
      setTrendData(normalizeTrendResponse(tr));
      setPerf(pm);
      if (!f.model_name && pm?.model_name) {
        setFilters((prev) => ({ ...prev, model_name: pm.model_name }));
      }
    } catch {
      setError("모니터링 데이터를 불러오지 못했습니다.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const handleSearch = () => { load(dateRange, filters); };

  const handleReset = () => {
    const range = defaultDateRange(7);
    const resetFilters = { site_id: "", model_name: perf?.model_name ?? "", model_version_id: "" };
    setDateRange(range);
    setFilters(resetFilters);
    load(range, resetFilters);
  };

  if (loading && trendData.count === 0 && !perf && !error) return <LoadingState />;
  if (error && trendData.count === 0 && !perf) return <ErrorState message={error} onRetry={() => load()} />;

  const trend = trendData.items ?? [];
  const hasActual = trendData.data_source === "MATCHED" && trend.some((t) => t.actual != null);
  const metrics = perf?.metrics ?? [];
  const avgMape = metrics.length
    ? (metrics.reduce((s, m) => s + (m.mape ?? 0), 0) / metrics.length).toFixed(2)
    : "-";
  const avgMae = metrics.length
    ? (metrics.reduce((s, m) => s + (m.mae ?? 0), 0) / metrics.length).toFixed(2)
    : "-";
  const avgRmse = metrics.length
    ? (metrics.reduce((s, m) => s + (m.rmse ?? 0), 0) / metrics.length).toFixed(2)
    : "-";
  const avgR2 = metrics.filter((m) => m.r2 != null).length
    ? (metrics.reduce((s, m) => s + (m.r2 ?? 0), 0) / metrics.filter((m) => m.r2 != null).length).toFixed(3)
    : "-";
  const totalSamples = metrics.reduce((s, m) => s + (m.sample_count ?? 0), 0);

  const siteOptions = [{ value: "", label: "전체 지사" }, ...sites.map((s) => ({ value: s.site_id, label: s.site_name }))];
  const modelOptions = [{ value: "", label: "전체 모델" }, ...models.map((m) => ({ value: m.model_name, label: m.model_name }))];
  const versionOptions = [
    { value: "", label: "최신 버전" },
    ...versions.map((v) => ({ value: v.model_version_id, label: `v${v.version}` })),
  ];

  return (
    <div>
      <PageHeader
        title={PAGE_TITLES.modelMonitoring}
        description={PAGE_DESCRIPTIONS.modelMonitoring}
        breadcrumbs={[
          { label: MENU_GROUPS.operations, path: "/ops/pipeline-runs" },
          { label: "성능 모니터링" },
        ]}
      />

      <SearchPanel
        fields={[
          {
            label: "모니터링 기간",
            colSpan: 2,
            element: <DateRangePicker from={dateRange.from} to={dateRange.to} onChange={(from, to) => setDateRange({ from, to })} />,
          },
          {
            label: "지사",
            element: <SelectInput value={filters.site_id} onChange={(v) => setFilters((f) => ({ ...f, site_id: v }))} options={siteOptions} />,
          },
          {
            label: "모델",
            element: (
              <SelectInput
                value={filters.model_name}
                onChange={(v) => setFilters((f) => ({ ...f, model_name: v, model_version_id: "" }))}
                options={modelOptions}
              />
            ),
          },
          {
            label: "모델 버전",
            element: (
              <SelectInput
                value={filters.model_version_id}
                onChange={(v) => setFilters((f) => ({ ...f, model_version_id: v }))}
                options={versionOptions}
              />
            ),
          },
        ]}
        onSearch={handleSearch}
        onReset={handleReset}
      />

      <div className="grid grid-cols-2 lg:grid-cols-5 gap-4 mb-6">
        <MetricCard title="운영 모델" value={perf?.model_name ?? "-"} subtitle={`v${perf?.model_version ?? "-"}`} />
        <MetricCard title="평균 MAPE" value={`${avgMape}%`} subtitle="전체 지사" />
        <MetricCard title="평균 MAE" value={avgMae} subtitle="Gcal/h" />
        <MetricCard title="평균 RMSE" value={avgRmse} subtitle="Gcal/h" />
        <MetricCard title="R² / 샘플" value={avgR2} subtitle={`${totalSamples}건`} />
      </div>

      <ChartCard title={monitoringTrendChartTitle(trendData.data_source)}>
        {trend.length === 0 ? (
          <EmptyState message="선택 기간에 예측 추이 데이터 없음" />
        ) : (
          <ResponsiveContainer width="100%" height={320}>
            <LineChart data={trend}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
              <XAxis dataKey="time" tick={{ fontSize: 11 }} />
              <YAxis tick={{ fontSize: 11 }} />
              <Tooltip />
              <Legend />
              <Line type="monotone" dataKey="predicted" name="예측" stroke="#1d4ed8" strokeWidth={2} dot={false} />
              {hasActual && (
                <Line type="monotone" dataKey="actual" name="실제" stroke="#059669" strokeWidth={2} dot={false} />
              )}
              {hasActual && (
                <Line type="monotone" dataKey="error" name="오차" stroke="#f59e0b" strokeWidth={2} dot={false} />
              )}
            </LineChart>
          </ResponsiveContainer>
        )}
      </ChartCard>

      <div className="mt-4">
        <ChartCard title="지사별 운영 성능 지표 (PREDICTION_ACTUAL_MATCH)">
          <DataTable
            columns={[
              { key: "site_name", header: "지사" },
              { key: "mape", header: "MAPE(%)", render: (r) => r.mape != null ? Number(r.mape).toFixed(2) : "-" },
              { key: "mae", header: "MAE", render: (r) => r.mae != null ? Number(r.mae).toFixed(2) : "-" },
              { key: "rmse", header: "RMSE", render: (r) => r.rmse != null ? Number(r.rmse).toFixed(2) : "-" },
              { key: "r2", header: "R²", render: (r) => r.r2 != null ? Number(r.r2).toFixed(3) : "-" },
              { key: "sample_count", header: "샘플 수" },
              { key: "max_abs_error", header: "최대 절대오차", render: (r) => r.max_abs_error != null ? Number(r.max_abs_error).toFixed(2) : "-" },
            ]}
            data={metrics as unknown as Record<string, unknown>[]}
          />
        </ChartCard>
      </div>
    </div>
  );
}
