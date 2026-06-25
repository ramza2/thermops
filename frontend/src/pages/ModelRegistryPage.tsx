import { useEffect, useState } from "react";
import { Award, Eye } from "lucide-react";
import { fetchApi, postApi } from "@/api/client";
import { Button } from "@/components/Button";
import { DataTable } from "@/components/DataTable";
import { Modal } from "@/components/Modal";
import { StatusBadge } from "@/components/StatusBadge";
import { LoadingState, ErrorState } from "@/components/Pagination";
import { useToast } from "@/hooks/useToast";
import { PageHeader } from "@/layouts/MainLayout";

interface ModelSummary {
  model_name: string;
  latest_version: string | null;
  champion_version: string | null;
  version_count: number;
}

interface ModelVersionRow {
  model_version_id: string;
  model_name: string;
  version: string;
  model_stage: string;
  mlflow_model_uri: string | null;
  artifact_uri?: string | null;
  metrics: { mae?: number; rmse?: number; mape?: number; r2?: number };
  registered_at: string;
}

export default function ModelRegistryPage() {
  const { showToast } = useToast();
  const [items, setItems] = useState<ModelVersionRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [detail, setDetail] = useState<ModelVersionRow | null>(null);
  const [championTarget, setChampionTarget] = useState<ModelVersionRow | null>(null);
  const [promoting, setPromoting] = useState(false);

  const load = async () => {
    setLoading(true);
    setError("");
    try {
      const models = await fetchApi<ModelSummary[]>("/models");
      const versionLists = await Promise.all(
        models.map((m) =>
          fetchApi<ModelVersionRow[]>(`/models/${encodeURIComponent(m.model_name)}/versions`).catch(() => []),
        ),
      );
      setItems(versionLists.flat());
    } catch {
      setError("모델 Registry를 불러오지 못했습니다.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const handleDetail = async (row: ModelVersionRow) => {
    try {
      const res = await fetchApi<ModelVersionRow>(
        `/models/${encodeURIComponent(row.model_name)}/versions/${encodeURIComponent(row.version)}`,
      );
      setDetail(res);
    } catch {
      setDetail(row);
    }
  };

  const handleChampion = async () => {
    if (!championTarget) return;
    setPromoting(true);
    try {
      await postApi(
        `/models/${encodeURIComponent(championTarget.model_name)}/versions/${encodeURIComponent(championTarget.version)}/champion`,
        { reason: "운영 모델 변경" },
      );
      showToast("success", "Champion 모델이 지정되었습니다.");
      setChampionTarget(null);
      load();
    } catch {
      showToast("error", "Champion 지정에 실패했습니다.");
    } finally {
      setPromoting(false);
    }
  };

  if (loading) return <LoadingState />;
  if (error) return <ErrorState message={error} onRetry={load} />;

  return (
    <div>
      <PageHeader title="모델 Registry 관리" description="등록된 모델 버전과 운영(Champion) 모델을 관리합니다." />

      <DataTable
        columns={[
          { key: "model_name", header: "모델명" },
          { key: "version", header: "버전" },
          { key: "model_stage", header: "상태", render: (r) => <StatusBadge status={r.model_stage as string} /> },
          {
            key: "mape",
            header: "MAPE(%)",
            render: (r) => {
              const m = r.metrics as ModelVersionRow["metrics"];
              return m?.mape != null ? `${m.mape}%` : "-";
            },
          },
          { key: "registered_at", header: "등록일", render: (r) => new Date(r.registered_at as string).toLocaleDateString("ko-KR") },
          {
            key: "actions",
            header: "작업",
            render: (r) => {
              const row = r as unknown as ModelVersionRow;
              return (
                <div className="flex gap-2" onClick={(e) => e.stopPropagation()}>
                  <Button variant="ghost" icon={<Eye className="w-3 h-3" />} onClick={() => handleDetail(row)}>
                    상세
                  </Button>
                  {row.model_stage !== "CHAMPION" && (
                    <Button variant="secondary" icon={<Award className="w-3 h-3" />} onClick={() => setChampionTarget(row)}>
                      Champion 지정
                    </Button>
                  )}
                </div>
              );
            },
          },
        ]}
        data={items as unknown as Record<string, unknown>[]}
      />

      <Modal
        open={!!detail}
        title="모델 상세"
        onClose={() => setDetail(null)}
        size="lg"
        footer={<Button variant="secondary" onClick={() => setDetail(null)}>닫기</Button>}
      >
        {detail && (
          <dl className="grid grid-cols-2 gap-3 text-sm">
            <div><dt className="text-slate-500">모델명</dt><dd className="font-medium">{detail.model_name}</dd></div>
            <div><dt className="text-slate-500">버전</dt><dd className="font-medium">{detail.version}</dd></div>
            <div><dt className="text-slate-500">상태</dt><dd><StatusBadge status={detail.model_stage} /></dd></div>
            <div><dt className="text-slate-500">등록일</dt><dd>{new Date(detail.registered_at).toLocaleString("ko-KR")}</dd></div>
            <div className="col-span-2"><dt className="text-slate-500">MLflow URI</dt><dd className="break-all text-xs mt-1">{detail.mlflow_model_uri || "-"}</dd></div>
            <div className="col-span-2"><dt className="text-slate-500">Artifact URI</dt><dd className="break-all text-xs mt-1">{detail.artifact_uri || "-"}</dd></div>
            <div><dt className="text-slate-500">MAE</dt><dd>{detail.metrics?.mae ?? "-"}</dd></div>
            <div><dt className="text-slate-500">RMSE</dt><dd>{detail.metrics?.rmse ?? "-"}</dd></div>
            <div><dt className="text-slate-500">MAPE</dt><dd>{detail.metrics?.mape != null ? `${detail.metrics.mape}%` : "-"}</dd></div>
            <div><dt className="text-slate-500">R²</dt><dd>{detail.metrics?.r2 != null ? detail.metrics.r2.toFixed(4) : "-"}</dd></div>
          </dl>
        )}
      </Modal>

      <Modal
        open={!!championTarget}
        title="Champion 모델 지정"
        onClose={() => setChampionTarget(null)}
        footer={
          <>
            <Button variant="secondary" onClick={() => setChampionTarget(null)}>취소</Button>
            <Button icon={<Award className="w-4 h-4" />} onClick={handleChampion} disabled={promoting}>
              {promoting ? "처리 중..." : "지정"}
            </Button>
          </>
        }
      >
        <p className="text-sm text-slate-600">
          <strong>{championTarget?.model_name} v{championTarget?.version}</strong>을(를) 운영(Champion) 모델로 지정하시겠습니까?
        </p>
        <p className="text-xs text-amber-600 mt-2">기존 Champion 모델은 후보(Candidate) 상태로 변경됩니다.</p>
      </Modal>
    </div>
  );
}
