import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Award, Eye, Plus, Copy, Trash2 } from "lucide-react";
import { deleteApi, fetchApi, postApi } from "@/api/client";
import { Button } from "@/components/Button";
import { DataTable } from "@/components/DataTable";
import { Modal } from "@/components/Modal";
import { SelectInput, TextInput } from "@/components/SearchPanel";
import { LoadingState, ErrorState } from "@/components/Pagination";
import { useToast } from "@/hooks/useToast";
import { useRole } from "@/hooks/useRole";
import { PermissionDeniedModal } from "@/components/PermissionDeniedModal";
import { PageHeader } from "@/layouts/MainLayout";
import { EMPTY_MESSAGES, PAGE_DESCRIPTIONS, PAGE_TITLES } from "@/constants/displayLabels";
import { FeatureSet, toFeatureSetPayload } from "@/types/featureSet";

const EMPTY_FORM = {
  feature_set_name: "",
  target_domain: "HEAT_DEMAND",
  apply_site_scope: "ALL",
  features: [] as string[],
  text: "",
  missingHandling: "PREV",
  normalize: false,
};

export default function FeatureSetsPage() {
  const navigate = useNavigate();
  const { showToast } = useToast();
  const { canEdit } = useRole();
  const [items, setItems] = useState<FeatureSet[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [createOpen, setCreateOpen] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<FeatureSet | null>(null);
  const [permissionDenied, setPermissionDenied] = useState(false);
  const [form, setForm] = useState(EMPTY_FORM);
  const [saving, setSaving] = useState(false);

  const load = async () => {
    setLoading(true);
    setError("");
    try {
      const res = await fetchApi<FeatureSet[]>("/feature-sets");
      setItems(res);
    } catch {
      setError("Feature Set 목록을 불러오지 못했습니다.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const handleCreate = async () => {
    if (!form.feature_set_name.trim()) {
      showToast("warning", "Feature Set 명을 입력하세요.");
      return;
    }
    setSaving(true);
    try {
      const res = await postApi<{ feature_set_id: string }>("/feature-sets", toFeatureSetPayload(form));
      showToast("success", "Feature Set이 등록되었습니다.");
      setCreateOpen(false);
      setForm(EMPTY_FORM);
      navigate(`/feature-sets/${res.feature_set_id}`);
    } catch {
      showToast("error", "등록에 실패했습니다.");
    } finally {
      setSaving(false);
    }
  };

  const handleCopy = async (row: FeatureSet) => {
    try {
      const res = await postApi<{ feature_set_id: string }>("/feature-sets", {
        feature_set_name: `${row.feature_set_name}_copy`,
        target_domain: row.target_domain,
        features: row.features,
        apply_site_scope: row.apply_site_scope,
        description: row.description,
      });
      showToast("success", "Feature Set이 복사되었습니다.");
      load();
      navigate(`/feature-sets/${res.feature_set_id}`);
    } catch {
      showToast("error", "복사에 실패했습니다.");
    }
  };

  const handleDelete = async () => {
    if (!deleteTarget) return;
    try {
      await deleteApi(`/feature-sets/${deleteTarget.feature_set_id}`);
      showToast("success", "Feature Set이 삭제되었습니다.");
      setDeleteTarget(null);
      load();
    } catch {
      showToast("error", "삭제에 실패했습니다.");
    }
  };

  if (loading) return <LoadingState />;
  if (error) return <ErrorState message={error} onRetry={load} />;

  return (
    <div>
      <PageHeader
        title={PAGE_TITLES.featureSets}
        description={PAGE_DESCRIPTIONS.featureSets}
        breadcrumbs={[
          { label: "학습 변수 관리", path: "/features" },
          { label: "변수 구성" },
        ]}
        actions={
          <Button
            icon={<Plus className="w-4 h-4" />}
            disabled={!canEdit}
            title={!canEdit ? "VIEWER 권한으로는 생성할 수 없습니다" : undefined}
            onClick={() => {
              if (!canEdit) { setPermissionDenied(true); return; }
              setForm(EMPTY_FORM);
              setCreateOpen(true);
            }}
          >
            신규 변수 구성
          </Button>
        }
      />

      <DataTable
        emptyMessage={EMPTY_MESSAGES.featureSets}
        columns={[
          { key: "feature_set_id", header: "ID", width: "120px" },
          { key: "feature_set_name", header: "Set명" },
          { key: "target_domain", header: "대상 도메인" },
          { key: "features", header: "Feature 수", render: (r) => (r.features as string[]).length },
          { key: "apply_site_scope", header: "적용 범위" },
          { key: "description", header: "설명", render: (r) => String(r.description || "-").split("---META---")[0] || "-" },
          {
            key: "actions",
            header: "작업",
            render: (r) => {
              const row = r as unknown as FeatureSet;
              return (
                <div className="flex gap-1 flex-wrap" onClick={(e) => e.stopPropagation()}>
                  <Button variant="ghost" icon={<Eye className="w-3 h-3" />} onClick={() => navigate(`/feature-sets/${row.feature_set_id}`)}>
                    상세
                  </Button>
                  <Button variant="secondary" icon={<Copy className="w-3 h-3" />} onClick={() => handleCopy(row)}>
                    복사
                  </Button>
                  <Button variant="danger" icon={<Trash2 className="w-3 h-3" />} onClick={() => setDeleteTarget(row)}>
                    삭제
                  </Button>
                </div>
              );
            },
          },
        ]}
        data={items as unknown as Record<string, unknown>[]}
      />

      <Modal
        open={createOpen}
        title="변수 구성 등록"
        onClose={() => setCreateOpen(false)}
        footer={
          <>
            <Button variant="secondary" onClick={() => setCreateOpen(false)}>취소</Button>
            <Button onClick={handleCreate} disabled={saving}>{saving ? "저장 중..." : "저장"}</Button>
          </>
        }
      >
        <div className="space-y-3">
          <div>
            <label className="block text-xs text-slate-500 mb-1">변수 구성명</label>
            <TextInput value={form.feature_set_name} onChange={(v) => setForm({ ...form, feature_set_name: v })} />
          </div>
          <div>
            <label className="block text-xs text-slate-500 mb-1">적용 범위</label>
            <SelectInput
              value={form.apply_site_scope}
              onChange={(v) => setForm({ ...form, apply_site_scope: v })}
              options={[
                { value: "ALL", label: "전체" },
                { value: "SITE", label: "지사" },
                { value: "REGION", label: "권역" },
              ]}
            />
          </div>
          <div>
            <label className="block text-xs text-slate-500 mb-1">설명</label>
            <TextInput value={form.text} onChange={(v) => setForm({ ...form, text: v })} />
          </div>
        </div>
      </Modal>

      <Modal
        open={!!deleteTarget}
        title="삭제 확인"
        onClose={() => setDeleteTarget(null)}
        footer={
          <>
            <Button variant="secondary" onClick={() => setDeleteTarget(null)}>취소</Button>
            <Button variant="danger" onClick={handleDelete}>삭제</Button>
          </>
        }
      >
        <p className="text-sm text-slate-600">
          <strong>{deleteTarget?.feature_set_name}</strong> 변수 구성을 삭제하시겠습니까?
        </p>
      </Modal>

      <PermissionDeniedModal open={permissionDenied} onClose={() => setPermissionDenied(false)} />
    </div>
  );
}
