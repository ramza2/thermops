import { useCallback, useEffect, useState } from "react";
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { fetchApi } from "@/api/client";
import { ChartCard } from "@/components/ChartCard";
import { MetricCard } from "@/components/MetricCard";
import { DataTable } from "@/components/DataTable";
import { SearchPanel, SelectInput } from "@/components/SearchPanel";
import { LoadingState, ErrorState } from "@/components/Pagination";
import { PageHeader } from "@/layouts/MainLayout";

const EVAL_PREDICTION = "PREDICTION_ACTUAL_MATCH";
const EVAL_TRAINING = "TRAINING_VALIDATION";

const EVAL_OPTIONS = [
  { value: EVAL_PREDICTION, label: "운영 예측 성능" },
  { value: EVAL_TRAINING, label: "학습 검증 성능" },
];

const EVAL_DESCRIPTIONS: Record<string, string> = {
  [EVAL_PREDICTION]: "운영 예측 성능: 예측값과 실제값 매칭 기준",
  [EVAL_TRAINING]: "학습 검증 성능: 학습 시 Validation Set 기준",
};

interface PerformanceMetric {
  site_id: string;
  site_name: string;
  mae: number | null;
  rmse: number | null;
  mape: number | null;
  r2: number | null;
  sample_count: number | null;
  eval_type: string | null;
}

interface PerformanceData {
  model_name: string;
  model_version: string;
  eval_type: string | null;
  period: { from: string; to: string };
  metrics: PerformanceMetric[];
}

export default function ModelPerformancePage() {
  const [data, setData] = useState<PerformanceData | null>(null);
  const [evalType, setEvalType] = useState(EVAL_PREDICTION);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = useCallback(async (type = evalType) => {
    setLoading(true);
    setError("");
    try {
      const res = await fetchApi<PerformanceData>("/performance-metrics", { eval_type: type });
      setData(res);
    } catch {
      setError("성능 지표를 불러오지 못했습니다.");
    } finally {
      setLoading(false);
    }
  }, [evalType]);

  useEffect(() => { load(evalType); }, [evalType, load]);

  const handleSearch = () => load(evalType);

  if (loading && !data) return <LoadingState />;
  if (error && !data) return <ErrorState message={error} onRetry={() => load(evalType)} />;

  const metrics = data?.metrics ?? [];
  const chartData = metrics.map((m) => ({
    site: m.site_name,
    MAPE: m.mape,
    MAE: m.mae,
    RMSE: m.rmse,
  }));

  const avgMape = metrics.length
    ? (metrics.reduce((s, m) => s + (m.mape ?? 0), 0) / metrics.length).toFixed(2)
    : "-";
  const avgR2 = metrics.filter((m) => m.r2 != null).length
    ? (metrics.reduce((s, m) => s + (m.r2 ?? 0), 0) / metrics.filter((m) => m.r2 != null).length).toFixed(3)
    : "-";
  const totalSamples = metrics.reduce((s, m) => s + (m.sample_count ?? 0), 0);

  const evalLabel = EVAL_OPTIONS.find((o) => o.value === evalType)?.label ?? evalType;
  const evalDesc = EVAL_DESCRIPTIONS[evalType] ?? "";

  return (
    <div>
      <PageHeader
        title="모델 성능 비교"
        description={`${data?.model_name ?? "-"} v${data?.model_version ?? "-"} · ${evalLabel} · ${data?.period.from ?? "-"} ~ ${data?.period.to ?? "-"}`}
      />

      <SearchPanel
        fields={[
          {
            label: "성능 유형",
            element: (
              <SelectInput value={evalType} onChange={setEvalType} options={EVAL_OPTIONS} />
            ),
          },
        ]}
        onSearch={handleSearch}
        onReset={() => setEvalType(EVAL_PREDICTION)}
      />

      <p className="text-sm text-slate-600 mb-4 bg-slate-50 border border-slate-200 rounded-md px-3 py-2">
        {evalDesc}
        {metrics.length === 0 && (
          <span className="text-amber-600 ml-2">해당 유형의 성능 데이터가 없습니다.</span>
        )}
      </p>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        <MetricCard title="모델" value={data?.model_name ?? "-"} subtitle={`v${data?.model_version ?? "-"}`} />
        <MetricCard title="평균 MAPE" value={metrics.length ? `${avgMape}%` : "-"} subtitle={evalLabel} />
        <MetricCard title="평균 R²" value={avgR2} subtitle={evalType === EVAL_PREDICTION ? "운영 기준" : "검증 기준"} />
        <MetricCard title="총 샘플 수" value={totalSamples || "-"} subtitle={`${metrics.length}개 지사`} />
      </div>

      {metrics.length > 0 && (
        <ChartCard title={`지사별 ${evalLabel} 비교`}>
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
      )}

      <div className="mt-4">
        <DataTable
          loading={loading}
          columns={[
            { key: "site_id", header: "지사 ID" },
            { key: "site_name", header: "지사명" },
            { key: "mape", header: "MAPE(%)", render: (r) => r.mape != null ? Number(r.mape).toFixed(2) : "-" },
            { key: "mae", header: "MAE", render: (r) => r.mae != null ? Number(r.mae).toFixed(2) : "-" },
            { key: "rmse", header: "RMSE", render: (r) => r.rmse != null ? Number(r.rmse).toFixed(2) : "-" },
            { key: "r2", header: "R²", render: (r) => r.r2 != null ? Number(r.r2).toFixed(3) : "-" },
            { key: "sample_count", header: "샘플 수", render: (r) => r.sample_count != null ? String(r.sample_count) : "-" },
            {
              key: "eval_type",
              header: "지표 유형",
              render: (r) => {
                const t = r.eval_type as string;
                if (t === EVAL_PREDICTION) return "운영 예측";
                if (t === EVAL_TRAINING) return "학습 검증";
                return "미분류";
              },
            },
          ]}
          data={metrics as unknown as Record<string, unknown>[]}
        />
      </div>
    </div>
  );
}
