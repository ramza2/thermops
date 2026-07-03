import { useEffect, useState } from "react";
import { RotateCcw, Settings } from "lucide-react";
import { fetchApi, postApi, putApi } from "@/api/client";
import { Button } from "@/components/Button";
import { DataTable } from "@/components/DataTable";
import { Modal } from "@/components/Modal";
import { TextInput } from "@/components/SearchPanel";
import { LoadingState, ErrorState } from "@/components/Pagination";
import { useToast } from "@/hooks/useToast";
import { PageHeader } from "@/layouts/MainLayout";
import { MENU_GROUPS, PAGE_DESCRIPTIONS, PAGE_TITLES } from "@/constants/displayLabels";

interface CommonCode {
  code_group: string;
  code: string;
  code_name: string;
}

interface SystemConfig {
  config_key: string;
  config_name: string;
  config_value: string;
  config_type: string;
  description: string;
  editable_yn: boolean;
  updated_at: string | null;
}

export default function SystemConfigPage() {
  const { showToast } = useToast();
  const [codes, setCodes] = useState<CommonCode[]>([]);
  const [configs, setConfigs] = useState<SystemConfig[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [editTarget, setEditTarget] = useState<SystemConfig | null>(null);
  const [editValue, setEditValue] = useState("");
  const [saving, setSaving] = useState(false);
  const [resetting, setResetting] = useState(false);

  const load = async () => {
    setLoading(true);
    setError("");
    try {
      const [codeRes, configRes] = await Promise.all([
        fetchApi<CommonCode[]>("/codes"),
        fetchApi<SystemConfig[]>("/system-configs"),
      ]);
      setCodes(codeRes);
      setConfigs(configRes);
    } catch {
      setError("공통 코드 또는 시스템 설정을 불러오지 못했습니다.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const handleSave = async () => {
    if (!editTarget) return;
    setSaving(true);
    try {
      const updated = await putApi<SystemConfig>(
        `/system-configs/${encodeURIComponent(editTarget.config_key)}`,
        { config_value: editValue },
      );
      setConfigs((prev) =>
        prev.map((c) => (c.config_key === updated.config_key ? updated : c)),
      );
      showToast("success", "시스템 설정이 저장되었습니다.");
      setEditTarget(null);
    } catch {
      showToast("error", "시스템 설정 저장에 실패했습니다.");
    } finally {
      setSaving(false);
    }
  };

  const handleReset = async () => {
    setResetting(true);
    try {
      const res = await postApi<{ reset_count: number; items: SystemConfig[] }>("/system-configs/reset");
      setConfigs((prev) => {
        const map = new Map(res.items.map((i) => [i.config_key, i]));
        return prev.map((c) => map.get(c.config_key) ?? c);
      });
      showToast("success", `시스템 설정 ${res.reset_count}건이 기본값으로 초기화되었습니다.`);
    } catch {
      showToast("error", "시스템 설정 초기화에 실패했습니다.");
    } finally {
      setResetting(false);
    }
  };

  if (loading) return <LoadingState />;
  if (error) return <ErrorState message={error} onRetry={load} />;

  return (
    <div>
      <PageHeader
        title={PAGE_TITLES.systemConfig}
        description={PAGE_DESCRIPTIONS.systemConfig}
        breadcrumbs={[
          { label: MENU_GROUPS.system, path: "/system/configs" },
          { label: "시스템 설정" },
        ]}
        actions={
          <Button
            variant="secondary"
            icon={<RotateCcw className="w-4 h-4" />}
            onClick={handleReset}
            disabled={resetting || !configs.some((c) => c.editable_yn)}
          >
            {resetting ? "초기화 중..." : "기본값 초기화"}
          </Button>
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
        {configs.length === 0 ? (
          <p className="text-sm text-slate-500 py-8 text-center">등록된 시스템 설정이 없습니다.</p>
        ) : (
          <DataTable
            columns={[
              { key: "config_key", header: "설정 키" },
              { key: "config_name", header: "설정명" },
              { key: "config_value", header: "설정값" },
              { key: "config_type", header: "유형" },
              { key: "description", header: "설명" },
              {
                key: "updated_at",
                header: "수정일",
                render: (r) => r.updated_at
                  ? new Date(r.updated_at as string).toLocaleString("ko-KR")
                  : "-",
              },
              {
                key: "actions",
                header: "작업",
                render: (r) => {
                  const row = r as unknown as SystemConfig;
                  if (!row.editable_yn) {
                    return <span className="text-xs text-slate-400">읽기 전용</span>;
                  }
                  return (
                    <Button
                      variant="secondary"
                      onClick={(e) => {
                        e.stopPropagation();
                        setEditTarget(row);
                        setEditValue(row.config_value);
                      }}
                    >
                      수정
                    </Button>
                  );
                },
              },
            ]}
            data={configs as unknown as Record<string, unknown>[]}
          />
        )}
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
              <label className="block text-xs text-slate-500 mb-1">설정명</label>
              <p className="text-sm text-slate-700">{editTarget.config_name}</p>
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
