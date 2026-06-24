import { useEffect, useState } from "react";
import { Plus, Play, Pencil, BarChart2 } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { fetchApi, postApi, putApi } from "@/api/client";
import { Button } from "@/components/Button";
import { DataTable } from "@/components/DataTable";
import { Modal } from "@/components/Modal";
import { SelectInput, TextInput } from "@/components/SearchPanel";
import { LoadingState, ErrorState } from "@/components/Pagination";
import { useToast } from "@/hooks/useToast";
import { PageHeader } from "@/layouts/MainLayout";

interface TrainingConfig {
  config_id: string;
  config_name: string;
  feature_set_id: string;
  algorithm: string;
  train_period_months: number;
  validation_period_months: number;
  active_yn: boolean;
}

const EMPTY = {
  config_name: "",
  feature_set_id: "",
  algorithm: "lightgbm",
  train_period_months: "24",
  validation_period_months: "3",
};

function configToForm(c: TrainingConfig) {
  return {
    config_name: c.config_name,
    feature_set_id: c.feature_set_id,
    algorithm: c.algorithm,
    train_period_months: String(c.train_period_months),
    validation_period_months: String(c.validation_period_months),
  };
}

export default function TrainingConfigsPage() {
  const navigate = useNavigate();
  const { showToast } = useToast();
  const [items, setItems] = useState<TrainingConfig[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [createOpen, setCreateOpen] = useState(false);
  const [editTarget, setEditTarget] = useState<TrainingConfig | null>(null);
  const [runTarget, setRunTarget] = useState<TrainingConfig | null>(null);
  const [form, setForm] = useState(EMPTY);
  const [saving, setSaving] = useState(false);
  const [running, setRunning] = useState(false);

  const load = async () => {
    setLoading(true);
    setError("");
    try {
      const res = await fetchApi<TrainingConfig[]>("/training-configs");
      setItems(res);
    } catch {
      setError("학습 설정 목록을 불러오지 못했습니다.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const buildPayload = () => ({
    config_name: form.config_name,
    feature_set_id: form.feature_set_id,
    algorithm: form.algorithm,
    train_period_months: Number(form.train_period_months),
    validation_period_months: Number(form.validation_period_months),
  });

  const handleCreate = async () => {
    if (!form.config_name.trim() || !form.feature_set_id.trim()) {
      showToast("warning", "설정명과 Feature Set ID를 입력하세요.");
      return;
    }
    setSaving(true);
    try {
      await postApi("/training-configs", buildPayload());
      showToast("success", "학습 설정이 등록되었습니다.");
      setCreateOpen(false);
      setForm(EMPTY);
      load();
    } catch {
      showToast("error", "등록에 실패했습니다.");
    } finally {
      setSaving(false);
    }
  };

  const handleUpdate = async () => {
    if (!editTarget || !form.config_name.trim() || !form.feature_set_id.trim()) {
      showToast("warning", "설정명과 Feature Set ID를 입력하세요.");
      return;
    }
    setSaving(true);
    try {
      await putApi(`/training-configs/${editTarget.config_id}`, buildPayload());
      showToast("success", "학습 설정이 수정되었습니다.");
      setEditTarget(null);
      load();
    } catch {
      showToast("error", "수정에 실패했습니다.");
    } finally {
      setSaving(false);
    }
  };

  const handleRunTraining = async () => {
    if (!runTarget) return;
    setRunning(true);
    try {
      await postApi("/training-jobs", { config_id: runTarget.config_id, register_model_yn: true });
      showToast("success", "모델 학습이 실행 요청되었습니다.");
      setRunTarget(null);
      navigate("/models/training-jobs");
    } catch {
      showToast("error", "학습 실행에 실패했습니다.");
    } finally {
      setRunning(false);
    }
  };

  const configForm = (
    <div className="space-y-3">
      <div>
        <label className="block text-xs text-slate-500 mb-1">설정명</label>
        <TextInput value={form.config_name} onChange={(v) => setForm({ ...form, config_name: v })} />
      </div>
      <div>
        <label className="block text-xs text-slate-500 mb-1">Feature Set ID</label>
        <TextInput value={form.feature_set_id} onChange={(v) => setForm({ ...form, feature_set_id: v })} placeholder="FS-XXXXXX" />
      </div>
      <div>
        <label className="block text-xs text-slate-500 mb-1">알고리즘</label>
        <SelectInput value={form.algorithm} onChange={(v) => setForm({ ...form, algorithm: v })}
          options={[
            { value: "lightgbm", label: "LightGBM" },
            { value: "xgboost", label: "XGBoost" },
            { value: "baseline", label: "Baseline" },
          ]} />
      </div>
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="block text-xs text-slate-500 mb-1">학습 기간(월)</label>
          <TextInput value={form.train_period_months} onChange={(v) => setForm({ ...form, train_period_months: v })} />
        </div>
        <div>
          <label className="block text-xs text-slate-500 mb-1">검증 기간(월)</label>
          <TextInput value={form.validation_period_months} onChange={(v) => setForm({ ...form, validation_period_months: v })} />
        </div>
      </div>
    </div>
  );

  if (loading) return <LoadingState />;
  if (error) return <ErrorState message={error} onRetry={load} />;

  return (
    <div>
      <PageHeader
        title="모델 학습 설정"
        description="알고리즘, Feature Set, 학습 기간 등 학습 파라미터를 관리합니다."
        breadcrumbs={[
          { label: "모델 관리", path: "/models/training-configs" },
          { label: "학습 설정" },
        ]}
        actions={<Button icon={<Plus className="w-4 h-4" />} onClick={() => { setForm(EMPTY); setCreateOpen(true); }}>신규 설정</Button>}
      />

      <DataTable
        columns={[
          { key: "config_id", header: "ID", width: "120px" },
          { key: "config_name", header: "설정명" },
          { key: "feature_set_id", header: "Feature Set" },
          { key: "algorithm", header: "알고리즘" },
          { key: "train_period_months", header: "학습(월)" },
          { key: "validation_period_months", header: "검증(월)" },
          {
            key: "actions", header: "작업", render: (r) => {
              const row = r as unknown as TrainingConfig;
              return (
                <div className="flex flex-wrap gap-1" onClick={(e) => e.stopPropagation()}>
                  <Button variant="secondary" icon={<Pencil className="w-3 h-3" />}
                    onClick={() => { setEditTarget(row); setForm(configToForm(row)); }}>수정</Button>
                  <Button variant="secondary" icon={<BarChart2 className="w-3 h-3" />}
                    onClick={() => navigate("/models/performance")}>성능 보기</Button>
                  <Button variant="primary" icon={<Play className="w-3 h-3" />}
                    onClick={() => setRunTarget(row)}>학습 실행</Button>
                </div>
              );
            },
          },
        ]}
        data={items as unknown as Record<string, unknown>[]}
      />

      <Modal open={createOpen} title="학습 설정 등록" onClose={() => setCreateOpen(false)}
        footer={<>
          <Button variant="secondary" onClick={() => setCreateOpen(false)}>취소</Button>
          <Button onClick={handleCreate} disabled={saving}>{saving ? "저장 중..." : "저장"}</Button>
        </>}>
        {configForm}
      </Modal>

      <Modal open={!!editTarget} title="학습 설정 수정" onClose={() => setEditTarget(null)}
        footer={<>
          <Button variant="secondary" onClick={() => setEditTarget(null)}>취소</Button>
          <Button onClick={handleUpdate} disabled={saving}>{saving ? "저장 중..." : "저장"}</Button>
        </>}>
        {configForm}
      </Modal>

      <Modal open={!!runTarget} title="학습 실행 확인" onClose={() => setRunTarget(null)}
        footer={<>
          <Button variant="secondary" onClick={() => setRunTarget(null)}>취소</Button>
          <Button icon={<Play className="w-4 h-4" />} onClick={handleRunTraining} disabled={running}>{running ? "실행 중..." : "학습 실행"}</Button>
        </>}>
        <p className="text-sm text-slate-600">
          <strong>{runTarget?.config_name}</strong> 설정으로 모델 학습 파이프라인을 실행하시겠습니까?
        </p>
        <p className="text-xs text-slate-400 mt-2">실행 후 학습 작업 화면으로 이동합니다.</p>
      </Modal>
    </div>
  );
}
