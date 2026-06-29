import { useEffect, useState } from "react";
import { CheckCircle, Eye, Plus, Pencil } from "lucide-react";
import { fetchApi, postApi, putApi, PagedData } from "@/api/client";
import { Button } from "@/components/Button";
import { DataTable } from "@/components/DataTable";
import { Modal } from "@/components/Modal";
import { StatusBadge } from "@/components/StatusBadge";
import { Pagination, LoadingState, ErrorState } from "@/components/Pagination";
import { SelectInput, TextInput } from "@/components/SearchPanel";
import { useToast } from "@/hooks/useToast";
import { PageHeader } from "@/layouts/MainLayout";

interface MappingColumn {
  source_column: string;
  target_column: string;
  required_yn?: boolean;
}

interface Mapping {
  mapping_id: string;
  source_id: string;
  mapping_name: string;
  target_table: string;
  columns: MappingColumn[];
  active_yn: boolean;
}

interface DataSource {
  source_id: string;
  source_name: string;
}

const EMPTY_FORM = {
  source_id: "",
  mapping_name: "",
  target_table: "heat_demand_actual",
  columns: [
    { source_column: "", target_column: "", required_yn: true },
  ] as MappingColumn[],
};

export default function DataMappingsPage() {
  const { showToast } = useToast();
  const [items, setItems] = useState<Mapping[]>([]);
  const [sources, setSources] = useState<DataSource[]>([]);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [previewOpen, setPreviewOpen] = useState(false);
  const [previewRows, setPreviewRows] = useState<Record<string, unknown>[]>([]);
  const [previewTitle, setPreviewTitle] = useState("");
  const [formOpen, setFormOpen] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [form, setForm] = useState(EMPTY_FORM);
  const [saving, setSaving] = useState(false);
  const [discovering, setDiscovering] = useState(false);
  const [discoveredFields, setDiscoveredFields] = useState<string[]>([]);

  const load = async (p = page) => {
    setLoading(true);
    setError("");
    try {
      const res = await fetchApi<PagedData<Mapping>>("/mappings", { page: p, size: 20 });
      setItems(res.items);
      setTotalPages(res.total_pages);
    } catch {
      setError("매핑 목록을 불러오지 못했습니다.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load(page);
    fetchApi<PagedData<DataSource>>("/data-sources", { page: 1, size: 100 })
      .then((res) => setSources(res.items))
      .catch(() => {});
  }, [page]);

  const openCreate = () => {
    setEditingId(null);
    setForm({
      ...EMPTY_FORM,
      source_id: sources[0]?.source_id || "",
    });
    setFormOpen(true);
  };

  const openEdit = (row: Mapping) => {
    setEditingId(row.mapping_id);
    setForm({
      source_id: row.source_id,
      mapping_name: row.mapping_name,
      target_table: row.target_table,
      columns: row.columns.length ? row.columns : EMPTY_FORM.columns,
    });
    setFormOpen(true);
  };

  const updateColumn = (idx: number, field: keyof MappingColumn, value: string | boolean) => {
    const cols = [...form.columns];
    cols[idx] = { ...cols[idx], [field]: value };
    setForm({ ...form, columns: cols });
  };

  const handleSave = async () => {
    if (!form.mapping_name.trim() || !form.source_id) {
      showToast("warning", "매핑명과 데이터 소스를 입력하세요.");
      return;
    }
    setSaving(true);
    try {
      const payload = {
        source_id: form.source_id,
        mapping_name: form.mapping_name,
        target_table: form.target_table,
        columns: form.columns.filter((c) => c.source_column && c.target_column),
      };
      if (editingId) {
        await putApi(`/mappings/${editingId}`, payload);
        showToast("success", "매핑이 수정되었습니다.");
      } else {
        await postApi("/mappings", payload);
        showToast("success", "매핑이 등록되었습니다.");
      }
      setFormOpen(false);
      load();
    } catch {
      showToast("error", "저장에 실패했습니다.");
    } finally {
      setSaving(false);
    }
  };

  const handleValidate = async (row: Mapping) => {
    try {
      const res = await postApi<{ valid: boolean; errors: string[]; warnings: string[] }>(`/mappings/${row.mapping_id}/validate`);
      if (res.valid) {
        showToast("success", res.warnings.length ? `검증 통과 (경고 ${res.warnings.length}건)` : "매핑 검증에 성공했습니다.");
      } else {
        showToast("error", res.errors.join(", ") || "매핑 검증에 실패했습니다.");
      }
    } catch {
      showToast("error", "검증 요청에 실패했습니다.");
    }
  };

  const handleDiscoverSchema = async () => {
    if (!form.source_id) {
      showToast("warning", "데이터 소스를 선택하세요.");
      return;
    }
    setDiscovering(true);
    try {
      const res = await fetchApi<{ fields: { name: string }[]; columns?: { name: string }[] }>(
        `/data-sources/${encodeURIComponent(form.source_id)}/discover-schema`,
      );
      const names = (res.fields || res.columns || []).map((f) => f.name).filter(Boolean);
      setDiscoveredFields(names);
      if (names.length) {
        const existing = new Set(form.columns.map((c) => c.source_column).filter(Boolean));
        const newCols = names
          .filter((n) => !existing.has(n))
          .map((n) => ({ source_column: n, target_column: "", required_yn: false }));
        if (newCols.length) {
          setForm({
            ...form,
            columns: [...form.columns.filter((c) => c.source_column || c.target_column), ...newCols],
          });
        }
        showToast("success", `스키마 탐색 완료: ${names.length}개 필드`);
      } else {
        showToast("warning", "탐색된 필드가 없습니다.");
      }
    } catch {
      showToast("error", "스키마 탐색에 실패했습니다.");
    } finally {
      setDiscovering(false);
    }
  };

  const handlePreview = async (row: Mapping) => {
    try {
      const res = await postApi<{ preview_rows: Record<string, unknown>[] }>(`/mappings/${row.mapping_id}/preview`);
      setPreviewRows(res.preview_rows);
      setPreviewTitle(row.mapping_name);
      setPreviewOpen(true);
    } catch {
      showToast("error", "미리보기를 불러오지 못했습니다.");
    }
  };

  if (loading && !items.length) return <LoadingState />;
  if (error && !items.length) return <ErrorState message={error} onRetry={() => load()} />;

  return (
    <div>
      <PageHeader
        title="데이터 매핑 설정"
        description="원천 컬럼과 표준 스키마 간 매핑 규칙을 관리합니다."
        actions={<Button icon={<Plus className="w-4 h-4" />} onClick={openCreate}>신규 매핑</Button>}
      />

      <DataTable
        loading={loading}
        columns={[
          { key: "mapping_id", header: "ID", width: "120px" },
          { key: "mapping_name", header: "매핑명" },
          { key: "source_id", header: "소스 ID" },
          { key: "target_table", header: "대상 테이블" },
          { key: "columns", header: "컬럼 수", render: (r) => (r.columns as MappingColumn[]).length },
          { key: "active_yn", header: "상태", render: (r) => <StatusBadge status={r.active_yn ? "ACTIVE" : "INACTIVE"} /> },
          {
            key: "actions",
            header: "작업",
            render: (r) => {
              const row = r as unknown as Mapping;
              return (
                <div className="flex gap-1 flex-wrap" onClick={(e) => e.stopPropagation()}>
                  <Button variant="ghost" icon={<Pencil className="w-3 h-3" />} onClick={() => openEdit(row)}>수정</Button>
                  <Button variant="secondary" icon={<CheckCircle className="w-3 h-3" />} onClick={() => handleValidate(row)}>검증</Button>
                  <Button variant="ghost" icon={<Eye className="w-3 h-3" />} onClick={() => handlePreview(row)}>미리보기</Button>
                </div>
              );
            },
          },
        ]}
        data={items as unknown as Record<string, unknown>[]}
      />
      <Pagination page={page} totalPages={totalPages} onChange={setPage} />

      <Modal
        open={formOpen}
        title={editingId ? "매핑 수정" : "신규 매핑 등록"}
        onClose={() => setFormOpen(false)}
        size="lg"
        footer={
          <>
            <Button variant="secondary" onClick={() => setFormOpen(false)}>취소</Button>
            <Button onClick={handleSave} disabled={saving}>{saving ? "저장 중..." : "저장"}</Button>
          </>
        }
      >
        <div className="space-y-3">
          <div>
            <label className="block text-xs text-slate-500 mb-1">데이터 소스</label>
            <SelectInput
              value={form.source_id}
              onChange={(v) => setForm({ ...form, source_id: v })}
              options={sources.map((s) => ({ value: s.source_id, label: `${s.source_name} (${s.source_id})` }))}
            />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs text-slate-500 mb-1">매핑명</label>
              <TextInput value={form.mapping_name} onChange={(v) => setForm({ ...form, mapping_name: v })} />
            </div>
            <div>
              <label className="block text-xs text-slate-500 mb-1">대상 테이블</label>
              <TextInput value={form.target_table} onChange={(v) => setForm({ ...form, target_table: v })} />
            </div>
          </div>
          <div>
            <div className="flex items-center justify-between mb-2">
              <label className="block text-xs text-slate-500">컬럼 매핑</label>
              <Button variant="secondary" disabled={discovering || !form.source_id} onClick={handleDiscoverSchema}>
                {discovering ? "탐색 중..." : "스키마 탐색"}
              </Button>
            </div>
            {discoveredFields.length > 0 && (
              <p className="text-xs text-slate-500 mb-2">
                탐색된 필드: {discoveredFields.join(", ")}
              </p>
            )}
            {form.columns.map((col, idx) => (
              <div key={idx} className="grid grid-cols-2 gap-2 mb-2">
                <TextInput
                  value={col.source_column}
                  onChange={(v) => updateColumn(idx, "source_column", v)}
                  placeholder="원천 컬럼"
                />
                <TextInput
                  value={col.target_column}
                  onChange={(v) => updateColumn(idx, "target_column", v)}
                  placeholder="표준 컬럼"
                />
              </div>
            ))}
            <Button
              variant="ghost"
              onClick={() => setForm({ ...form, columns: [...form.columns, { source_column: "", target_column: "", required_yn: false }] })}
            >
              + 컬럼 행 추가
            </Button>
          </div>
        </div>
      </Modal>

      <Modal
        open={previewOpen}
        title={`변환 미리보기 - ${previewTitle}`}
        onClose={() => setPreviewOpen(false)}
        size="lg"
        footer={<Button variant="secondary" onClick={() => setPreviewOpen(false)}>닫기</Button>}
      >
        <DataTable
          columns={previewRows.length ? Object.keys(previewRows[0]).map((k) => ({ key: k, header: k })) : []}
          data={previewRows}
        />
      </Modal>
    </div>
  );
}
