import { useEffect, useState } from "react";
import { RefreshCw } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { fetchApi, postApi } from "@/api/client";
import { Button } from "@/components/Button";
import { DataTable } from "@/components/DataTable";
import { Modal } from "@/components/Modal";
import { StatusBadge } from "@/components/StatusBadge";
import { LoadingState, ErrorState } from "@/components/Pagination";
import { useToast } from "@/hooks/useToast";
import { PageHeader } from "@/layouts/MainLayout";

interface RetrainingCandidate {
  candidate_id: string;
  reason: string;
  model_name: string;
  model_version: string;
  site_id: string | null;
  site_name: string;
  risk_level: string;
  status: string;
  created_at: string;
}

interface TrainingConfig {
  config_id: string;
  config_name: string;
}

export default function RetrainingCandidatesPage() {
  const navigate = useNavigate();
  const { showToast } = useToast();
  const [items, setItems] = useState<RetrainingCandidate[]>([]);
  const [configs, setConfigs] = useState<TrainingConfig[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [requestTarget, setRequestTarget] = useState<RetrainingCandidate | null>(null);
  const [requesting, setRequesting] = useState(false);

  const load = async () => {
    setLoading(true);
    setError("");
    try {
      const [candidates, trainingConfigs] = await Promise.all([
        fetchApi<RetrainingCandidate[]>("/retraining-candidates"),
        fetchApi<TrainingConfig[]>("/training-configs"),
      ]);
      setItems(candidates);
      setConfigs(trainingConfigs);
    } catch {
      setError("재학습 후보 목록을 불러오지 못했습니다.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const handleRequest = async () => {
    if (!requestTarget) return;
    const configId = configs[0]?.config_id;
    if (!configId) {
      showToast("warning", "학습 설정이 없습니다. 먼저 학습 설정을 등록하세요.");
      return;
    }
    setRequesting(true);
    try {
      await postApi("/training-jobs", {
        config_id: configId,
        triggered_by: `retraining:${requestTarget.candidate_id}`,
        site_ids: requestTarget.site_id ? [requestTarget.site_id] : undefined,
      });
      showToast("success", "재학습이 요청되었습니다.");
      setRequestTarget(null);
      navigate("/models/training-jobs");
    } catch {
      showToast("error", "재학습 요청에 실패했습니다.");
    } finally {
      setRequesting(false);
    }
  };

  if (loading) return <LoadingState />;
  if (error) return <ErrorState message={error} onRetry={load} />;

  return (
    <div>
      <PageHeader title="재학습 후보 관리" description="성능 저하 및 드리프트로 인한 재학습 후보를 검토합니다." />

      <DataTable
        columns={[
          { key: "candidate_id", header: "후보 ID" },
          { key: "model_name", header: "모델", render: (r) => `${r.model_name} v${r.model_version}` },
          { key: "site_name", header: "지사" },
          { key: "reason", header: "사유" },
          { key: "risk_level", header: "위험도", render: (r) => <StatusBadge status={r.risk_level as string} /> },
          { key: "status", header: "상태", render: (r) => <StatusBadge status={r.status as string} /> },
          { key: "created_at", header: "등록일", render: (r) => new Date(r.created_at as string).toLocaleDateString("ko-KR") },
          {
            key: "actions", header: "작업", render: (r) => {
              const row = r as unknown as RetrainingCandidate;
              if (row.status === "REQUESTED") return <span className="text-xs text-blue-600">요청완료</span>;
              return (
                <Button variant="secondary" icon={<RefreshCw className="w-3 h-3" />} onClick={(e) => { e.stopPropagation(); setRequestTarget(row); }}>
                  재학습 요청
                </Button>
              );
            },
          },
        ]}
        data={items as unknown as Record<string, unknown>[]}
      />

      <Modal open={!!requestTarget} title="재학습 요청 확인" onClose={() => setRequestTarget(null)}
        footer={<>
          <Button variant="secondary" onClick={() => setRequestTarget(null)}>취소</Button>
          <Button icon={<RefreshCw className="w-4 h-4" />} onClick={handleRequest} disabled={requesting}>{requesting ? "요청 중..." : "재학습 요청"}</Button>
        </>}>
        <p className="text-sm text-slate-600">
          <strong>{requestTarget?.model_name} v{requestTarget?.model_version}</strong> ({requestTarget?.site_name})에 대한 재학습을 요청하시겠습니까?
        </p>
        <p className="text-xs text-slate-500 mt-2">사유: {requestTarget?.reason}</p>
        <p className="text-xs text-slate-400 mt-2">요청 후 학습 작업 화면으로 이동합니다.</p>
      </Modal>
    </div>
  );
}
