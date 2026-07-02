import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { Eye, Plus, Sparkles } from "lucide-react";
import {
  activateStandardDatasetType,
  createStandardDatasetType,
  getStandardDatasetType,
  getStandardDatasetTypes,
} from "@/api/standardDatasets";
import { Button } from "@/components/Button";
import { DataTable } from "@/components/DataTable";
import { Modal } from "@/components/Modal";
import { ErrorState, LoadingState } from "@/components/Pagination";
import { SelectInput, TextInput } from "@/components/SearchPanel";
import { useToast } from "@/hooks/useToast";
import { PageHeader } from "@/layouts/MainLayout";
import type { StandardDatasetColumnInput, StandardDatasetType } from "@/types/standardDatasets";
import { R7_DATASET_BUILDER_NOTE } from "@/types/standardDatasets";
import {
  categoryLabel,
  datasetStatusClass,
  datasetStatusLabel,
  domainLabel,
  physicalTableLabel,
  supportBadgeClass,
  supportLabel,
} from "@/utils/standardDatasetFormat";

const STATUS_FILTER = [
  { value: "", label: "전체 상태" },
  { value: "ACTIVE", label: "운영 (ACTIVE)" },
  { value: "DRAFT", label: "설계 (DRAFT)" },
  { value: "PLANNED", label: "계획 (PLANNED)" },
];

const DOMAIN_FILTER = [
  { value: "", label: "전체 도메인" },
  { value: "HEAT_DEMAND", label: "열수요" },
  { value: "WEATHER", label: "기상" },
  { value: "MASTER", label: "기준정보" },
  { value: "FACILITY", label: "설비" },
];

const EMPTY_COLUMN: StandardDatasetColumnInput = {
  column_name: "",
  data_type: "STRING",
  required: false,
  default_column_role: "",
};

const EMPTY_CREATE = {
  dataset_type_code: "",
  dataset_type_name: "",
  target_table: "",
  domain: "MASTER",
  category: "FACT",
  description: "",
  columns: [{ ...EMPTY_COLUMN }] as StandardDatasetColumnInput[],
};

export default function StandardDatasetsPage() {
  const { showToast } = useToast();
  const [items, setItems] = useState<StandardDatasetType[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [domainFilter, setDomainFilter] = useState("");
  const [detail, setDetail] = useState<StandardDatasetType | null>(null);
  const [detailOpen, setDetailOpen] = useState(false);
  const [createOpen, setCreateOpen] = useState(false);
  const [createForm, setCreateForm] = useState(EMPTY_CREATE);
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const res = await getStandardDatasetTypes({
        status: statusFilter || undefined,
        domain: domainFilter || undefined,
        include_columns: false,
        include_planned: true,
      });
      setItems(res.items);
    } catch {
      setError("표준 데이터셋 목록을 불러오지 못했습니다.");
    } finally {
      setLoading(false);
    }
  }, [statusFilter, domainFilter]);

  useEffect(() => {
    void load();
  }, [load]);

  const filteredCount = useMemo(() => items.length, [items]);

  const openDetail = async (datasetTypeId: string) => {
    try {
      const full = await getStandardDatasetType(datasetTypeId, {
        include_columns: true,
        include_recipe_availability: true,
      });
      setDetail(full);
      setDetailOpen(true);
    } catch {
      showToast("error", "상세 정보를 불러오지 못했습니다.");
    }
  };

  const handleCreate = async () => {
    if (!createForm.dataset_type_code.trim() || !createForm.dataset_type_name.trim() || !createForm.target_table.trim()) {
      showToast("warning", "코드, 이름, 대상 테이블명을 입력하세요.");
      return;
    }
    setSaving(true);
    try {
      const columns = createForm.columns.filter((c) => c.column_name.trim());
      await createStandardDatasetType({
        ...createForm,
        dataset_type_code: createForm.dataset_type_code.toUpperCase(),
        status: "DRAFT",
        mapping_supported: false,
        columns,
      });
      showToast("success", "학습 데이터셋 유형이 DRAFT로 등록되었습니다.");
      setCreateOpen(false);
      setCreateForm(EMPTY_CREATE);
      void load();
    } catch {
      showToast("error", "등록에 실패했습니다.");
    } finally {
      setSaving(false);
    }
  };

  const handleActivate = async (id: string) => {
    try {
      await activateStandardDatasetType(id);
      showToast("success", "ACTIVE로 전환되었습니다.");
      setDetailOpen(false);
      void load();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "ACTIVE 전환에 실패했습니다.";
      showToast("error", msg);
    }
  };

  if (loading && !items.length) return <LoadingState />;
  if (error && !items.length) return <ErrorState message={error} onRetry={() => void load()} />;

  return (
    <div>
      <PageHeader
        title="표준 데이터셋"
        description="학습/운영 데이터셋 유형, 표준 대상 테이블, 컬럼 정의 및 Recipe/Build 연결 가능성을 관리합니다."
        actions={
          <Button icon={<Plus className="w-4 h-4" />} onClick={() => setCreateOpen(true)}>
            학습 데이터셋 유형 등록
          </Button>
        }
      />

      <div className="mb-4 text-xs text-slate-600 bg-amber-50 border border-amber-200 rounded-lg p-3 space-y-1">
        <p>{R7_DATASET_BUILDER_NOTE}</p>
        <p>신규 도메인은 DRAFT로 설계 후, 실제 테이블과 적재 로직이 준비되면 ACTIVE로 전환합니다.</p>
        <p>
          데이터 매핑 설정은 <Link to="/data/mappings" className="text-blue-600 hover:underline">데이터 매핑 설정</Link>
          에서 표준 대상 테이블을 선택해 연결합니다.
        </p>
      </div>

      <div className="flex flex-wrap gap-2 mb-4">
        <SelectInput value={statusFilter} onChange={setStatusFilter} options={STATUS_FILTER} />
        <SelectInput value={domainFilter} onChange={setDomainFilter} options={DOMAIN_FILTER} />
        <span className="text-xs text-slate-500 self-center">{filteredCount}건</span>
      </div>

      <DataTable
        columns={[
          { key: "dataset_type_name", header: "데이터셋 유형" },
          { key: "target_table", header: "대상 테이블" },
          { key: "domain", header: "도메인", render: (r) => domainLabel(r.domain as string) },
          { key: "category", header: "분류", render: (r) => categoryLabel(r.category as string) },
          {
            key: "status",
            header: "상태",
            render: (r) => (
              <span className={`inline-flex text-[10px] px-1.5 py-0.5 rounded border ${datasetStatusClass(String(r.status))}`}>
                {datasetStatusLabel(String(r.status))}
              </span>
            ),
          },
          {
            key: "mapping_supported",
            header: "매핑",
            render: (r) => (
              <span className={`text-[10px] px-1.5 py-0.5 rounded border ${supportBadgeClass(!!r.mapping_supported)}`}>
                {supportLabel(!!r.mapping_supported)}
              </span>
            ),
          },
          {
            key: "recipe_supported",
            header: "Recipe",
            render: (r) => (
              <span className={`text-[10px] px-1.5 py-0.5 rounded border ${supportBadgeClass(!!r.recipe_supported)}`}>
                {supportLabel(!!r.recipe_supported)}
              </span>
            ),
          },
          {
            key: "build_supported",
            header: "Build",
            render: (r) => (
              <span className={`text-[10px] px-1.5 py-0.5 rounded border ${supportBadgeClass(!!r.build_supported)}`}>
                {supportLabel(!!r.build_supported)}
              </span>
            ),
          },
          {
            key: "physical_table_exists",
            header: "물리 테이블",
            render: (r) => physicalTableLabel(!!r.physical_table_exists),
          },
          {
            key: "actions",
            header: "",
            render: (r) => (
              <Button
                variant="ghost"
                icon={<Eye className="w-3 h-3" />}
                onClick={() => void openDetail(String(r.dataset_type_id))}
              >
                상세
              </Button>
            ),
          },
        ]}
        data={items as unknown as Record<string, unknown>[]}
      />

      <Modal
        open={detailOpen}
        title={detail?.dataset_type_name || "데이터셋 유형 상세"}
        onClose={() => setDetailOpen(false)}
        size="xl"
        footer={
          <>
            {detail && detail.status !== "ACTIVE" && detail.physical_table_exists && (
              <Button icon={<Sparkles className="w-4 h-4" />} onClick={() => void handleActivate(detail.dataset_type_id)}>
                ACTIVE 전환
              </Button>
            )}
            <Button variant="secondary" onClick={() => setDetailOpen(false)}>닫기</Button>
          </>
        }
      >
        {detail && (
          <div className="space-y-4 text-sm">
            <div className="grid grid-cols-2 gap-2 text-xs">
              <div>코드: <strong>{detail.dataset_type_code}</strong></div>
              <div>대상 테이블: <strong>{detail.target_table}</strong></div>
              <div>도메인: {domainLabel(detail.domain)}</div>
              <div>분류: {categoryLabel(detail.category)}</div>
              <div>상태: {datasetStatusLabel(detail.status)}</div>
              <div>{physicalTableLabel(detail.physical_table_exists)}</div>
            </div>
            {detail.description && <p className="text-xs text-slate-600">{detail.description}</p>}
            {detail.columns && detail.columns.length > 0 && (
              <div>
                <h4 className="font-semibold text-slate-800 mb-2">표준 컬럼</h4>
                <div className="overflow-x-auto border rounded-lg">
                  <table className="w-full text-xs">
                    <thead className="bg-slate-50">
                      <tr>
                        <th className="px-2 py-1 text-left">컬럼</th>
                        <th className="px-2 py-1 text-left">타입</th>
                        <th className="px-2 py-1 text-left">필수</th>
                        <th className="px-2 py-1 text-left">기본 Role</th>
                      </tr>
                    </thead>
                    <tbody>
                      {detail.columns.map((c) => (
                        <tr key={c.column_id} className="border-t">
                          <td className="px-2 py-1">{c.column_name}</td>
                          <td className="px-2 py-1">{c.data_type}</td>
                          <td className="px-2 py-1">{c.required ? "Y" : "N"}</td>
                          <td className="px-2 py-1">{c.default_column_role || "-"}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
            {detail.default_roles && Object.keys(detail.default_roles).length > 0 && (
              <div className="text-xs">
                <h4 className="font-semibold text-slate-800 mb-1">기본 Column Role</h4>
                <pre className="bg-slate-50 border rounded p-2 overflow-x-auto">{JSON.stringify(detail.default_roles, null, 2)}</pre>
              </div>
            )}
            {detail.recipe_readiness && (
              <div>
                <h4 className="font-semibold text-slate-800 mb-2">
                  Recipe Template 사용 가능성 ({detail.recipe_readiness.available_count}개 사용 가능)
                </h4>
                <ul className="text-xs space-y-1 max-h-48 overflow-y-auto">
                  {detail.recipe_readiness.templates.map((t) => (
                    <li key={t.recipe_type} className={t.available ? "text-emerald-700" : "text-slate-500"}>
                      {t.available ? "✓" : "○"} {t.display_name} ({t.recipe_type})
                      {!t.available && t.missing_roles.length > 0 && (
                        <span className="text-amber-700"> — 부족: {t.missing_roles.join(", ")}</span>
                      )}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}
      </Modal>

      <Modal
        open={createOpen}
        title="학습 데이터셋 유형 등록"
        onClose={() => setCreateOpen(false)}
        size="lg"
        footer={
          <>
            <Button variant="secondary" onClick={() => setCreateOpen(false)}>취소</Button>
            <Button onClick={() => void handleCreate()} disabled={saving}>{saving ? "저장 중..." : "DRAFT 저장"}</Button>
          </>
        }
      >
        <div className="space-y-3 text-sm">
          <p className="text-xs text-slate-500">물리 테이블은 자동 생성되지 않습니다. DRAFT로 설계 후 컬럼·역할을 정의하세요.</p>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs text-slate-500 mb-1">유형 코드</label>
              <TextInput value={createForm.dataset_type_code} onChange={(v) => setCreateForm({ ...createForm, dataset_type_code: v })} placeholder="MY_DATASET" />
            </div>
            <div>
              <label className="block text-xs text-slate-500 mb-1">유형명</label>
              <TextInput value={createForm.dataset_type_name} onChange={(v) => setCreateForm({ ...createForm, dataset_type_name: v })} />
            </div>
          </div>
          <div>
            <label className="block text-xs text-slate-500 mb-1">대상 테이블 제안명</label>
            <TextInput value={createForm.target_table} onChange={(v) => setCreateForm({ ...createForm, target_table: v })} placeholder="tb_my_dataset" />
          </div>
          <div>
            <label className="block text-xs text-slate-500 mb-1">설명</label>
            <TextInput value={createForm.description} onChange={(v) => setCreateForm({ ...createForm, description: v })} />
          </div>
          <div>
            <div className="flex items-center justify-between mb-2">
              <label className="text-xs text-slate-500">컬럼 정의</label>
              <Button
                variant="ghost"
                onClick={() => setCreateForm({ ...createForm, columns: [...createForm.columns, { ...EMPTY_COLUMN }] })}
              >
                컬럼 추가
              </Button>
            </div>
            {createForm.columns.map((col, idx) => (
              <div key={idx} className="grid grid-cols-3 gap-2 mb-2">
                <TextInput
                  value={col.column_name}
                  onChange={(v) => {
                    const columns = [...createForm.columns];
                    columns[idx] = { ...columns[idx], column_name: v };
                    setCreateForm({ ...createForm, columns });
                  }}
                  placeholder="column_name"
                />
                <TextInput
                  value={col.data_type || "STRING"}
                  onChange={(v) => {
                    const columns = [...createForm.columns];
                    columns[idx] = { ...columns[idx], data_type: v };
                    setCreateForm({ ...createForm, columns });
                  }}
                  placeholder="data_type"
                />
                <TextInput
                  value={col.default_column_role || ""}
                  onChange={(v) => {
                    const columns = [...createForm.columns];
                    columns[idx] = { ...columns[idx], default_column_role: v };
                    setCreateForm({ ...createForm, columns });
                  }}
                  placeholder="default_column_role"
                />
              </div>
            ))}
          </div>
        </div>
      </Modal>
    </div>
  );
}
