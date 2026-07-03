import { useCallback, useEffect, useState } from "react";
import { Check, Eye, Play, RefreshCw, X } from "lucide-react";
import { fetchApi, postApi } from "@/api/client";
import { Button } from "@/components/Button";
import { DataTable } from "@/components/DataTable";
import { Modal } from "@/components/Modal";
import { StatusBadge } from "@/components/StatusBadge";
import { LoadingState, ErrorState } from "@/components/Pagination";
import { useToast } from "@/hooks/useToast";
import { PageHeader } from "@/layouts/MainLayout";
import { PAGE_DESCRIPTIONS, PAGE_TITLES } from "@/constants/displayLabels";
import { useRole } from "@/hooks/useRole";

type SourceFilter = "computed" | "all" | "seed";

interface RetrainingCandidate {
  candidate_id: string;
  model_version_id: string | null;
  new_model_version_id: string | null;
  feature_set_id: string | null;
  model_name: string;
  model_version: string;
  site_id: string | null;
  site_name: string;
  reason_type: string;
  severity: string;
  reason_summary: string;
  status: string;
  source_type: string;
  drift_report_id: string | null;
  training_job_id: string | null;
  mlflow_run_id: string | null;
  retraining_dag_run_id: string | null;
  execution_mode: string | null;
  trained_at: string | null;
  train_result_summary: Record<string, unknown> | null;
  error_message: string | null;
  metric_snapshot_json: Record<string, unknown> | null;
  created_at: string;
}

const REASON_LABELS: Record<string, string> = {
  PERFORMANCE_DEGRADATION: "성능 저하",
  FEATURE_DRIFT: "Feature Drift",
  ERROR_DRIFT: "예측 오차 Drift",
  MANUAL: "수동",
};

const SOURCE_LABELS: Record<string, string> = {
  COMPUTED: "자동 산출",
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

export default function RetrainingCandidatesPage() {
  const { showToast } = useToast();
  const { canEdit } = useRole();
  const [items, setItems] = useState<RetrainingCandidate[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [acting, setActing] = useState<string | null>(null);
  const [sourceFilter, setSourceFilter] = useState<SourceFilter>("computed");
  const [detail, setDetail] = useState<RetrainingCandidate | null>(null);

  const load = useCallback(async (filter = sourceFilter, syncAirflow = false) => {
    setLoading(true);
    setError("");
    try {
      const params: Record<string, string | boolean> = {};
      if (filter === "computed") params.computed_only = true;
      else if (filter === "seed") params.source_type = "SEED";
      if (syncAirflow) params.sync_airflow = true;
      const candidates = await fetchApi<RetrainingCandidate[]>("/retraining-candidates", params);
      setItems(candidates);
    } catch {
      setError("재학습 후보 목록을 불러오지 못했습니다.");
    } finally {
      setLoading(false);
    }
  }, [sourceFilter]);

  useEffect(() => { load(sourceFilter); }, [sourceFilter, load]);

  const hasTraining = items.some((i) => i.status === "TRAINING");
  useEffect(() => {
    if (!hasTraining) return;
    const timer = window.setInterval(() => {
      load(sourceFilter, true);
    }, 10000);
    return () => window.clearInterval(timer);
  }, [hasTraining, sourceFilter, load]);

  const handleApprove = async (candidateId: string) => {
    setActing(candidateId);
    try {
      await postApi(`/retraining-candidates/${candidateId}/approve`, {});
      showToast("success", "재학습 후보가 승인되었습니다.");
      load(sourceFilter);
    } catch {
      showToast("error", "승인 처리에 실패했습니다.");
    } finally {
      setActing(null);
    }
  };

  const handleReject = async (candidateId: string) => {
    setActing(candidateId);
    try {
      await postApi(`/retraining-candidates/${candidateId}/reject`, {});
      showToast("success", "재학습 후보가 반려되었습니다.");
      load(sourceFilter);
    } catch {
      showToast("error", "반려 처리에 실패했습니다.");
    } finally {
      setActing(null);
    }
  };

  const handleTrain = async (candidateId: string) => {
    setActing(candidateId);
    try {
      const res = await postApi<{
        candidate: RetrainingCandidate;
        retraining_dag_run_id?: string;
        dag_run_id?: string;
      }>(`/retraining-candidates/${candidateId}/train?execution_mode=AIRFLOW`, {});
      const dagRunId = res.retraining_dag_run_id || res.dag_run_id || res.candidate?.retraining_dag_run_id;
      showToast("success", `재학습 DAG 실행 요청 완료${dagRunId ? `: ${dagRunId}` : ""}`);
      load(sourceFilter, true);
    } catch {
      showToast("error", "재학습 실행에 실패했습니다.");
    } finally {
      setActing(null);
    }
  };

  const showSeedNotice = sourceFilter !== "computed" && items.some((i) => i.source_type === "SEED");

  const renderActions = (row: RetrainingCandidate) => {
    if (!canEdit) return <span className="text-xs text-slate-400">권한 없음</span>;
    if (row.source_type === "SEED") {
      return <span className="text-xs text-slate-400">시드(학습 불가)</span>;
    }
    if (row.status === "PENDING" || row.status === "REVIEW") {
      return (
        <div className="flex gap-1 flex-wrap">
          <Button variant="secondary" icon={<Check className="w-3 h-3" />} disabled={acting === row.candidate_id} onClick={(e) => { e.stopPropagation(); handleApprove(row.candidate_id); }}>승인</Button>
          <Button variant="secondary" icon={<X className="w-3 h-3" />} disabled={acting === row.candidate_id} onClick={(e) => { e.stopPropagation(); handleReject(row.candidate_id); }}>반려</Button>
        </div>
      );
    }
    if (row.status === "APPROVED" && row.source_type === "COMPUTED") {
      return (
        <Button variant="secondary" icon={<Play className="w-3 h-3" />} disabled={acting === row.candidate_id} onClick={(e) => { e.stopPropagation(); handleTrain(row.candidate_id); }}>
          재학습 실행
        </Button>
      );
    }
    if (row.status === "TRAINING") {
      return (
        <div className="text-xs text-blue-600 space-y-0.5">
          <div>학습 진행 중 ({row.execution_mode || "AIRFLOW"})</div>
          {row.retraining_dag_run_id && <div className="text-slate-500 truncate max-w-[180px]" title={row.retraining_dag_run_id}>{row.retraining_dag_run_id}</div>}
        </div>
      );
    }
    if (row.status === "TRAINED") {
      return (
        <div className="text-xs text-slate-600 space-y-0.5">
          <div>{row.training_job_id}</div>
          <div>{row.new_model_version_id}</div>
          <Button variant="secondary" icon={<Eye className="w-3 h-3" />} onClick={(e) => { e.stopPropagation(); setDetail(row); }}>결과</Button>
        </div>
      );
    }
    if (row.status === "FAILED") {
      return (
        <div className="text-xs text-red-600 max-w-[200px] truncate" title={row.error_message || ""}>
          {row.error_message || "학습 실패"}
        </div>
      );
    }
    return <span className="text-xs text-slate-500">{row.status}</span>;
  };

  if (loading) return <LoadingState />;
  if (error) return <ErrorState message={error} onRetry={() => load()} />;

  return (
    <div>
      <PageHeader
        title={PAGE_TITLES.retrainingCandidates}
        description={PAGE_DESCRIPTIONS.retrainingCandidates}
      />

      <div className="flex flex-wrap gap-2 mb-4 items-center">
        <Button variant={sourceFilter === "computed" ? "primary" : "secondary"} onClick={() => setSourceFilter("computed")}>자동 산출만</Button>
        <Button variant={sourceFilter === "all" ? "primary" : "secondary"} onClick={() => setSourceFilter("all")}>전체</Button>
        <Button variant={sourceFilter === "seed" ? "primary" : "secondary"} onClick={() => setSourceFilter("seed")}>Seed/Sample</Button>
        <Button variant="secondary" icon={<RefreshCw className="w-3 h-3" />} onClick={() => load(sourceFilter, true)}>새로고침</Button>
      </div>

      {showSeedNotice && (
        <p className="mb-4 text-sm text-amber-700 bg-amber-50 border border-amber-100 rounded px-3 py-2">
          샘플/시드 후보는 시연용이며 Drift 감지로 자동 산출된 운영 후보가 아닙니다. 재학습 실행은 불가합니다.
        </p>
      )}

      <DataTable
        columns={[
          { key: "candidate_id", header: "후보 ID" },
          { key: "source_type", header: "구분", render: (r) => <SourceTypeBadge sourceType={(r.source_type as string) || "SEED"} /> },
          { key: "model_name", header: "모델", render: (r) => `${r.model_name} v${r.model_version}` },
          { key: "site_name", header: "지사" },
          { key: "reason_type", header: "사유 유형", render: (r) => REASON_LABELS[r.reason_type as string] || (r.reason_type as string) },
          { key: "severity", header: "심각도", render: (r) => <StatusBadge status={(r.severity as string) || "MEDIUM"} /> },
          { key: "status", header: "상태", render: (r) => <StatusBadge status={r.status as string} /> },
          { key: "reason_summary", header: "사유" },
          { key: "created_at", header: "등록일", render: (r) => new Date(r.created_at as string).toLocaleDateString("ko-KR") },
          { key: "actions", header: "작업", render: (r) => renderActions(r as unknown as RetrainingCandidate) },
        ]}
        data={items as unknown as Record<string, unknown>[]}
      />

      <Modal open={!!detail} title={`재학습 결과 — ${detail?.candidate_id ?? ""}`} onClose={() => setDetail(null)} footer={<Button variant="secondary" onClick={() => setDetail(null)}>닫기</Button>}>
        {detail && (
          <div className="space-y-3 text-sm">
            <div className="flex gap-2"><StatusBadge status={detail.status} /><SourceTypeBadge sourceType={detail.source_type} /></div>
            <p><strong>Execution Mode:</strong> {detail.execution_mode || "-"}</p>
            <p><strong>DAG Run:</strong> {detail.retraining_dag_run_id || "-"}</p>
            <p><strong>Training Job:</strong> {detail.training_job_id || "-"}</p>
            <p><strong>신규 모델:</strong> {detail.new_model_version_id || "-"}</p>
            <p><strong>MLflow Run:</strong> {detail.mlflow_run_id || "-"}</p>
            <pre className="bg-slate-50 p-3 rounded text-xs overflow-auto max-h-48">{JSON.stringify(detail.train_result_summary, null, 2)}</pre>
          </div>
        )}
      </Modal>
    </div>
  );
}
