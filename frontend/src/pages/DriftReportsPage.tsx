import { useEffect, useState } from "react";
import { Play } from "lucide-react";
import { fetchApi, postApi, PagedData } from "@/api/client";
import { Button } from "@/components/Button";
import { DataTable } from "@/components/DataTable";
import { StatusBadge } from "@/components/StatusBadge";
import { Pagination, LoadingState, ErrorState } from "@/components/Pagination";
import { useToast } from "@/hooks/useToast";
import { PageHeader } from "@/layouts/MainLayout";

interface DriftReport {
  drift_report_id: string;
  base_period: string;
  current_period: string;
  drift_status: string;
  drift_score_json: Record<string, number>;
  created_at: string;
}

export default function DriftReportsPage() {
  const { showToast } = useToast();
  const [items, setItems] = useState<DriftReport[]>([]);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [running, setRunning] = useState(false);

  const load = async (p = page) => {
    setLoading(true);
    setError("");
    try {
      const res = await fetchApi<PagedData<DriftReport>>("/drift-reports", { page: p, size: 20 });
      setItems(res.items);
      setTotalPages(res.total_pages);
    } catch {
      setError("드리프트 리포트를 불러오지 못했습니다.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(page); }, [page]);

  const handleRunCheck = async () => {
    setRunning(true);
    try {
      const res = await postApi<{ report_id: string; status: string }>("/drift-checks", {});
      showToast("success", `드리프트 점검이 요청되었습니다. (${res.report_id})`);
      load(1);
      setPage(1);
    } catch {
      showToast("error", "드리프트 점검 실행에 실패했습니다.");
    } finally {
      setRunning(false);
    }
  };

  if (loading && !items.length) return <LoadingState />;
  if (error && !items.length) return <ErrorState message={error} onRetry={() => load()} />;

  return (
    <div>
      <PageHeader
        title="드리프트 리포트"
        description="Feature 및 데이터 분포 드리프트를 점검하고 리포트를 확인합니다."
        actions={<Button icon={<Play className="w-4 h-4" />} onClick={handleRunCheck} disabled={running}>{running ? "실행 중..." : "드리프트 점검"}</Button>}
      />

      <DataTable
        loading={loading}
        columns={[
          { key: "drift_report_id", header: "리포트 ID" },
          { key: "base_period", header: "기준 기간" },
          { key: "current_period", header: "현재 기간" },
          { key: "drift_status", header: "상태", render: (r) => <StatusBadge status={r.drift_status as string} /> },
          {
            key: "drift_score_json", header: "드리프트 점수", render: (r) => {
              const scores = r.drift_score_json as Record<string, number>;
              return Object.entries(scores).map(([k, v]) => `${k}: ${v}`).join(", ") || "-";
            },
          },
          { key: "created_at", header: "생성일", render: (r) => new Date(r.created_at as string).toLocaleString("ko-KR") },
        ]}
        data={items as unknown as Record<string, unknown>[]}
      />
      <Pagination page={page} totalPages={totalPages} onChange={setPage} />
    </div>
  );
}
