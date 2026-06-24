import { useEffect, useState } from "react";
import { Plus, Trash2 } from "lucide-react";
import { deleteApi, fetchApi, postApi, PagedData } from "@/api/client";
import { Button } from "@/components/Button";
import { DataTable } from "@/components/DataTable";
import { Modal } from "@/components/Modal";
import { StatusBadge } from "@/components/StatusBadge";
import { Pagination, LoadingState, ErrorState } from "@/components/Pagination";
import { SelectInput, TextInput } from "@/components/SearchPanel";
import { useToast } from "@/hooks/useToast";
import { PageHeader } from "@/layouts/MainLayout";

interface Feature {
  feature_id: string;
  feature_name: string;
  feature_group: string | null;
  feature_type: string;
  calc_expression: string | null;
  status: string;
  description: string | null;
}

const EMPTY = { feature_name: "", feature_group: "", feature_type: "NUMERIC", calc_expression: "", description: "" };

export default function FeaturesPage() {
  const { showToast } = useToast();
  const [items, setItems] = useState<Feature[]>([]);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [createOpen, setCreateOpen] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<Feature | null>(null);
  const [form, setForm] = useState(EMPTY);
  const [saving, setSaving] = useState(false);

  const load = async (p = page) => {
    setLoading(true);
    setError("");
    try {
      const res = await fetchApi<PagedData<Feature>>("/features", { page: p, size: 20 });
      setItems(res.items);
      setTotalPages(res.total_pages);
    } catch {
      setError("Feature 목록을 불러오지 못했습니다.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(page); }, [page]);

  const handleCreate = async () => {
    if (!form.feature_name.trim()) {
      showToast("warning", "Feature명을 입력하세요.");
      return;
    }
    setSaving(true);
    try {
      await postApi("/features", {
        feature_name: form.feature_name,
        feature_group: form.feature_group || null,
        feature_type: form.feature_type,
        calc_expression: form.calc_expression || null,
        description: form.description || null,
      });
      showToast("success", "Feature가 등록되었습니다.");
      setCreateOpen(false);
      setForm(EMPTY);
      load(1);
      setPage(1);
    } catch {
      showToast("error", "등록에 실패했습니다.");
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async () => {
    if (!deleteTarget) return;
    try {
      await deleteApi(`/features/${deleteTarget.feature_id}`);
      showToast("success", "Feature가 삭제되었습니다.");
      setDeleteTarget(null);
      load();
    } catch {
      showToast("error", "삭제에 실패했습니다.");
    }
  };

  if (loading && !items.length) return <LoadingState />;
  if (error && !items.length) return <ErrorState message={error} onRetry={() => load()} />;

  return (
    <div>
      <PageHeader
        title="Feature 목록"
        description="모델 학습에 사용되는 Feature를 정의하고 관리합니다."
        actions={<Button icon={<Plus className="w-4 h-4" />} onClick={() => setCreateOpen(true)}>신규 Feature</Button>}
      />

      <DataTable
        loading={loading}
        columns={[
          { key: "feature_id", header: "ID", width: "120px" },
          { key: "feature_name", header: "Feature명" },
          { key: "feature_group", header: "그룹", render: (r) => String(r.feature_group || "-") },
          { key: "feature_type", header: "유형" },
          { key: "calc_expression", header: "계산식", render: (r) => String(r.calc_expression || "-") },
          { key: "status", header: "상태", render: (r) => <StatusBadge status={r.status as string} /> },
          {
            key: "actions", header: "작업", render: (r) => (
              <Button variant="danger" icon={<Trash2 className="w-3 h-3" />} onClick={(e) => { e.stopPropagation(); setDeleteTarget(r as unknown as Feature); }}>삭제</Button>
            ),
          },
        ]}
        data={items as unknown as Record<string, unknown>[]}
      />
      <Pagination page={page} totalPages={totalPages} onChange={setPage} />

      <Modal open={createOpen} title="Feature 등록" onClose={() => setCreateOpen(false)}
        footer={<>
          <Button variant="secondary" onClick={() => setCreateOpen(false)}>취소</Button>
          <Button onClick={handleCreate} disabled={saving}>{saving ? "저장 중..." : "저장"}</Button>
        </>}>
        <div className="space-y-3">
          <div>
            <label className="block text-xs text-slate-500 mb-1">Feature명</label>
            <TextInput value={form.feature_name} onChange={(v) => setForm({ ...form, feature_name: v })} placeholder="lag_24h_demand" />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs text-slate-500 mb-1">그룹</label>
              <TextInput value={form.feature_group} onChange={(v) => setForm({ ...form, feature_group: v })} placeholder="lag" />
            </div>
            <div>
              <label className="block text-xs text-slate-500 mb-1">유형</label>
              <SelectInput value={form.feature_type} onChange={(v) => setForm({ ...form, feature_type: v })}
                options={[{ value: "NUMERIC", label: "수치" }, { value: "CATEGORICAL", label: "범주" }, { value: "DATETIME", label: "일시" }]} />
            </div>
          </div>
          <div>
            <label className="block text-xs text-slate-500 mb-1">계산식</label>
            <TextInput value={form.calc_expression} onChange={(v) => setForm({ ...form, calc_expression: v })} placeholder="LAG(heat_demand, 24)" />
          </div>
          <div>
            <label className="block text-xs text-slate-500 mb-1">설명</label>
            <TextInput value={form.description} onChange={(v) => setForm({ ...form, description: v })} />
          </div>
        </div>
      </Modal>

      <Modal open={!!deleteTarget} title="삭제 확인" onClose={() => setDeleteTarget(null)}
        footer={<>
          <Button variant="secondary" onClick={() => setDeleteTarget(null)}>취소</Button>
          <Button variant="danger" onClick={handleDelete}>삭제</Button>
        </>}>
        <p className="text-sm text-slate-600"><strong>{deleteTarget?.feature_name}</strong> Feature를 삭제하시겠습니까?</p>
      </Modal>
    </div>
  );
}
