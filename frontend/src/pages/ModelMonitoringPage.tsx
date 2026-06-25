import { useEffect, useState } from "react";
import { Line, LineChart, CartesianGrid, ResponsiveContainer, Tooltip, Legend, XAxis, YAxis } from "recharts";
import { fetchApi } from "@/api/client";
import { ChartCard } from "@/components/ChartCard";
import { MetricCard } from "@/components/MetricCard";
import { DataTable } from "@/components/DataTable";
import { DateRangePicker, defaultDateRange } from "@/components/DateRangePicker";
import { SearchPanel } from "@/components/SearchPanel";
import { LoadingState, ErrorState } from "@/components/Pagination";
import { PageHeader } from "@/layouts/MainLayout";

interface TrendItem {
  time: string;
  predicted: number;
  actual: number | null;
  error: number | null;
}

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

export default function ModelMonitoringPage() {
  const [trend, setTrend] = useState<TrendItem[]>([]);
  const [allTrend, setAllTrend] = useState<TrendItem[]>([]);
  const [perf, setPerf] = useState<PerformanceData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [dateRange, setDateRange] = useState(defaultDateRange(7));

  const load = async () => {
    setLoading(true);
    setError("");
    try {
      const [tr, pm] = await Promise.all([
        fetchApi<TrendItem[]>("/dashboard/prediction-trend"),
        fetchApi<PerformanceData>("/performance-metrics", { eval_type: "PREDICTION_ACTUAL_MATCH" }),
      ]);
      setAllTrend(tr);
      setTrend(tr);
      setPerf(pm);
    } catch {
      setError("모니터링 데이터를 불러오지 못했습니다.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const handleSearch = () => {
    const sliceCount = Math.max(1, Math.ceil(
      ((new Date(dateRange.to).getTime() - new Date(dateRange.from).getTime()) / 86400000) + 1,
    ));
    setTrend(allTrend.slice(0, Math.min(sliceCount * 3, allTrend.length)));
  };

  if (loading) return <LoadingState />;
  if (error) return <ErrorState message={error} onRetry={load} />;

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

  return (
    <div>
      <PageHeader
        title="성능 모니터링"
        description={`${perf?.model_name} v${perf?.model_version} · 운영 예측 성능 (예측값-실제값 매칭) · ${perf?.period?.from ?? dateRange.from} ~ ${perf?.period?.to ?? dateRange.to}`}
        breadcrumbs={[
          { label: "운영 관리", path: "/ops/pipeline-runs" },
          { label: "성능 모니터링" },
        ]}
      />

      <SearchPanel
        fields={[
          {
            label: "모니터링 기간",
            element: <DateRangePicker from={dateRange.from} to={dateRange.to} onChange={(from, to) => setDateRange({ from, to })} />,
          },
        ]}
        onSearch={handleSearch}
        onReset={() => { setDateRange(defaultDateRange(7)); setTrend(allTrend); }}
      />

      <div className="grid grid-cols-2 lg:grid-cols-5 gap-4 mb-6">
        <MetricCard title="운영 모델" value={perf?.model_name ?? "-"} subtitle={`v${perf?.model_version}`} />
        <MetricCard title="평균 MAPE" value={`${avgMape}%`} subtitle="전체 지사" />
        <MetricCard title="평균 MAE" value={avgMae} subtitle="Gcal/h" />
        <MetricCard title="평균 RMSE" value={avgRmse} subtitle="Gcal/h" />
        <MetricCard title="R² / 샘플" value={avgR2} subtitle={`${totalSamples}건`} />
      </div>

      <ChartCard title="예측 성능 추이 (예측 vs 실제)">
        <ResponsiveContainer width="100%" height={320}>
          <LineChart data={trend}>
            <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
            <XAxis dataKey="time" tick={{ fontSize: 11 }} />
            <YAxis tick={{ fontSize: 11 }} />
            <Tooltip />
            <Legend />
            <Line type="monotone" dataKey="predicted" name="예측" stroke="#1d4ed8" strokeWidth={2} dot={false} />
            <Line type="monotone" dataKey="actual" name="실제" stroke="#059669" strokeWidth={2} dot={false} />
            <Line type="monotone" dataKey="error" name="오차" stroke="#f59e0b" strokeWidth={2} dot={false} />
          </LineChart>
        </ResponsiveContainer>
      </ChartCard>

      <div className="mt-4">
        <ChartCard title="지사별 운영 성능 지표">
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
