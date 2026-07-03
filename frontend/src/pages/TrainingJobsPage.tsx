import { useEffect, useState } from "react";
import { Eye, StopCircle } from "lucide-react";
import { fetchApi, postApi, PagedData } from "@/api/client";
import { Button } from "@/components/Button";
import { DataTable } from "@/components/DataTable";
import { Modal } from "@/components/Modal";
import { StatusBadge } from "@/components/StatusBadge";
import { Pagination, LoadingState, ErrorState } from "@/components/Pagination";
import { useToast } from "@/hooks/useToast";
import { PageHeader } from "@/layouts/MainLayout";
import { PAGE_DESCRIPTIONS, PAGE_TITLES } from "@/constants/displayLabels";

interface TrainingJob {
  job_id: string;
  config_id: string;
  status: string;
  pipeline_run_id: string | null;
  site_ids: string[] | null;
  mlflow_run_id: string | null;
  registered_model_name: string | null;
  registered_model_version: string | null;
  metrics: Record<string, number> | null;
  started_at: string | null;
  ended_at: string | null;
}

export default function TrainingJobsPage() {
  const { showToast } = useToast();
  const [items, setItems] = useState<TrainingJob[]>([]);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [detail, setDetail] = useState<TrainingJob | null>(null);
  const [cancelTarget, setCancelTarget] = useState<TrainingJob | null>(null);
  const [canceling, setCanceling] = useState(false);

  const load = async (p = page) => {
    setLoading(true);
    setError("");
    try {
      const res = await fetchApi<PagedData<TrainingJob>>("/training-jobs", { page: p, size: 20 });
      setItems(res.items);
      setTotalPages(res.total_pages);
    } catch {
      setError("학습 작업 목록을 불러오지 못했습니다.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(page); }, [page]);

  const handleDetail = async (row: TrainingJob) => {
    try {
      const res = await fetchApi<TrainingJob>(`/training-jobs/${row.job_id}`);
      setDetail(res);
    } catch {
      setDetail(row);
    }
  };

  const handleCancel = async () => {
    if (!cancelTarget) return;
    setCanceling(true);
    try {
      await postApi(`/training-jobs/${cancelTarget.job_id}/cancel`);
      showToast("success", "학습 작업이 취소되었습니다.");
      setCancelTarget(null);
      setDetail(null);
      load();
    } catch {
      showToast("error", "취소에 실패했습니다.");
    } finally {
      setCanceling(false);
    }
  };

  if (loading && !items.length) return <LoadingState />;
  if (error && !items.length) return <ErrorState message={error} onRetry={() => load()} />;

  return (
    <div>
      <PageHeader title={PAGE_TITLES.trainingJobs} description={PAGE_DESCRIPTIONS.trainingJobs} />

      <DataTable
        loading={loading}
        columns={[
          { key: "job_id", header: "작업 ID" },
          { key: "config_id", header: "설정 ID" },
          { key: "status", header: "상태", render: (r) => <StatusBadge status={r.status as string} /> },
          { key: "pipeline_run_id", header: "파이프라인 Run", render: (r) => String(r.pipeline_run_id || "-") },
          { key: "registered_model_name", header: "등록 모델", render: (r) => String(r.registered_model_name || "-") },
          { key: "registered_model_version", header: "버전", render: (r) => String(r.registered_model_version || "-") },
          {
            key: "metrics",
            header: "MAPE",
            render: (r) => {
              const m = r.metrics as TrainingJob["metrics"];
              return m?.mape != null ? `${m.mape}%` : "-";
            },
          },
          { key: "started_at", header: "시작", render: (r) => r.started_at ? new Date(r.started_at as string).toLocaleString("ko-KR") : "-" },
          {
            key: "actions",
            header: "작업",
            render: (r) => {
              const row = r as unknown as TrainingJob;
              return (
                <Button variant="ghost" icon={<Eye className="w-3 h-3" />} onClick={(e) => { e.stopPropagation(); handleDetail(row); }}>
                  상세
                </Button>
              );
            },
          },
        ]}
        data={items as unknown as Record<string, unknown>[]}
      />
      <Pagination page={page} totalPages={totalPages} onChange={setPage} />

      <Modal
        open={!!detail}
        title="학습 작업 상세"
        onClose={() => setDetail(null)}
        size="lg"
        footer={
          <>
            {detail?.status === "RUNNING" && (
              <Button variant="danger" icon={<StopCircle className="w-4 h-4" />} onClick={() => setCancelTarget(detail)}>
                취소
              </Button>
            )}
            <Button variant="secondary" onClick={() => setDetail(null)}>닫기</Button>
          </>
        }
      >
        {detail && (
          <dl className="grid grid-cols-2 gap-3 text-sm">
            <div><dt className="text-slate-500">작업 ID</dt><dd className="font-medium">{detail.job_id}</dd></div>
            <div><dt className="text-slate-500">설정 ID</dt><dd>{detail.config_id}</dd></div>
            <div><dt className="text-slate-500">상태</dt><dd><StatusBadge status={detail.status} /></dd></div>
            <div><dt className="text-slate-500">파이프라인 Run</dt><dd>{detail.pipeline_run_id || "-"}</dd></div>
            <div><dt className="text-slate-500">MLflow Run</dt><dd>{detail.mlflow_run_id || "-"}</dd></div>
            <div><dt className="text-slate-500">등록 모델</dt><dd>{detail.registered_model_name ? `${detail.registered_model_name} v${detail.registered_model_version}` : "-"}</dd></div>
            <div><dt className="text-slate-500">시작</dt><dd>{detail.started_at ? new Date(detail.started_at).toLocaleString("ko-KR") : "-"}</dd></div>
            <div><dt className="text-slate-500">종료</dt><dd>{detail.ended_at ? new Date(detail.ended_at).toLocaleString("ko-KR") : "-"}</dd></div>
            {detail.metrics && (
              <div className="col-span-2">
                <dt className="text-slate-500 mb-1">성능 지표</dt>
                <dd>MAE: {detail.metrics.mae ?? "-"} / RMSE: {detail.metrics.rmse ?? "-"} / MAPE: {detail.metrics.mape ?? "-"}% / R²: {detail.metrics.r2 != null ? detail.metrics.r2.toFixed(4) : "-"}</dd>
              </div>
            )}
          </dl>
        )}
      </Modal>

      <Modal
        open={!!cancelTarget}
        title="학습 작업 취소 확인"
        onClose={() => setCancelTarget(null)}
        footer={
          <>
            <Button variant="secondary" onClick={() => setCancelTarget(null)}>닫기</Button>
            <Button variant="danger" onClick={handleCancel} disabled={canceling}>
              {canceling ? "처리 중..." : "취소 실행"}
            </Button>
          </>
        }
      >
        <p className="text-sm text-slate-600">
          작업 <strong>{cancelTarget?.job_id}</strong>을(를) 취소하시겠습니까?
        </p>
      </Modal>
    </div>
  );
}
