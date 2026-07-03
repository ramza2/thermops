import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { Eye, Plus, Sparkles } from "lucide-react";
import {
  activateStandardDatasetType,
  getStandardDatasetMetadataOptions,
  getStandardDatasetType,
  getStandardDatasetTypes,
} from "@/api/standardDatasets";
import { StandardDatasetWizard } from "@/components/StandardDatasetWizard";
import { Button } from "@/components/Button";
import { DataTable } from "@/components/DataTable";
import { Modal } from "@/components/Modal";
import { ErrorState, LoadingState } from "@/components/Pagination";
import { SelectInput, TextInput } from "@/components/SearchPanel";
import { useToast } from "@/hooks/useToast";
import { PageHeader } from "@/layouts/MainLayout";
import { EMPTY_MESSAGES, PAGE_DESCRIPTIONS, PAGE_TITLES, R9_S2_3_NOTE } from "@/constants/displayLabels";
import type { StandardDatasetMetadataOptions, StandardDatasetType } from "@/types/standardDatasets";
import { R9_DATASET_METADATA_NOTE, R9_DATASET_WIZARD_NOTE } from "@/types/standardDatasets";
import {
  datasetCategoryLabel,
  datasetStatusClass,
  datasetStatusLabel,
  formatTags,
  physicalTableLabel,
  supportBadgeClass,
  supportLabel,
} from "@/utils/standardDatasetFormat";

const STATUS_FILTER = [
  { value: "", label: "전체 상태" },
  { value: "ACTIVE", label: "운영 (ACTIVE)" },
  { value: "VALIDATED", label: "검증 (VALIDATED)" },
  { value: "DRAFT", label: "설계 (DRAFT)" },
  { value: "PLANNED", label: "계획 (PLANNED)" },
  { value: "ARCHIVED", label: "보관 (ARCHIVED)" },
];

const PHYSICAL_FILTER = [
  { value: "", label: "전체 물리 테이블" },
  { value: "Y", label: "물리 테이블 존재" },
  { value: "N", label: "물리 테이블 없음" },
];

const EMPTY_MESSAGE = EMPTY_MESSAGES.standardDatasets;

export default function StandardDatasetsPage() {
  const { showToast } = useToast();
  const [items, setItems] = useState<StandardDatasetType[]>([]);
  const [metadata, setMetadata] = useState<StandardDatasetMetadataOptions | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [categoryFilter, setCategoryFilter] = useState("");
  const [businessDomainFilter, setBusinessDomainFilter] = useState("");
  const [tagFilter, setTagFilter] = useState("");
  const [physicalFilter, setPhysicalFilter] = useState("");
  const [keyword, setKeyword] = useState("");
  const [detail, setDetail] = useState<StandardDatasetType | null>(null);
  const [detailOpen, setDetailOpen] = useState(false);
  const [wizardOpen, setWizardOpen] = useState(false);

  const loadMetadata = useCallback(async () => {
    try {
      const opts = await getStandardDatasetMetadataOptions();
      setMetadata(opts);
    } catch {
      setMetadata({ dataset_categories: [], business_domains: [], tags: [] });
    }
  }, []);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const res = await getStandardDatasetTypes({
        status: statusFilter || undefined,
        dataset_category: categoryFilter || undefined,
        business_domain: businessDomainFilter || undefined,
        tag: tagFilter || undefined,
        keyword: keyword.trim() || undefined,
        physical_table_exists_yn: physicalFilter || undefined,
        include_columns: false,
        include_planned: true,
      });
      setItems(res.items);
    } catch {
      setError("표준 데이터셋 목록을 불러오지 못했습니다.");
    } finally {
      setLoading(false);
    }
  }, [statusFilter, categoryFilter, businessDomainFilter, tagFilter, physicalFilter, keyword]);

  useEffect(() => {
    void loadMetadata();
  }, [loadMetadata]);

  useEffect(() => {
    void load();
  }, [load]);

  const categoryFilterOptions = useMemo(() => {
    const opts = [{ value: "", label: "전체 데이터 분류" }];
    for (const c of metadata?.dataset_categories || []) {
      opts.push({ value: c.code, label: c.name });
    }
    return opts;
  }, [metadata]);

  const businessDomainFilterOptions = useMemo(() => {
    const opts = [{ value: "", label: "전체 업무 영역" }];
    for (const d of metadata?.business_domains || []) {
      opts.push({ value: d, label: d });
    }
    return opts;
  }, [metadata]);

  const tagFilterOptions = useMemo(() => {
    const opts = [{ value: "", label: "전체 태그" }];
    for (const t of metadata?.tags || []) {
      opts.push({ value: t, label: t });
    }
    return opts;
  }, [metadata]);

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

  const handleActivate = async (id: string) => {
    try {
      await activateStandardDatasetType(id);
      showToast("success", "ACTIVE로 전환되었습니다.");
      setDetailOpen(false);
      void load();
      void loadMetadata();
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
        title={PAGE_TITLES.standardDatasets}
        description={PAGE_DESCRIPTIONS.standardDatasets}
        actions={
          <Button icon={<Plus className="w-4 h-4" />} onClick={() => setWizardOpen(true)}>
            표준 데이터셋 생성
          </Button>
        }
      />

      <div className="mb-4 text-xs text-slate-600 bg-amber-50 border border-amber-200 rounded-lg p-3 space-y-1">
        <p>{R9_DATASET_WIZARD_NOTE}</p>
        <p>{R9_DATASET_METADATA_NOTE}</p>
        <p>{R9_S2_3_NOTE}</p>
        <p>
          데이터 매핑은 <Link to="/data/mappings" className="text-blue-600 hover:underline">데이터 매핑</Link>
          에서 Wizard로 생성한 내부 테이블을 대상으로 연결합니다.
        </p>
      </div>

      <div className="flex flex-wrap gap-2 mb-4">
        <TextInput value={keyword} onChange={setKeyword} placeholder="검색 (이름·코드·설명)" />
        <SelectInput value={categoryFilter} onChange={setCategoryFilter} options={categoryFilterOptions} />
        <SelectInput value={businessDomainFilter} onChange={setBusinessDomainFilter} options={businessDomainFilterOptions} />
        <SelectInput value={tagFilter} onChange={setTagFilter} options={tagFilterOptions} />
        <SelectInput value={statusFilter} onChange={setStatusFilter} options={STATUS_FILTER} />
        <SelectInput value={physicalFilter} onChange={setPhysicalFilter} options={PHYSICAL_FILTER} />
        <span className="text-xs text-slate-500 self-center">{filteredCount}건</span>
      </div>

      <DataTable
        emptyMessage={EMPTY_MESSAGE}
        columns={[
          { key: "dataset_type_name", header: "데이터셋" },
          { key: "dataset_type_code", header: "코드" },
          {
            key: "dataset_category",
            header: "데이터 분류",
            render: (r) => datasetCategoryLabel((r.dataset_category || r.category) as string),
          },
          {
            key: "business_domain",
            header: "업무 영역",
            render: (r) => (r.business_domain as string) || "-",
          },
          {
            key: "tags",
            header: "태그",
            render: (r) => formatTags(r.tags as string[] | undefined),
          },
          {
            key: "status",
            header: "상태",
            render: (r) => (
              <span className={`inline-flex text-[10px] px-1.5 py-0.5 rounded border ${datasetStatusClass(String(r.status))}`}>
                {datasetStatusLabel(String(r.status))}
              </span>
            ),
          },
          { key: "target_table", header: "물리 테이블" },
          {
            key: "physical_table_exists",
            header: "물리 존재",
            render: (r) => physicalTableLabel(!!r.physical_table_exists),
          },
          { key: "column_count", header: "컬럼 수", render: (r) => String(r.column_count ?? "-") },
          {
            key: "created_at",
            header: "생성일",
            render: (r) => (r.created_at ? String(r.created_at).slice(0, 10) : "-"),
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

      <StandardDatasetWizard
        open={wizardOpen}
        onClose={() => setWizardOpen(false)}
        onCompleted={() => {
          void load();
          void loadMetadata();
        }}
      />

      <Modal
        open={detailOpen}
        title={detail?.dataset_type_name || "데이터셋 유형 상세"}
        onClose={() => setDetailOpen(false)}
        size="xl"
        footer={
          <>
            {detail && detail.status !== "ACTIVE" && detail.physical_table_exists && !detail.managed_table && (
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
              <div>데이터 분류: {datasetCategoryLabel(detail.dataset_category || detail.category)}</div>
              <div>업무 영역: {detail.business_domain || "-"}</div>
              <div>태그: {formatTags(detail.tags)}</div>
              <div>상태: {datasetStatusLabel(detail.status)}</div>
              <div>{physicalTableLabel(detail.physical_table_exists)}</div>
              {detail.table_create_status && <div>테이블 생성: {detail.table_create_status}</div>}
            </div>
            {detail.description && <p className="text-xs text-slate-600">{detail.description}</p>}
            {detail.table_create_sql_preview && (
              <div>
                <h4 className="font-semibold text-slate-800 mb-1">SQL Preview</h4>
                <pre className="text-xs bg-slate-900 text-slate-100 p-2 rounded overflow-x-auto">{detail.table_create_sql_preview}</pre>
              </div>
            )}
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
            {detail.recipe_readiness && (
              <div>
                <h4 className="font-semibold text-slate-800 mb-2">
                  Recipe Template 사용 가능성 ({detail.recipe_readiness.available_count}개 사용 가능)
                </h4>
                <ul className="text-xs space-y-1 max-h-48 overflow-y-auto">
                  {detail.recipe_readiness.templates.map((t) => (
                    <li key={t.recipe_type} className={t.available ? "text-emerald-700" : "text-slate-500"}>
                      {t.available ? "✓" : "○"} {t.display_name} ({t.recipe_type})
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}
      </Modal>
    </div>
  );
}
