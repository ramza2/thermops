import { useEffect, useState } from "react";
import { RotateCcw, Save, Settings } from "lucide-react";
import { fetchApi } from "@/api/client";
import { Button } from "@/components/Button";
import { DataTable } from "@/components/DataTable";
import { Modal } from "@/components/Modal";
import { TextInput } from "@/components/SearchPanel";
import { LoadingState, ErrorState } from "@/components/Pagination";
import { useToast } from "@/hooks/useToast";
import { PageHeader } from "@/layouts/MainLayout";

/**
 * TODO: 백엔드 API 연동 필요
 * - GET  /api/v1/system-configs
 * - PUT  /api/v1/system-configs/{config_key}
 * - POST /api/v1/system-configs/reset (선택)
 */

interface CommonCode {
  code_group: string;
  code: string;
  code_name: string;
}

interface SystemConfig {
  config_key: string;
  config_value: string;
  config_type: string;
  scope: string;
  description: string;
}

const DEFAULT_CONFIGS: SystemConfig[] = [
  { config_key: "default_champion_model", config_value: "heat_demand_lgbm", config_type: "STRING", scope: "GLOBAL", description: "기본 Champion 모델명" },
  { config_key: "mape_alert_threshold", config_value: "6.0", config_type: "NUMBER", scope: "GLOBAL", description: "MAPE 알림 임계치(%)" },
  { config_key: "drift_score_threshold", config_value: "0.35", config_type: "NUMBER", scope: "GLOBAL", description: "드리프트 점수 임계치" },
];

export default function SystemConfigPage() {
  const { showToast } = useToast();
  const [codes, setCodes] = useState<CommonCode[]>([]);
  const [configs, setConfigs] = useState<SystemConfig[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [editTarget, setEditTarget] = useState<SystemConfig | null>(null);
  const [editValue, setEditValue] = useState("");
  const [saving, setSaving] = useState(false);

  const load = async () => {
    setLoading(true);
    setError("");
    try {
      const codeRes = await fetchApi<CommonCode[]>("/codes");
      setCodes(codeRes);
      const stored = localStorage.getItem("thermops_system_configs");
      setConfigs(stored ? JSON.parse(stored) as SystemConfig[] : DEFAULT_CONFIGS);
    } catch {
      setError("공통 코드를 불러오지 못했습니다.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const persistConfigs = (next: SystemConfig[]) => {
    setConfigs(next);
    localStorage.setItem("thermops_system_configs", JSON.stringify(next));
  };

  const handleSave = async () => {
    if (!editTarget) return;
    setSaving(true);
    try {
      const next = configs.map((c) =>
        c.config_key === editTarget.config_key ? { ...c, config_value: editValue } : c,
      );
      persistConfigs(next);
      showToast("success", "시스템 설정이 저장되었습니다.");
      setEditTarget(null);
    } finally {
      setSaving(false);
    }
  };

  const handleSaveAll = () => {
    persistConfigs(configs);
    showToast("success", "모든 설정이 저장되었습니다.");
  };

  const handleReset = () => {
    persistConfigs(DEFAULT_CONFIGS);
    showToast("success", "시스템 설정이 초기값으로 복원되었습니다.");
  };

  if (loading) return <LoadingState />;
  if (error) return <ErrorState message={error} onRetry={load} />;

  return (
    <div>
      <PageHeader
        title="공통 코드/설정 관리"
        description="공통 코드와 시스템 운영 설정을 조회·수정합니다."
        breadcrumbs={[
          { label: "운영 관리", path: "/ops/pipeline-runs" },
          { label: "공통 코드/설정" },
        ]}
        actions={
          <>
            <Button variant="secondary" icon={<RotateCcw className="w-4 h-4" />} onClick={handleReset}>초기화</Button>
            <Button icon={<Save className="w-4 h-4" />} onClick={handleSaveAll}>저장</Button>
          </>
        }
      />

      <div className="mb-6">
        <h2 className="text-sm font-semibold text-slate-800 mb-2 flex items-center gap-2">
          <Settings className="w-4 h-4" /> 공통 코드 목록
        </h2>
        <DataTable
          columns={[
            { key: "code_group", header: "코드 그룹" },
            { key: "code", header: "코드" },
            { key: "code_name", header: "코드명" },
          ]}
          data={codes as unknown as Record<string, unknown>[]}
        />
      </div>

      <div>
        <h2 className="text-sm font-semibold text-slate-800 mb-2">시스템 설정 목록</h2>
        <p className="text-xs text-amber-600 mb-2">※ 시스템 설정 API 미구현 — Mock 데이터 + localStorage 저장 (TODO: GET/PUT /system-configs)</p>
        <DataTable
          columns={[
            { key: "config_key", header: "설정 키" },
            { key: "config_value", header: "설정값" },
            { key: "config_type", header: "유형" },
            { key: "scope", header: "범위" },
            { key: "description", header: "설명" },
            {
              key: "actions", header: "작업", render: (r) => {
                const row = r as unknown as SystemConfig;
                return (
                  <Button variant="secondary" onClick={(e) => {
                    e.stopPropagation();
                    setEditTarget(row);
                    setEditValue(row.config_value);
                  }}>수정</Button>
                );
              },
            },
          ]}
          data={configs as unknown as Record<string, unknown>[]}
        />
      </div>

      <Modal
        open={!!editTarget}
        title="설정값 수정"
        onClose={() => setEditTarget(null)}
        footer={
          <>
            <Button variant="secondary" onClick={() => setEditTarget(null)}>취소</Button>
            <Button onClick={handleSave} disabled={saving}>{saving ? "저장 중..." : "저장"}</Button>
          </>
        }
      >
        {editTarget && (
          <div className="space-y-3">
            <div>
              <label className="block text-xs text-slate-500 mb-1">설정 키</label>
              <p className="text-sm font-medium">{editTarget.config_key}</p>
            </div>
            <div>
              <label className="block text-xs text-slate-500 mb-1">설명</label>
              <p className="text-sm text-slate-600">{editTarget.description}</p>
            </div>
            <div>
              <label className="block text-xs text-slate-500 mb-1">설정값</label>
              <TextInput value={editValue} onChange={setEditValue} />
            </div>
          </div>
        )}
      </Modal>
    </div>
  );
}
