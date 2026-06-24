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

export default function PredictionJobsPage() {
  const navigate = useNavigate();
  const { showToast } = useToast();
  const [sites, setSites] = useState<Site[]>([]);
  const [loading, setLoading] = useState(true);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [running, setRunning] = useState(false);
  const [form, setForm] = useState({
    site_id: "",
    target_start: "",
    target_end: "",
    prediction_horizon: "D_PLUS_1",
  });

  useEffect(() => {
    fetchApi<Site[]>("/sites").then((res) => {
      setSites(res);
      if (res.length) setForm((f) => ({ ...f, site_id: res[0].site_id }));
    }).finally(() => setLoading(false));
  }, []);

  const handleRun = async () => {
    if (!form.site_id || !form.target_start || !form.target_end) {
      showToast("warning", "지사와 예측 기간을 입력하세요.");
      return;
    }
    setRunning(true);
    try {
      const res = await postApi<{ job_id: string; pipeline_run_id: string }>("/prediction-jobs", {
        site_ids: [form.site_id],
        target_start_at: new Date(form.target_start).toISOString(),
        target_end_at: new Date(form.target_end).toISOString(),
        prediction_horizon: form.prediction_horizon,
      });
      showToast("success", `배치 예측이 실행되었습니다. (${res.job_id})`);
      setConfirmOpen(false);
      navigate("/ops/pipeline-runs");
    } catch {
      showToast("error", "예측 실행에 실패했습니다.");
    } finally {
      setRunning(false);
    }
  };

  if (loading) return <LoadingState />;

  return (
    <div>
      <PageHeader title="배치 예측 실행" description="Champion 모델로 열수요 배치 예측을 실행합니다." />

      <div className="bg-white rounded-lg border border-slate-200 p-6 shadow-sm max-w-xl">
        <div className="space-y-4">
          <div>
            <label className="block text-xs text-slate-500 mb-1">지사</label>
            <SelectInput value={form.site_id} onChange={(v) => setForm({ ...form, site_id: v })}
              options={sites.map((s) => ({ value: s.site_id, label: s.site_name }))} />
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
        <p className="text-sm text-slate-600">선택한 조건으로 배치 예측 파이프라인을 실행하시겠습니까?</p>
        <ul className="text-xs text-slate-500 mt-3 space-y-1">
          <li>지사: {sites.find((s) => s.site_id === form.site_id)?.site_name}</li>
          <li>기간: {form.target_start || "-"} ~ {form.target_end || "-"}</li>
          <li>구간: {form.prediction_horizon}</li>
        </ul>
        <p className="text-xs text-slate-400 mt-2">실행 후 파이프라인 실행 이력 화면으로 이동합니다.</p>
      </Modal>
    </div>
  );
}
