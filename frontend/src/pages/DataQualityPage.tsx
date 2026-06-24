import { useEffect, useState } from "react";
import { Play } from "lucide-react";
import { fetchApi, postApi, PagedData } from "@/api/client";
import { Button } from "@/components/Button";
import { DataTable } from "@/components/DataTable";
import { MetricCard } from "@/components/MetricCard";
import { StatusBadge } from "@/components/StatusBadge";
import { Pagination, LoadingState, ErrorState } from "@/components/Pagination";
import { useToast } from "@/hooks/useToast";
import { PageHeader } from "@/layouts/MainLayout";

interface QualitySummary {
  quality_score?: number;
  missing_count?: number;
  duplicate_count?: number;
  time_gap_count?: number;
  outlier_count?: number;
  missing_rate?: number;
  target_table?: string;
  data_domain?: string;
}

interface QualityRun {
  run_id: string;
  source_id: string | null;
  check_type: string;
  run_status: string;
  result_summary: QualitySummary | null;
  started_at: string;
  finished_at: string | null;
}

function formatSummary(s: QualitySummary | null | undefined): string {
  if (!s) return "-";
  const score = s.quality_score != null ? `점수 ${s.quality_score.toFixed(1)}` : null;
  const missing = s.missing_count != null
    ? `결측 ${s.missing_count}`
    : s.missing_rate != null
      ? `결측 ${(s.missing_rate * 100).toFixed(1)}%`
      : null;
  const parts = [
    score,
    missing,
    `중복 ${s.duplicate_count ?? 0}`,
    `시간누락 ${s.time_gap_count ?? 0}`,
    `이상치 ${s.outlier_count ?? 0}`,
  ].filter(Boolean);
  return parts.join(" · ");
}

export default function DataQualityPage() {
  const { showToast } = useToast();
  const [items, setItems] = useState<QualityRun[]>([]);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [running, setRunning] = useState(false);

  const load = async (p = page) => {
    setLoading(true);
    setError("");
    try {
      const res = await fetchApi<PagedData<QualityRun>>("/data-quality/runs", { page: p, size: 20 });
      setItems(res.items);
      setTotalPages(res.total_pages);
    } catch {
      setError("품질 점검 이력을 불러오지 못했습니다.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(page); }, [page]);

  const handleRunCheck = async () => {
    setRunning(true);
    try {
      const res = await postApi<{
        run_id: string;
        status: string;
        result_summary?: QualitySummary;
      }>("/data-quality/checks");
      const score = res.result_summary?.quality_score;
      showToast(
        "success",
        score != null
          ? `품질 점검 완료 — 점수 ${score.toFixed(1)} (${res.run_id})`
          : `품질 점검이 완료되었습니다. (${res.run_id})`,
      );
      load(1);
      setPage(1);
    } catch {
      showToast("error", "품질 점검 실행에 실패했습니다.");
    } finally {
      setRunning(false);
    }
  };

  const successCount = items.filter((i) => i.run_status === "SUCCESS").length;
  const latest = items[0]?.result_summary;

  if (loading && !items.length) return <LoadingState />;
  if (error && !items.length) return <ErrorState message={error} onRetry={() => load()} />;

  return (
    <div>
      <PageHeader
        title="데이터 품질 점검"
        description="데이터 적재 후 품질 규칙을 실행하고 결과를 확인합니다."
        actions={<Button icon={<Play className="w-4 h-4" />} onClick={handleRunCheck} disabled={running}>{running ? "실행 중..." : "품질 점검 실행"}</Button>}
      />

      <div className="grid grid-cols-4 gap-4 mb-6">
        <MetricCard title="총 점검 횟수" value={items.length} />
        <MetricCard title="성공" value={successCount} subtitle="현재 페이지 기준" />
        <MetricCard
          title="최근 품질 점수"
          value={latest?.quality_score != null ? latest.quality_score.toFixed(1) : "-"}
          subtitle={latest?.target_table || "이력 없음"}
        />
        <div className="bg-white rounded-lg border border-slate-200 p-4 shadow-sm">
          <p className="text-xs text-slate-500 font-medium uppercase tracking-wide">최근 상태</p>
          <div className="mt-2">{items[0] ? <StatusBadge status={items[0].run_status} /> : <span className="text-2xl font-bold text-slate-900">-</span>}</div>
          <p className="text-xs text-slate-400 mt-1">{items[0] ? new Date(items[0].started_at).toLocaleString("ko-KR") : "이력 없음"}</p>
        </div>
      </div>

      <DataTable
        loading={loading}
        columns={[
          { key: "run_id", header: "실행 ID" },
          { key: "source_id", header: "소스 ID", render: (r) => String(r.source_id || "전체") },
          { key: "check_type", header: "점검 유형" },
          { key: "run_status", header: "상태", render: (r) => <StatusBadge status={r.run_status as string} /> },
          {
            key: "result_summary",
            header: "결과 요약",
            render: (r) => formatSummary(r.result_summary as QualitySummary | null),
          },
          { key: "started_at", header: "시작", render: (r) => new Date(r.started_at as string).toLocaleString("ko-KR") },
        ]}
        data={items as unknown as Record<string, unknown>[]}
      />
      <Pagination page={page} totalPages={totalPages} onChange={setPage} />
    </div>
  );
}
