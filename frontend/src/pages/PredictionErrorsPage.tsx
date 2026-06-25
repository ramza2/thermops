import { useEffect, useState } from "react";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { fetchApi, PagedData } from "@/api/client";
import { ChartCard } from "@/components/ChartCard";
import { MetricCard } from "@/components/MetricCard";
import { DataTable } from "@/components/DataTable";
import { SearchPanel, SelectInput } from "@/components/SearchPanel";
import { DateRangePicker, defaultDateRange } from "@/components/DateRangePicker";
import { LoadingState, ErrorState } from "@/components/Pagination";
import { PageHeader } from "@/layouts/MainLayout";

interface PredictionError {
  match_id: number;
  site_id: string;
  target_at: string;
  predicted_demand: number;
  actual_demand: number;
  error: number | null;
  abs_error: number | null;
  ape: number | null;
  model_name: string | null;
  model_version: string | null;
  model_version_id: string;
}

interface Site {
  site_id: string;
  site_name: string;
}

interface Model {
  model_version_id: string;
  model_name: string;
  version_no: string;
}

export default function PredictionErrorsPage() {
  const [items, setItems] = useState<PredictionError[]>([]);
  const [totalCount, setTotalCount] = useState(0);
  const [sites, setSites] = useState<Site[]>([]);
  const [models, setModels] = useState<Model[]>([]);
  const [siteId, setSiteId] = useState("");
  const [modelVersionId, setModelVersionId] = useState("");
  const [dateRange, setDateRange] = useState(defaultDateRange(7));
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    Promise.all([
      fetchApi<Site[]>("/sites").catch(() => []),
      fetchApi<Model[]>("/models").catch(() => []),
    ]).then(([s, m]) => {
      setSites(s);
      setModels(m);
      if (m.length) setModelVersionId(m[0].model_version_id);
    });
  }, []);

  const load = async () => {
    setLoading(true);
    setError("");
    try {
      const params: Record<string, unknown> = { page: 1, size: 100 };
      if (siteId) params.site_id = siteId;
      if (modelVersionId) params.model_version_id = modelVersionId;
      if (dateRange.from) params.from = `${dateRange.from}T00:00:00`;
      if (dateRange.to) params.to = `${dateRange.to}T23:59:59`;
      const res = await fetchApi<PagedData<PredictionError>>("/predictions/errors", params);
      setItems(res.items);
      setTotalCount(res.total_count);
    } catch {
      setError("오차 분석 데이터를 불러오지 못했습니다.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const withErrors = items.filter((p) => p.abs_error != null);
  const avgError = withErrors.length
    ? (withErrors.reduce((s, p) => s + (p.abs_error ?? 0), 0) / withErrors.length).toFixed(2)
    : "-";
  const maxError = withErrors.length
    ? Math.max(...withErrors.map((p) => p.abs_error ?? 0)).toFixed(2)
    : "-";
  const avgApe = withErrors.filter((p) => p.ape != null).length
    ? (withErrors.reduce((s, p) => s + (p.ape ?? 0), 0) / withErrors.filter((p) => p.ape != null).length).toFixed(2)
    : "-";

  const chartData = withErrors.slice(0, 12).map((p) => ({
    time: new Date(p.target_at).toLocaleTimeString("ko-KR", { hour: "2-digit", minute: "2-digit" }),
    error: p.abs_error,
  }));

  if (loading && !items.length) return <LoadingState />;
  if (error) return <ErrorState message={error} onRetry={load} />;

  return (
    <div>
      <PageHeader title="실제값 매칭 및 오차 분석" description="예측값과 실제값을 비교하여 오차를 분석합니다." />

      <SearchPanel
        fields={[
          {
            label: "조회 기간",
            colSpan: 2,
            element: <DateRangePicker from={dateRange.from} to={dateRange.to} onChange={(from, to) => setDateRange({ from, to })} />,
          },
          {
            label: "지사",
            element: (
              <SelectInput value={siteId} onChange={setSiteId}
                options={[{ value: "", label: "전체" }, ...sites.map((s) => ({ value: s.site_id, label: s.site_name }))]} />
            ),
          },
          {
            label: "모델 버전",
            element: (
              <SelectInput value={modelVersionId} onChange={setModelVersionId}
                options={[{ value: "", label: "전체" }, ...models.map((m) => ({
                  value: m.model_version_id,
                  label: `${m.model_name} v${m.version_no}`,
                }))]} />
            ),
          },
        ]}
        onSearch={load}
        onReset={() => { setSiteId(""); setModelVersionId(""); setDateRange(defaultDateRange(7)); }}
      />

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        <MetricCard title="매칭 건수" value={totalCount || withErrors.length} />
        <MetricCard title="평균 절대오차" value={avgError} subtitle="Gcal/h" />
        <MetricCard title="최대 절대오차" value={maxError} subtitle="Gcal/h" />
        <MetricCard title="평균 APE" value={avgApe !== "-" ? `${avgApe}%` : "-"} />
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
            { key: "site_id", header: "지사" },
            { key: "predicted_demand", header: "예측", render: (r) => Number(r.predicted_demand).toFixed(2) },
            { key: "actual_demand", header: "실제", render: (r) => Number(r.actual_demand).toFixed(2) },
            { key: "error", header: "오차", render: (r) => r.error != null ? Number(r.error).toFixed(2) : "-" },
            { key: "abs_error", header: "절대오차", render: (r) => r.abs_error != null ? Number(r.abs_error).toFixed(2) : "-" },
            { key: "ape", header: "APE(%)", render: (r) => r.ape != null ? Number(r.ape).toFixed(2) : "-" },
          ]}
          data={withErrors as unknown as Record<string, unknown>[]}
        />
      </div>
    </div>
  );
}
