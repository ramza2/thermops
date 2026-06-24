import { useEffect, useState } from "react";
import { Activity, AlertTriangle, Box, TrendingUp } from "lucide-react";
import {
  Bar, BarChart, CartesianGrid, Legend, Line, LineChart,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import { fetchApi } from "@/api/client";
import { ChartCard } from "@/components/ChartCard";
import { MetricCard } from "@/components/MetricCard";
import { StatusBadge } from "@/components/StatusBadge";
import { DataTable } from "@/components/DataTable";
import { ErrorState, LoadingState } from "@/components/Pagination";
import { PageHeader } from "@/layouts/MainLayout";

interface Overview {
  prediction_status: string;
  latest_prediction_at: string | null;
  avg_mape_7d: number;
  champion_model: { model_name: string; version: string } | null;
  failed_pipeline_count: number;
  retraining_candidate_count: number;
}

interface TrendItem {
  time: string;
  predicted: number;
  actual: number | null;
  error: number | null;
}

interface ModelHealth {
  model_name: string;
  version: string;
  stage: string;
  mape: number | null;
  registered_at: string;
}

export default function DashboardPage() {
  const [overview, setOverview] = useState<Overview | null>(null);
  const [trend, setTrend] = useState<TrendItem[]>([]);
  const [health, setHealth] = useState<ModelHealth[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = async () => {
    setLoading(true);
    setError("");
    try {
      const [ov, tr, mh] = await Promise.all([
        fetchApi<Overview>("/dashboard/overview"),
        fetchApi<TrendItem[]>("/dashboard/prediction-trend"),
        fetchApi<ModelHealth[]>("/dashboard/model-health"),
      ]);
      setOverview(ov);
      setTrend(tr);
      setHealth(mh);
    } catch {
      setError("대시보드 데이터를 불러오지 못했습니다.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  if (loading) return <LoadingState />;
  if (error) return <ErrorState message={error} onRetry={load} />;

  const errorTrend = trend.filter((t) => t.error != null).map((t) => ({ time: t.time, error: t.error }));

  return (
    <div>
      <PageHeader
        title="대시보드"
        description="열수요 예측 현황 및 모델 운영 상태를 한눈에 확인합니다."
      />

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        <div className="bg-white rounded-lg border border-slate-200 p-4 shadow-sm">
          <div className="flex items-start justify-between">
            <div>
              <p className="text-xs text-slate-500 font-medium uppercase tracking-wide">예측 상태</p>
              <div className="mt-2"><StatusBadge status={overview?.prediction_status || "READY"} /></div>
              <p className="text-xs text-slate-400 mt-1">
                {overview?.latest_prediction_at ? `최근: ${new Date(overview.latest_prediction_at).toLocaleString("ko-KR")}` : "실행 이력 없음"}
              </p>
            </div>
            <Activity className="w-5 h-5 text-blue-600 opacity-80" />
          </div>
        </div>
        <MetricCard
          title="7일 평균 MAPE"
          value={`${overview?.avg_mape_7d ?? "-"}%`}
          subtitle="전체 지사 기준"
          icon={<TrendingUp className="w-5 h-5" />}
        />
        <MetricCard
          title="Champion 모델"
          value={overview?.champion_model ? `${overview.champion_model.model_name} v${overview.champion_model.version}` : "-"}
          icon={<Box className="w-5 h-5" />}
        />
        <MetricCard
          title="운영 알림"
          value={(overview?.failed_pipeline_count ?? 0) + (overview?.retraining_candidate_count ?? 0)}
          subtitle={`실패 파이프라인 ${overview?.failed_pipeline_count ?? 0} · 재학습 후보 ${overview?.retraining_candidate_count ?? 0}`}
          icon={<AlertTriangle className="w-5 h-5" />}
        />
      </div>

      <div className="grid lg:grid-cols-2 gap-4 mb-6">
        <ChartCard title="예측 vs 실제 추이">
          <ResponsiveContainer width="100%" height={280}>
            <LineChart data={trend}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
              <XAxis dataKey="time" tick={{ fontSize: 11 }} />
              <YAxis tick={{ fontSize: 11 }} />
              <Tooltip />
              <Legend />
              <Line type="monotone" dataKey="predicted" name="예측" stroke="#1d4ed8" strokeWidth={2} dot={false} />
              <Line type="monotone" dataKey="actual" name="실제" stroke="#059669" strokeWidth={2} dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </ChartCard>

        <ChartCard title="시간대별 오차">
          <ResponsiveContainer width="100%" height={280}>
            <BarChart data={errorTrend}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
              <XAxis dataKey="time" tick={{ fontSize: 11 }} />
              <YAxis tick={{ fontSize: 11 }} />
              <Tooltip />
              <Bar dataKey="error" name="절대오차" fill="#3b82f6" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>
      </div>

      <ChartCard title="모델 운영 상태">
        <DataTable
          columns={[
            { key: "model_name", header: "모델명" },
            { key: "version", header: "버전" },
            { key: "stage", header: "상태", render: (r) => <StatusBadge status={r.stage as string} /> },
            { key: "mape", header: "MAPE(%)", render: (r) => r.mape != null ? `${r.mape}%` : "-" },
            { key: "registered_at", header: "등록일", render: (r) => new Date(r.registered_at as string).toLocaleDateString("ko-KR") },
          ]}
          data={health as unknown as Record<string, unknown>[]}
        />
      </ChartCard>
    </div>
  );
}
