import { useCallback, useEffect, useState } from "react";
import { Eye, Play } from "lucide-react";
import { fetchApi, postApi, PagedData } from "@/api/client";
import { Button } from "@/components/Button";
import { DataTable } from "@/components/DataTable";
import { Modal } from "@/components/Modal";
import { StatusBadge } from "@/components/StatusBadge";
import { Pagination, LoadingState, ErrorState } from "@/components/Pagination";
import { useToast } from "@/hooks/useToast";
import { PageHeader } from "@/layouts/MainLayout";

type SourceFilter = "computed" | "all" | "seed";

interface DriftReport {
  drift_report_id: string;
  model_version_id: string | null;
  feature_set_id: string | null;
  site_id: string | null;
  site_name: string;
  drift_type: string;
  drift_status: string;
  drift_score: number | null;
  base_period: string;
  current_period: string;
  baseline_start_at: string | null;
  baseline_end_at: string | null;
  current_start_at: string | null;
  current_end_at: string | null;
  drift_score_json: Record<string, unknown>;
  metric_summary_json: Record<string, unknown>;
  feature_drift_json: Record<string, unknown>;
  recommendation: string | null;
  source_type: string;
  computed: boolean;
  created_at: string;
}

interface DriftCheckResult {
  status: string;
  overall_drift_status: string;
  drift_report_id: string;
  created_retraining_candidates: number;
  metric_summary: Record<string, unknown>;
}

const SOURCE_LABELS: Record<string, string> = {
  COMPUTED: "계산 결과",
  SEED: "샘플/시드",
  MANUAL: "수동",
};

function SourceTypeBadge({ sourceType }: { sourceType: string }) {
  const className =
    sourceType === "COMPUTED"
      ? "bg-emerald-100 text-emerald-700"
      : sourceType === "SEED"
        ? "bg-slate-100 text-slate-500"
        : "bg-blue-100 text-blue-700";
  return (
    <span className={`inline-flex px-2 py-0.5 rounded text-xs font-medium ${className}`}>
      {SOURCE_LABELS[sourceType] || sourceType}
    </span>
  );
}

export default function DriftReportsPage() {
  const { showToast } = useToast();
  const [items, setItems] = useState<DriftReport[]>([]);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [running, setRunning] = useState(false);
  const [detail, setDetail] = useState<DriftReport | null>(null);
  const [sourceFilter, setSourceFilter] = useState<SourceFilter>("computed");

  const load = useCallback(async (p = page, filter = sourceFilter) => {
    setLoading(true);
    setError("");
    try {
      const params: Record<string, string | number | boolean> = { page: p, size: 20 };
      if (filter === "computed") params.computed_only = true;
      else if (filter === "seed") params.source_type = "SEED";
      const res = await fetchApi<PagedData<DriftReport>>("/drift-reports", params);
      setItems(res.items);
      setTotalPages(res.total_pages);
    } catch {
      setError("드리프트 리포트를 불러오지 못했습니다.");
    } finally {
      setLoading(false);
    }
  }, [page, sourceFilter]);

  useEffect(() => { load(page, sourceFilter); }, [page, sourceFilter, load]);

  const handleFilterChange = (filter: SourceFilter) => {
    setSourceFilter(filter);
    setPage(1);
  };

  const handleRunCheck = async () => {
    setRunning(true);
    try {
      const res = await postApi<DriftCheckResult>("/drift-checks", {
        feature_set_id: "FS-TPL-LAG-ROLL",
        baseline_start_at: "2026-05-22T00:00:00",
        baseline_end_at: "2026-06-05T23:00:00",
        current_start_at: "2026-06-06T00:00:00",
        current_end_at: "2026-06-20T23:00:00",
      });
      showToast(
        "success",
        `드리프트 점검 완료: ${res.overall_drift_status} (리포트 ${res.drift_report_id})`,
      );
      setSourceFilter("computed");
      setPage(1);
      load(1, "computed");
    } catch {
      showToast("error", "드리프트 점검 실행에 실패했습니다.");
    } finally {
      setRunning(false);
    }
  };

  const openDetail = async (reportId: string) => {
    try {
      const res = await fetchApi<DriftReport>(`/drift-reports/${reportId}`);
      setDetail(res);
    } catch {
      showToast("error", "상세 정보를 불러오지 못했습니다.");
    }
  };

  const showSeedNotice = sourceFilter !== "computed" && items.some((i) => i.source_type === "SEED");

  if (loading && !items.length) return <LoadingState />;
  if (error && !items.length) return <ErrorState message={error} onRetry={() => load()} />;

  return (
    <div>
      <PageHeader
        title="드리프트 리포트"
        description="운영 성능·예측 오차·Feature 분포 Drift를 점검하고 리포트를 확인합니다."
        actions={<Button icon={<Play className="w-4 h-4" />} onClick={handleRunCheck} disabled={running}>{running ? "실행 중..." : "드리프트 점검"}</Button>}
      />

      <div className="flex flex-wrap gap-2 mb-4">
        <Button variant={sourceFilter === "computed" ? "primary" : "secondary"} onClick={() => handleFilterChange("computed")}>
          계산 결과만
        </Button>
        <Button variant={sourceFilter === "all" ? "primary" : "secondary"} onClick={() => handleFilterChange("all")}>
          전체
        </Button>
        <Button variant={sourceFilter === "seed" ? "primary" : "secondary"} onClick={() => handleFilterChange("seed")}>
          Seed/Sample
        </Button>
      </div>

      {showSeedNotice && (
        <p className="mb-4 text-sm text-amber-700 bg-amber-50 border border-amber-100 rounded px-3 py-2">
          샘플/시드 데이터는 시연용이며 실제 운영 Drift 계산 결과가 아닙니다.
        </p>
      )}

      <DataTable
        loading={loading}
        columns={[
          { key: "drift_report_id", header: "리포트 ID" },
          {
            key: "source_type",
            header: "구분",
            render: (r) => <SourceTypeBadge sourceType={(r.source_type as string) || "SEED"} />,
          },
          { key: "model_version_id", header: "모델 버전", render: (r) => (r.model_version_id as string) || "-" },
          { key: "site_name", header: "지사" },
          { key: "drift_type", header: "유형" },
          { key: "drift_status", header: "상태", render: (r) => <StatusBadge status={r.drift_status as string} /> },
          {
            key: "drift_score",
            header: "Drift 점수",
            render: (r) => (r.drift_score != null ? Number(r.drift_score).toFixed(3) : "-"),
          },
          { key: "base_period", header: "기준 기간" },
          { key: "current_period", header: "현재 기간" },
          { key: "created_at", header: "생성일", render: (r) => new Date(r.created_at as string).toLocaleString("ko-KR") },
          {
            key: "actions",
            header: "상세",
            render: (r) => (
              <Button
                variant="secondary"
                icon={<Eye className="w-3 h-3" />}
                onClick={(e) => { e.stopPropagation(); openDetail(r.drift_report_id as string); }}
              >
                보기
              </Button>
            ),
          },
        ]}
        data={items as unknown as Record<string, unknown>[]}
      />
      <Pagination page={page} totalPages={totalPages} onChange={setPage} />

      <Modal
        open={!!detail}
        title={`Drift 리포트 — ${detail?.drift_report_id ?? ""}`}
        onClose={() => setDetail(null)}
        footer={<Button variant="secondary" onClick={() => setDetail(null)}>닫기</Button>}
      >
        {detail && (
          <div className="space-y-4 text-sm">
            <div className="flex gap-2 items-center flex-wrap">
              <StatusBadge status={detail.drift_status} />
              <SourceTypeBadge sourceType={detail.source_type || "SEED"} />
              <span className="text-slate-500">{detail.drift_type}</span>
            </div>
            {detail.source_type === "SEED" && (
              <p className="text-amber-700 text-xs bg-amber-50 rounded px-2 py-1">
                이 리포트는 샘플/시드 데이터이며 실제 운영 계산 결과가 아닙니다.
              </p>
            )}
            <p className="text-slate-600">{detail.recommendation || "권고 사항 없음"}</p>
            <div>
              <h4 className="font-medium text-slate-700 mb-1">성능·오차 요약</h4>
              <pre className="bg-slate-50 p-3 rounded text-xs overflow-auto max-h-48">
                {JSON.stringify(detail.metric_summary_json, null, 2)}
              </pre>
            </div>
            <div>
              <h4 className="font-medium text-slate-700 mb-1">Feature Drift</h4>
              <pre className="bg-slate-50 p-3 rounded text-xs overflow-auto max-h-48">
                {JSON.stringify(detail.feature_drift_json, null, 2)}
              </pre>
            </div>
          </div>
        )}
      </Modal>
    </div>
  );
}
