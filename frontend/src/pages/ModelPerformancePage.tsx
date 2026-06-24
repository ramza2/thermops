import { useEffect, useState } from "react";
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { fetchApi } from "@/api/client";
import { ChartCard } from "@/components/ChartCard";
import { MetricCard } from "@/components/MetricCard";
import { DataTable } from "@/components/DataTable";
import { LoadingState, ErrorState } from "@/components/Pagination";
import { PageHeader } from "@/layouts/MainLayout";

interface PerformanceData {
  model_name: string;
  model_version: string;
  period: { from: string; to: string };
  metrics: { site_id: string; site_name: string; mae: number | null; rmse: number | null; mape: number | null }[];
}

export default function ModelPerformancePage() {
  const [data, setData] = useState<PerformanceData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = async () => {
    setLoading(true);
    setError("");
    try {
      const res = await fetchApi<PerformanceData>("/performance-metrics");
      setData(res);
    } catch {
      setError("성능 지표를 불러오지 못했습니다.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  if (loading) return <LoadingState />;
  if (error) return <ErrorState message={error} onRetry={load} />;

  const chartData = (data?.metrics ?? []).map((m) => ({
    site: m.site_name,
    MAPE: m.mape,
    MAE: m.mae,
    RMSE: m.rmse,
  }));

  const avgMape = data?.metrics.length
    ? (data.metrics.reduce((s, m) => s + (m.mape ?? 0), 0) / data.metrics.length).toFixed(2)
    : "-";

  return (
    <div>
      <PageHeader
        title="모델 성능 비교"
        description={`${data?.model_name} v${data?.model_version} · ${data?.period.from} ~ ${data?.period.to}`}
      />

      <div className="grid grid-cols-3 gap-4 mb-6">
        <MetricCard title="모델" value={data?.model_name ?? "-"} subtitle={`v${data?.model_version}`} />
        <MetricCard title="평균 MAPE" value={`${avgMape}%`} subtitle="지사별 평균" />
        <MetricCard title="비교 지사 수" value={data?.metrics.length ?? 0} />
      </div>

      <ChartCard title="지사별 성능 비교">
        <ResponsiveContainer width="100%" height={320}>
          <BarChart data={chartData}>
            <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
            <XAxis dataKey="site" tick={{ fontSize: 11 }} />
            <YAxis tick={{ fontSize: 11 }} />
            <Tooltip />
            <Legend />
            <Bar dataKey="MAPE" name="MAPE(%)" fill="#1d4ed8" radius={[4, 4, 0, 0]} />
            <Bar dataKey="MAE" name="MAE" fill="#059669" radius={[4, 4, 0, 0]} />
            <Bar dataKey="RMSE" name="RMSE" fill="#7c3aed" radius={[4, 4, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </ChartCard>

      <div className="mt-4">
        <DataTable
          columns={[
            { key: "site_id", header: "지사 ID" },
            { key: "site_name", header: "지사명" },
            { key: "mape", header: "MAPE(%)", render: (r) => r.mape != null ? `${r.mape}%` : "-" },
            { key: "mae", header: "MAE", render: (r) => r.mae != null ? String(r.mae) : "-" },
            { key: "rmse", header: "RMSE", render: (r) => r.rmse != null ? String(r.rmse) : "-" },
          ]}
          data={(data?.metrics ?? []) as unknown as Record<string, unknown>[]}
        />
      </div>
    </div>
  );
}
