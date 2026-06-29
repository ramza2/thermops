import { useEffect, useState } from "react";
import { Play } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { fetchApi, postApi } from "@/api/client";
import { Button } from "@/components/Button";
import { Modal } from "@/components/Modal";
import { SelectInput } from "@/components/SearchPanel";
import { LoadingState } from "@/components/Pagination";
import { useToast } from "@/hooks/useToast";
import { PageHeader } from "@/layouts/MainLayout";

interface Site {
  site_id: string;
  site_name: string;
}

interface FeatureSet {
  feature_set_id: string;
  feature_set_name: string;
}

interface ModelSummary {
  model_name: string;
  latest_version: string | null;
  champion_version: string | null;
}

interface ModelVersionRow {
  model_version_id: string;
  model_name: string;
  version: string;
  model_stage: string;
}

interface PredictionJobResult {
  job_id: string;
  status: string;
  predicted_count?: number;
  model_version_id?: string;
  model_name?: string;
  model_version?: string;
  result_summary?: {
    model_stage?: string;
    warnings?: string[];
  };
}

export default function PredictionJobsPage() {
  const navigate = useNavigate();
  const { showToast } = useToast();
  const [sites, setSites] = useState<Site[]>([]);
  const [featureSets, setFeatureSets] = useState<FeatureSet[]>([]);
  const [modelVersions, setModelVersions] = useState<ModelVersionRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [running, setRunning] = useState(false);
  const [form, setForm] = useState({
    site_id: "",
    feature_set_id: "FS-TPL-LAG-ROLL",
    model_version_id: "",
    target_start: "",
    target_end: "",
    prediction_horizon: "BATCH",
  });

  useEffect(() => {
    Promise.all([
      fetchApi<Site[]>("/sites"),
      fetchApi<FeatureSet[]>("/feature-sets"),
      fetchApi<ModelSummary[]>("/models"),
    ])
      .then(async ([siteRes, fsRes, modelRes]) => {
        setSites(siteRes);
        setFeatureSets(fsRes);
        if (siteRes.length) setForm((f) => ({ ...f, site_id: siteRes[0].site_id }));
        if (fsRes.length) {
          const preferred = fsRes.find((f) => f.feature_set_id === "FS-TPL-LAG-ROLL") || fsRes[0];
          setForm((f) => ({ ...f, feature_set_id: preferred.feature_set_id }));
        }

        const versionLists = await Promise.all(
          modelRes.map((m) =>
            fetchApi<ModelVersionRow[]>(`/models/${encodeURIComponent(m.model_name)}/versions`).catch(() => []),
          ),
        );
        const flat = versionLists.flat();
        setModelVersions(flat);
        const champion = flat.find((v) => v.model_stage === "CHAMPION")
          || flat.find((v) => v.model_stage === "CANDIDATE")
          || flat[0];
        if (champion) setForm((f) => ({ ...f, model_version_id: champion.model_version_id }));
      })
      .finally(() => setLoading(false));
  }, []);

  const handleRun = async () => {
    if (!form.feature_set_id || !form.target_start || !form.target_end) {
      showToast("warning", "Feature Set과 예측 기간을 입력하세요.");
      return;
    }
    setRunning(true);
    try {
      const body: Record<string, unknown> = {
        feature_set_id: form.feature_set_id,
        start_at: new Date(form.target_start).toISOString(),
        end_at: new Date(form.target_end).toISOString(),
        prediction_horizon: form.prediction_horizon,
        overwrite_yn: true,
      };
      if (form.site_id) body.site_ids = [form.site_id];
      if (form.model_version_id) body.model_version_id = form.model_version_id;

      const res = await postApi<PredictionJobResult>("/prediction-jobs", body);
      const modelLabel = res.model_name
        ? `${res.model_name} v${res.model_version}`
        : res.model_version_id || "-";
      showToast(
        "success",
        `배치 예측 완료: ${res.predicted_count ?? 0}건 (${modelLabel})`,
      );
      setConfirmOpen(false);
      navigate("/predictions/results");
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      showToast("error", typeof detail === "string" ? detail : "예측 실행에 실패했습니다.");
    } finally {
      setRunning(false);
    }
  };

  if (loading) return <LoadingState />;

  const selectedModel = modelVersions.find((m) => m.model_version_id === form.model_version_id);

  return (
    <div>
      <PageHeader title="배치 예측 실행" description="학습된 모델로 Feature Dataset 기반 배치 예측을 실행합니다." />

      <div className="bg-white rounded-lg border border-slate-200 p-6 shadow-sm max-w-xl">
        <div className="space-y-4">
          <div>
            <label className="block text-xs text-slate-500 mb-1">Feature Set</label>
            <SelectInput value={form.feature_set_id} onChange={(v) => setForm({ ...form, feature_set_id: v })}
              options={featureSets.map((f) => ({ value: f.feature_set_id, label: f.feature_set_name }))} />
          </div>
          <div>
            <label className="block text-xs text-slate-500 mb-1">모델 버전</label>
            <SelectInput value={form.model_version_id} onChange={(v) => setForm({ ...form, model_version_id: v })}
              options={[
                { value: "", label: "자동 (Champion → CANDIDATE)" },
                ...modelVersions.map((m) => ({
                  value: m.model_version_id,
                  label: `${m.model_name} v${m.version} (${m.model_stage})`,
                })),
              ]} />
            {selectedModel && (
              <p className="text-xs text-slate-400 mt-1">선택: {selectedModel.model_name} v{selectedModel.version}</p>
            )}
          </div>
          <div>
            <label className="block text-xs text-slate-500 mb-1">지사 (선택)</label>
            <SelectInput value={form.site_id} onChange={(v) => setForm({ ...form, site_id: v })}
              options={[{ value: "", label: "전체" }, ...sites.map((s) => ({ value: s.site_id, label: s.site_name }))]} />
          </div>
          <div>
            <label className="block text-xs text-slate-500 mb-1">예측 기간 시작</label>
            <input type="datetime-local" value={form.target_start}
              onChange={(e) => setForm({ ...form, target_start: e.target.value })}
              className="w-full border border-slate-200 rounded-md px-2 py-1.5 text-sm bg-slate-50" />
          </div>
          <div>
            <label className="block text-xs text-slate-500 mb-1">예측 기간 종료</label>
            <input type="datetime-local" value={form.target_end}
              onChange={(e) => setForm({ ...form, target_end: e.target.value })}
              className="w-full border border-slate-200 rounded-md px-2 py-1.5 text-sm bg-slate-50" />
          </div>
          <div>
            <label className="block text-xs text-slate-500 mb-1">예측 구간</label>
            <SelectInput value={form.prediction_horizon} onChange={(v) => setForm({ ...form, prediction_horizon: v })}
              options={[
                { value: "BATCH", label: "배치 (Feature 기간)" },
                { value: "D_PLUS_1", label: "D+1 (익일)" },
                { value: "D_PLUS_3", label: "D+3" },
                { value: "D_PLUS_7", label: "D+7" },
              ]} />
          </div>
          <div className="pt-2">
            <Button icon={<Play className="w-4 h-4" />} onClick={() => setConfirmOpen(true)}>예측 실행</Button>
          </div>
        </div>
      </div>

      <Modal open={confirmOpen} title="배치 예측 실행 확인" onClose={() => setConfirmOpen(false)}
        footer={<>
          <Button variant="secondary" onClick={() => setConfirmOpen(false)}>취소</Button>
          <Button icon={<Play className="w-4 h-4" />} onClick={handleRun} disabled={running}>{running ? "실행 중..." : "실행"}</Button>
        </>}>
        <p className="text-sm text-slate-600">선택한 조건으로 배치 예측을 실행하시겠습니까?</p>
        <ul className="text-xs text-slate-500 mt-3 space-y-1">
          <li>Feature Set: {form.feature_set_id}</li>
          <li>모델: {selectedModel ? `${selectedModel.model_name} v${selectedModel.version}` : "자동 선택"}</li>
          <li>지사: {form.site_id ? sites.find((s) => s.site_id === form.site_id)?.site_name : "전체"}</li>
          <li>기간: {form.target_start || "-"} ~ {form.target_end || "-"}</li>
        </ul>
        <p className="text-xs text-slate-400 mt-2">완료 후 예측 결과 화면으로 이동합니다.</p>
      </Modal>
    </div>
  );
}
