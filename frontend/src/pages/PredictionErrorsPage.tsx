import { useEffect, useState } from "react";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { fetchApi, PagedData } from "@/api/client";
import { ChartCard } from "@/components/ChartCard";
import { MetricCard } from "@/components/MetricCard";
import { DataTable } from "@/components/DataTable";
import { SearchPanel, SelectInput } from "@/components/SearchPanel";
import { LoadingState, ErrorState } from "@/components/Pagination";
import { PageHeader } from "@/layouts/MainLayout";

interface Prediction {
  site_id: string;
  target_at: string;
  predicted_demand: number;
  actual_demand: number | null;
  absolute_error: number | null;
}

interface Summary {
  site_id: string;
  count: number;
  avg_predicted_demand: number;
}

interface Site {
  site_id: string;
  site_name: string;
}

export default function PredictionErrorsPage() {
  const [items, setItems] = useState<Prediction[]>([]);
  const [summary, setSummary] = useState<Summary | null>(null);
  const [sites, setSites] = useState<Site[]>([]);
  const [siteId, setSiteId] = useState("SITE-001");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    fetchApi<Site[]>("/sites").then((res) => {
      setSites(res);
      if (res.length) setSiteId(res[0].site_id);
    }).catch(() => {});
  }, []);

  const load = async (sid = siteId) => {
    setLoading(true);
    setError("");
    try {
      const [preds, sum] = await Promise.all([
        fetchApi<PagedData<Prediction>>("/predictions", { site_id: sid, page: 1, size: 50 }),
        fetchApi<Summary>("/predictions/summary", { site_id: sid }),
      ]);
      setItems(preds.items.filter((p) => p.actual_demand != null));
      setSummary(sum);
    } catch {
      setError("오차 분석 데이터를 불러오지 못했습니다.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { if (siteId) load(siteId); }, [siteId]);

  const withErrors = items.filter((p) => p.absolute_error != null);
  const avgError = withErrors.length
    ? (withErrors.reduce((s, p) => s + (p.absolute_error ?? 0), 0) / withErrors.length).toFixed(2)
    : "-";
  const maxError = withErrors.length
    ? Math.max(...withErrors.map((p) => p.absolute_error ?? 0)).toFixed(2)
    : "-";

  const chartData = withErrors.slice(0, 12).map((p) => ({
    time: new Date(p.target_at).toLocaleTimeString("ko-KR", { hour: "2-digit", minute: "2-digit" }),
    error: p.absolute_error,
  }));

  if (loading && !items.length) return <LoadingState />;
  if (error) return <ErrorState message={error} onRetry={() => load()} />;

  return (
    <div>
      <PageHeader title="실제값 매칭 및 오차 분석" description="예측값과 실제값을 비교하여 오차를 분석합니다." />

      <SearchPanel
        fields={[{
          label: "지사",
          element: (
            <SelectInput value={siteId} onChange={setSiteId}
              options={sites.map((s) => ({ value: s.site_id, label: s.site_name }))} />
          ),
        }]}
        onSearch={() => load(siteId)}
      />

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        <MetricCard title="매칭 건수" value={withErrors.length} />
        <MetricCard title="평균 절대오차" value={avgError} subtitle="Gcal/h" />
        <MetricCard title="최대 절대오차" value={maxError} subtitle="Gcal/h" />
        <MetricCard title="평균 예측값" value={summary?.avg_predicted_demand ?? "-"} subtitle="Gcal/h" />
      </div>

      <ChartCard title="시간대별 절대오차">
        <ResponsiveContainer width="100%" height={280}>
          <BarChart data={chartData}>
            <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
            <XAxis dataKey="time" tick={{ fontSize: 11 }} />
            <YAxis tick={{ fontSize: 11 }} />
            <Tooltip />
            <Bar dataKey="error" name="절대오차" fill="#ef4444" radius={[4, 4, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </ChartCard>

      <div className="mt-4">
        <DataTable
          columns={[
            { key: "target_at", header: "대상 시각", render: (r) => new Date(r.target_at as string).toLocaleString("ko-KR") },
            { key: "predicted_demand", header: "예측", render: (r) => Number(r.predicted_demand).toFixed(2) },
            { key: "actual_demand", header: "실제", render: (r) => Number(r.actual_demand).toFixed(2) },
            { key: "absolute_error", header: "절대오차", render: (r) => Number(r.absolute_error).toFixed(2) },
          ]}
          data={withErrors as unknown as Record<string, unknown>[]}
        />
      </div>
    </div>
  );
}
