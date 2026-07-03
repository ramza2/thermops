import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { CheckCircle, Eye, Plus, Pencil, Sparkles, Save, Trash2 } from "lucide-react";
import { deleteApi, extractApiErrorMessage, fetchApi, postApi, putApi, PagedData } from "@/api/client";
import {
  getColumnRoleCodes,
  getColumnRoles,
  inferColumnRoles,
  saveColumnRoles,
  validateColumnRoles,
} from "@/api/featureColumnRoles";
import { getFeatureRecipeTemplates } from "@/api/featureRecipeTemplates";
import { getStandardTargetTables } from "@/api/standardDatasets";
import { FeatureRecipePreviewModal } from "@/components/FeatureRecipePreviewModal";
import { Button } from "@/components/Button";
import { DataTable } from "@/components/DataTable";
import { Modal } from "@/components/Modal";
import { StatusBadge } from "@/components/StatusBadge";
import { Pagination, LoadingState, ErrorState } from "@/components/Pagination";
import { SelectInput, TextInput } from "@/components/SearchPanel";
import { useToast } from "@/hooks/useToast";
import { PageHeader } from "@/layouts/MainLayout";
import type {
  ColumnRoleCode,
  FeatureColumnRole,
  FeatureColumnRoleSummary,
  FeatureColumnRoleValidation,
} from "@/types/featureColumnRoles";
import type { RecipeTemplate, RecipeTemplateListResponse } from "@/types/featureRecipeTemplates";
import {
  COLUMN_ROLE_HELP,
  COLUMN_ROLE_INFERENCE_NOTE,
  roleBadgeClass,
  roleLabel,
} from "@/utils/featureColumnRoleFormat";
import {
  formatRequiredRoles,
  PREVIEW_SUPPORTED_RECIPE_TYPES,
  PREVIEW_FUTURE_RECIPE_TYPES,
  RECIPE_BUILDER_FUTURE_NOTE,
  RECIPE_PREVIEW_NO_SAVE_NOTE,
  RECIPE_PREVIEW_ROW_STEP_NOTE,
  RECIPE_PREVIEW_R4_NOTE,
  RECIPE_TEMPLATE_SECTION_TITLE,
  templateAvailabilityClass,
  templateCategoryLabel,
  templateStatusClass,
  templateStatusLabel,
} from "@/utils/featureRecipeTemplateFormat";
import type { StandardTargetTable } from "@/types/standardDatasets";
import { R9_MAPPING_TARGET_NOTE } from "@/types/standardDatasets";
import { targetTableOptionLabel } from "@/utils/standardDatasetFormat";

interface MappingColumn {
  source_column: string;
  target_column: string;
  required_yn?: boolean;
  data_type?: string;
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

interface DeleteBlocker {
  code: string;
  count?: number;
  message: string;
  items?: { recipe_id: string; display_name: string; status: string }[];
}

interface DeleteBlockersResponse {
  mapping_id: string;
  can_delete: boolean;
  blockers: DeleteBlocker[];
}

const EMPTY_FORM = {
  source_id: "",
  mapping_name: "",
  target_table: "",
  columns: [
    { source_column: "", target_column: "", required_yn: true },
  ] as MappingColumn[],
};

function normalizeTargetKey(table: string): string {
  return table.toLowerCase().replace(/^tb_/, "");
}

const ROLE_EMPTY_OPTION = { value: "", label: "미지정" };

function RoleCoverageCard({ summary }: { summary: FeatureColumnRoleSummary | null }) {
  if (!summary) return null;
  const readiness = summary.recipe_readiness;
  return (
    <div className="text-xs border border-slate-200 rounded-lg p-3 bg-slate-50 space-y-2">
      <div className="font-semibold text-slate-800">Recipe 준비도</div>
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
        <div>개체 키: <strong>{summary.entity_key_count}</strong></div>
        <div>시간 키: <strong>{summary.time_key_count}</strong></div>
        <div>예측 대상: <strong>{summary.target_count}</strong></div>
        <div>Feature 후보: <strong>{summary.feature_candidate_count}</strong></div>
      </div>
      <ul className="space-y-1 text-slate-600">
        {Object.entries(readiness).map(([key, item]) => (
          <li key={key} className={item.ready ? "text-emerald-700" : "text-amber-700"}>
            {item.ready ? "✓" : "○"} {item.message}
          </li>
        ))}
      </ul>
    </div>
  );
}

function RecipeTemplatesSection({
  catalog,
  loading,
  error,
  expandedType,
  onToggle,
  onPreview,
  mappingId,
}: {
  catalog: RecipeTemplateListResponse | null;
  loading: boolean;
  error: string;
  expandedType: string | null;
  onToggle: (type: string) => void;
  onPreview: (tpl: RecipeTemplate) => void;
  mappingId?: string | null;
}) {
  if (loading) {
    return <p className="text-xs text-slate-400">Recipe 템플릿 불러오는 중...</p>;
  }
  if (error) {
    return <p className="text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded p-2">{error}</p>;
  }
  if (!catalog?.items?.length) return null;

  const available = catalog.items.filter((t) => t.available);
  const unavailable = catalog.items.filter((t) => t.available === false);

  return (
    <div className="text-xs border border-slate-200 rounded-lg p-3 bg-white space-y-3">
      <div className="font-semibold text-slate-800">{RECIPE_TEMPLATE_SECTION_TITLE}</div>
      <p className="text-slate-500">{RECIPE_BUILDER_FUTURE_NOTE}</p>
      <p className="text-slate-500">{RECIPE_PREVIEW_NO_SAVE_NOTE}</p>
      <p className="text-slate-500">{RECIPE_PREVIEW_ROW_STEP_NOTE}</p>
      <p className="text-slate-500">{RECIPE_PREVIEW_R4_NOTE}</p>
      {mappingId && (
        <p>
          <Link
            to={`/feature-recipes/new?mapping_id=${encodeURIComponent(mappingId)}&recipe_type=LAG`}
            className="text-blue-600 hover:underline"
          >
            Recipe Builder에서 계속하기
          </Link>
        </p>
      )}
      <p className="text-slate-600">
        LAG/ROLLING은 ENTITY_KEY, TIME_KEY, NUMERIC_INPUT 역할이 필요합니다.
        {" "}
        사용 가능 {catalog.summary.available_count ?? available.length} / {catalog.summary.total_count}
      </p>
      <div className="space-y-2">
        {available.map((tpl) => (
          <RecipeTemplateRow
            key={tpl.recipe_type}
            tpl={tpl}
            expanded={expandedType === tpl.recipe_type}
            onToggle={onToggle}
            onPreview={onPreview}
          />
        ))}
        {unavailable.map((tpl) => (
          <RecipeTemplateRow
            key={tpl.recipe_type}
            tpl={tpl}
            expanded={expandedType === tpl.recipe_type}
            onToggle={onToggle}
            onPreview={onPreview}
            unavailable
          />
        ))}
      </div>
    </div>
  );
}

function RecipeTemplateRow({
  tpl,
  expanded,
  onToggle,
  onPreview,
  unavailable,
}: {
  tpl: RecipeTemplate;
  expanded: boolean;
  onToggle: (type: string) => void;
  onPreview: (tpl: RecipeTemplate) => void;
  unavailable?: boolean;
}) {
  const avail = tpl.availability;
  const previewSupported = PREVIEW_SUPPORTED_RECIPE_TYPES.has(tpl.recipe_type);
  const previewFuture = PREVIEW_FUTURE_RECIPE_TYPES.has(tpl.recipe_type);
  return (
    <div className={`border rounded p-2 ${unavailable ? "border-amber-200 bg-amber-50/50" : "border-slate-200"}`}>
      <div className="flex flex-wrap items-center gap-2">
        <button type="button" className="flex-1 text-left min-w-0" onClick={() => onToggle(tpl.recipe_type)}>
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-medium text-slate-800">{tpl.display_name}</span>
            <span className={`text-[10px] px-1 py-0.5 rounded border ${templateStatusClass(tpl.status)}`}>
              {templateStatusLabel(tpl.status)}
            </span>
            <span className="text-[10px] text-slate-500">{templateCategoryLabel(tpl.category)}</span>
            <span className={`text-[10px] ${templateAvailabilityClass(tpl.available)}`}>
              {tpl.available ? "사용 가능" : "사용 불가"}
            </span>
          </div>
          {!tpl.available && avail?.warnings?.[0] && (
            <p className="text-amber-700 mt-1">{avail.warnings[0]}</p>
          )}
          {avail?.missing_roles?.length ? (
            <p className="text-amber-700 mt-1">부족 역할: {avail.missing_roles.join(", ")}</p>
          ) : null}
        </button>
        {previewSupported ? (
          <Button
            variant="secondary"
            disabled={tpl.available === false}
            onClick={() => onPreview(tpl)}
          >
            Preview
          </Button>
        ) : previewFuture ? (
          <span className="text-[10px] text-slate-400 whitespace-nowrap">후속 Preview</span>
        ) : (
          <span className="text-[10px] text-slate-400 whitespace-nowrap">Preview 미지원</span>
        )}
      </div>
      {expanded && (
        <div className="mt-2 pt-2 border-t border-slate-200 text-slate-600 space-y-1">
          <p>{tpl.description}</p>
          <p>필수 역할: {formatRequiredRoles(tpl)}</p>
          <p>출력명 규칙: <code className="text-[10px]">{tpl.output_name_rule}</code></p>
          {tpl.param_schema && Object.keys(tpl.param_schema).length > 0 && (
            <p>주요 파라미터: {Object.keys(tpl.param_schema).join(", ")}</p>
          )}
        </div>
      )}
    </div>
  );
}

function ValidationPanel({ validation }: { validation: FeatureColumnRoleValidation | null }) {
  if (!validation) return null;
  const hasAny =
    validation.errors.length > 0
    || validation.warnings.length > 0
    || (validation.infos?.length ?? 0) > 0;
  if (!hasAny) {
    return (
      <div className="text-xs text-emerald-800 bg-emerald-50 border border-emerald-200 rounded-lg p-3">
        검증 결과: 문제 없음
      </div>
    );
  }
  return (
    <div className="text-xs border border-slate-200 rounded-lg p-3 space-y-2">
      <div className="font-semibold text-slate-800">검증 결과</div>
      {validation.errors.map((e) => (
        <p key={e} className="text-red-700">• {e}</p>
      ))}
      {validation.warnings.map((w) => (
        <p key={w} className="text-amber-700">• {w}</p>
      ))}
      {(validation.infos ?? []).map((i) => (
        <p key={i} className="text-slate-600">• {i}</p>
      ))}
    </div>
  );
}

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

  const [roleCodes, setRoleCodes] = useState<ColumnRoleCode[]>([]);
  const [columnRoles, setColumnRoles] = useState<FeatureColumnRole[]>([]);
  const [roleSummary, setRoleSummary] = useState<FeatureColumnRoleSummary | null>(null);
  const [roleValidation, setRoleValidation] = useState<FeatureColumnRoleValidation | null>(null);
  const [roleSectionOpen, setRoleSectionOpen] = useState(true);
  const [roleLoading, setRoleLoading] = useState(false);
  const [roleSaving, setRoleSaving] = useState(false);
  const [roleInferring, setRoleInferring] = useState(false);

  const [templateCatalog, setTemplateCatalog] = useState<RecipeTemplateListResponse | null>(null);
  const [templateLoading, setTemplateLoading] = useState(false);
  const [templateError, setTemplateError] = useState("");
  const [expandedTemplateType, setExpandedTemplateType] = useState<string | null>(null);
  const [templateSectionOpen, setTemplateSectionOpen] = useState(true);
  const [recipePreviewOpen, setRecipePreviewOpen] = useState(false);
  const [recipePreviewTemplate, setRecipePreviewTemplate] = useState<RecipeTemplate | null>(null);
  const [targetTables, setTargetTables] = useState<StandardTargetTable[]>([]);
  const [deleteTarget, setDeleteTarget] = useState<Mapping | null>(null);
  const [deleteBlockers, setDeleteBlockers] = useState<DeleteBlockersResponse | null>(null);

  const roleOptions = useMemo(
    () => [
      ROLE_EMPTY_OPTION,
      ...roleCodes.map((c) => ({ value: c.code, label: c.label })),
    ],
    [roleCodes],
  );

  const targetTableOptions = useMemo(
    () => targetTables.map((t) => ({
      value: t.target_table,
      label: targetTableOptionLabel(t),
    })),
    [targetTables],
  );

  const selectedTargetTable = useMemo(
    () => targetTables.find((t) => normalizeTargetKey(t.target_table) === normalizeTargetKey(form.target_table)),
    [targetTables, form.target_table],
  );

  const standardColumnOptions = useMemo(() => {
    const cols = selectedTargetTable?.standard_columns || [];
    return [
      { value: "", label: "선택" },
      ...cols.map((c) => ({ value: c, label: c })),
    ];
  }, [selectedTargetTable]);

  const isNonStandardTarget = useMemo(() => {
    if (!form.target_table) return false;
    return !targetTables.some((t) => normalizeTargetKey(t.target_table) === normalizeTargetKey(form.target_table));
  }, [form.target_table, targetTables]);

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

  const resetRoleState = () => {
    setColumnRoles([]);
    setRoleSummary(null);
    setRoleValidation(null);
    setTemplateCatalog(null);
    setTemplateError("");
    setExpandedTemplateType(null);
  };

  const syncRolesFromColumns = useCallback((cols: MappingColumn[]) => {
    setColumnRoles((prev) => {
      const prevMap = new Map(prev.map((r) => [r.source_column, r]));
      return cols
        .filter((c) => c.source_column)
        .map((c) => {
          const existing = prevMap.get(c.source_column);
          return existing ?? {
            source_column: c.source_column,
            target_column: c.target_column,
            column_role: null,
            saved: false,
          };
        });
    });
  }, []);

  const loadRecipeTemplates = useCallback(async (mappingId: string) => {
    setTemplateLoading(true);
    setTemplateError("");
    try {
      const res = await getFeatureRecipeTemplates({
        mapping_id: mappingId,
        include_availability: true,
      });
      setTemplateCatalog(res);
    } catch {
      setTemplateCatalog(null);
      setTemplateError("Recipe 템플릿 목록을 불러오지 못했습니다.");
    } finally {
      setTemplateLoading(false);
    }
  }, []);

  const loadRolesForMapping = useCallback(async (mappingId: string, cols: MappingColumn[]) => {
    setRoleLoading(true);
    try {
      const res = await getColumnRoles({ mapping_id: mappingId, include_inferred: true });
      if (res.items.length) {
        setColumnRoles(res.items);
      } else {
        syncRolesFromColumns(cols);
      }
      setRoleSummary(res.summary);
      setRoleValidation(res.validation);
      void loadRecipeTemplates(mappingId);
    } catch {
      syncRolesFromColumns(cols);
    } finally {
      setRoleLoading(false);
    }
  }, [syncRolesFromColumns, loadRecipeTemplates]);

  useEffect(() => {
    load(page);
    fetchApi<PagedData<DataSource>>("/data-sources", { page: 1, size: 100 })
      .then((res) => setSources(res.items))
      .catch(() => {});
    getColumnRoleCodes()
      .then((res) => setRoleCodes(res.items || []))
      .catch(() => {});
    getStandardTargetTables()
      .then((res) => setTargetTables(res.items || []))
      .catch(() => {});
  }, [page]);

  useEffect(() => {
    if (!formOpen || !editingId) return;
    const validCols = form.columns.filter((c) => c.source_column);
    if (validCols.length) {
      void loadRolesForMapping(editingId, validCols);
    }
  }, [formOpen, editingId, form.columns, loadRolesForMapping]);

  const openCreate = () => {
    setEditingId(null);
    setForm({
      ...EMPTY_FORM,
      source_id: sources[0]?.source_id || "",
      target_table: targetTables[0]?.target_table || "",
    });
    resetRoleState();
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
    resetRoleState();
    setFormOpen(true);
  };

  const updateColumn = (idx: number, field: keyof MappingColumn, value: string | boolean) => {
    const cols = [...form.columns];
    cols[idx] = { ...cols[idx], [field]: value };
    setForm({ ...form, columns: cols });
    if (field === "source_column" || field === "target_column") {
      syncRolesFromColumns(cols.filter((c) => c.source_column));
    }
  };

  const updateColumnRole = (sourceColumn: string, role: string) => {
    setColumnRoles((prev) => {
      const idx = prev.findIndex((r) => r.source_column === sourceColumn);
      if (idx >= 0) {
        const next = [...prev];
        next[idx] = { ...next[idx], column_role: role || null, saved: false };
        return next;
      }
      const col = form.columns.find((c) => c.source_column === sourceColumn);
      return [
        ...prev,
        {
          source_column: sourceColumn,
          target_column: col?.target_column,
          column_role: role || null,
          saved: false,
        },
      ];
    });
  };

  const getRoleForColumn = (sourceColumn: string): FeatureColumnRole | undefined =>
    columnRoles.find((r) => r.source_column === sourceColumn);

  const buildRolePayload = () =>
    columnRoles
      .filter((r) => r.source_column && r.column_role)
      .map((r) => ({
        source_column: r.source_column,
        target_column: r.target_column,
        data_type: r.data_type,
        column_role: r.column_role as string,
        description: r.description,
      }));

  const handleApplyInferred = async () => {
    const cols = form.columns.filter((c) => c.source_column);
    if (!cols.length) {
      showToast("warning", "매핑 컬럼을 먼저 입력하세요.");
      return;
    }
    setRoleInferring(true);
    try {
      const res = await inferColumnRoles({
        mapping_id: editingId ?? undefined,
        target_table: form.target_table,
        columns: cols.map((c) => ({
          source_column: c.source_column,
          target_column: c.target_column,
        })),
      });
      setColumnRoles(
        res.items.map((item) => ({
          ...item,
          column_role: item.inferred_role ?? item.column_role,
          saved: false,
        })),
      );
      setRoleSummary(res.summary);
      setRoleValidation(res.validation);
      showToast("success", "추천 역할을 적용했습니다. 저장 전 검증 결과를 확인하세요.");
    } catch {
      showToast("error", "역할 추론에 실패했습니다.");
    } finally {
      setRoleInferring(false);
    }
  };

  const handleValidateRoles = async () => {
    const roles = buildRolePayload();
    if (!roles.length) {
      showToast("warning", "지정된 컬럼 역할이 없습니다.");
      return;
    }
    try {
      const res = await validateColumnRoles({
        mapping_id: editingId ?? undefined,
        roles,
        mapping_columns: form.columns.filter((c) => c.source_column),
      });
      setRoleValidation(res.validation);
      setRoleSummary(res.summary);
      if (res.validation.blocking) {
        showToast("error", res.validation.errors[0] || "검증에 실패했습니다.");
      } else if (res.validation.warnings.length) {
        showToast("warning", `검증 통과 (경고 ${res.validation.warnings.length}건)`);
      } else {
        showToast("success", "컬럼 역할 검증에 성공했습니다.");
      }
    } catch {
      showToast("error", "역할 검증 요청에 실패했습니다.");
    }
  };

  const handleSaveRoles = async () => {
    if (!editingId) {
      showToast("warning", "매핑을 먼저 저장한 뒤 컬럼 역할을 저장할 수 있습니다.");
      return;
    }
    const roles = buildRolePayload();
    if (!roles.length) {
      showToast("warning", "저장할 컬럼 역할이 없습니다.");
      return;
    }
    setRoleSaving(true);
    try {
      const res = await saveColumnRoles({ mapping_id: editingId, roles });
      setColumnRoles(res.items);
      setRoleSummary(res.summary);
      setRoleValidation(res.validation);
      if (editingId) void loadRecipeTemplates(editingId);
      if (res.validation.blocking) {
        showToast("error", res.validation.errors[0] || "저장 후 검증 오류가 있습니다.");
      } else {
        showToast("success", `컬럼 역할 ${res.saved_count}건이 저장되었습니다.`);
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "컬럼 역할 저장에 실패했습니다.";
      showToast("error", msg);
    } finally {
      setRoleSaving(false);
    }
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
        const created = await postApi<{ mapping_id: string }>("/mappings", payload);
        setEditingId(created.mapping_id);
        showToast("success", "매핑이 등록되었습니다. 이제 컬럼 역할을 지정할 수 있습니다.");
      }
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
      const res = await fetchApi<{ fields: { name: string; type?: string }[]; columns?: { name: string }[] }>(
        `/data-sources/${encodeURIComponent(form.source_id)}/discover-schema`,
      );
      const fields = res.fields || res.columns || [];
      const names = fields.map((f) => f.name).filter(Boolean);
      setDiscoveredFields(names);
      if (names.length) {
        const existing = new Set(form.columns.map((c) => c.source_column).filter(Boolean));
        const newCols = names
          .filter((n) => !existing.has(n))
          .map((n) => {
            const field = fields.find((f) => f.name === n);
            return {
              source_column: n,
              target_column: "",
              required_yn: false,
              data_type: field && "type" in field ? field.type : undefined,
            };
          });
        if (newCols.length) {
          const merged = [...form.columns.filter((c) => c.source_column || c.target_column), ...newCols];
          setForm({ ...form, columns: merged });
          syncRolesFromColumns(merged.filter((c) => c.source_column));
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

  const openDelete = async (row: Mapping) => {
    setDeleteTarget(row);
    setDeleteBlockers(null);
    try {
      const res = await fetchApi<DeleteBlockersResponse>(`/mappings/${row.mapping_id}/delete-blockers`);
      setDeleteBlockers(res);
    } catch {
      setDeleteBlockers(null);
    }
  };

  const handleDelete = async () => {
    if (!deleteTarget) return;
    try {
      await deleteApi(`/mappings/${deleteTarget.mapping_id}`);
      showToast("success", "데이터 매핑이 삭제되었습니다.");
      setDeleteTarget(null);
      setDeleteBlockers(null);
      load();
    } catch (err) {
      showToast("error", extractApiErrorMessage(err, "삭제에 실패했습니다."));
    }
  };

  if (loading && !items.length) return <LoadingState />;
  if (error && !items.length) return <ErrorState message={error} onRetry={() => load()} />;

  return (
    <div>
      <PageHeader
        title="데이터 매핑 설정"
        description="원천 컬럼과 표준 스키마 간 매핑 규칙 및 Column Role을 관리합니다."
        actions={<Button icon={<Plus className="w-4 h-4" />} onClick={openCreate}>신규 매핑</Button>}
      />

      <div className="mb-4 text-xs text-slate-600 bg-blue-50 border border-blue-200 rounded-lg p-3 space-y-1">
        <p>{R9_MAPPING_TARGET_NOTE}</p>
        {!targetTables.length && (
          <p className="text-amber-800 font-medium">
            표준 데이터셋 또는 대상 테이블을 먼저 생성하세요.{" "}
            <Link to="/standard-datasets" className="text-blue-600 hover:underline">표준 데이터셋 Wizard</Link>
          </p>
        )}
        <p>임의 테이블 생성은 지원하지 않습니다. 신규 도메인은 <Link to="/standard-datasets" className="text-blue-600 hover:underline">표준 데이터셋</Link>에서 먼저 등록하세요.</p>
        <p>{COLUMN_ROLE_HELP}</p>
        <p>
          매핑 수정 화면에서 {RECIPE_TEMPLATE_SECTION_TITLE}을 확인할 수 있습니다.
          {" "}
          {RECIPE_BUILDER_FUTURE_NOTE}
        </p>
        <p>{RECIPE_PREVIEW_NO_SAVE_NOTE}</p>
        <p>{RECIPE_PREVIEW_ROW_STEP_NOTE}</p>
      </div>

      <DataTable
        loading={loading}
        emptyMessage="등록된 데이터 매핑이 없습니다. 표준 데이터셋 물리 테이블을 먼저 생성한 뒤 매핑을 등록하세요."
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
                  <Button variant="ghost" icon={<Trash2 className="w-3 h-3" />} onClick={() => openDelete(row)}>삭제</Button>
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
            <Button onClick={handleSave} disabled={saving}>{saving ? "저장 중..." : "매핑 저장"}</Button>
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
              <SelectInput
                value={form.target_table}
                onChange={(v) => setForm({ ...form, target_table: v })}
                options={
                  targetTableOptions.length
                    ? targetTableOptions
                    : [{ value: "", label: "표준 데이터셋 물리 테이블을 먼저 생성하세요" }]
                }
              />
              {!targetTables.length && (
                <p className="text-[11px] text-amber-700 mt-1">
                  ACTIVE 상태의 표준 데이터셋 물리 테이블이 없습니다.
                </p>
              )}
              {isNonStandardTarget && (
                <p className="text-[11px] text-amber-700 mt-1">
                  현재 매핑은 표준 대상 테이블에 등록되어 있지 않습니다. 수정 저장하려면 표준 대상 테이블을 선택해야 합니다.
                </p>
              )}
              {selectedTargetTable && (
                <p className="text-[11px] text-slate-500 mt-1">
                  표준 컬럼: {selectedTargetTable.standard_columns.join(", ")}
                </p>
              )}
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
            <div className="grid grid-cols-[1fr_1fr_140px] gap-2 mb-1 text-[11px] text-slate-500 px-1">
              <span>원천 컬럼</span>
              <span>표준 컬럼</span>
              <span>컬럼 역할</span>
            </div>
            {form.columns.map((col, idx) => {
              const roleRow = getRoleForColumn(col.source_column);
              const role = roleRow?.column_role;
              const inferred = roleRow?.inferred_role;
              const showSuggest = !role && inferred;
              return (
                <div key={idx} className="grid grid-cols-[1fr_1fr_140px] gap-2 mb-2 items-start">
                  <TextInput
                    value={col.source_column}
                    onChange={(v) => updateColumn(idx, "source_column", v)}
                    placeholder="원천 컬럼"
                  />
                  {standardColumnOptions.length > 1 ? (
                    <SelectInput
                      value={col.target_column}
                      onChange={(v) => updateColumn(idx, "target_column", v)}
                      options={standardColumnOptions}
                    />
                  ) : (
                    <TextInput
                      value={col.target_column}
                      onChange={(v) => updateColumn(idx, "target_column", v)}
                      placeholder="표준 컬럼"
                    />
                  )}
                  <div className="space-y-1">
                    <SelectInput
                      value={role || ""}
                      onChange={(v) => {
                        if (col.source_column) updateColumnRole(col.source_column, v);
                      }}
                      options={roleOptions}
                    />
                    {role && (
                      <span className={`inline-flex text-[10px] px-1 py-0.5 rounded border ${roleBadgeClass(role)}`}>
                        {roleRow?.saved ? "저장됨" : "미저장"}
                      </span>
                    )}
                    {showSuggest && (
                      <span className="block text-[10px] text-amber-700">
                        추천: {roleLabel(inferred, roleCodes)}
                      </span>
                    )}
                  </div>
                </div>
              );
            })}
            <Button
              variant="ghost"
              onClick={() => setForm({
                ...form,
                columns: [...form.columns, { source_column: "", target_column: "", required_yn: false }],
              })}
            >
              + 컬럼 행 추가
            </Button>
          </div>

          <div className="border-t border-slate-200 pt-3">
            <button
              type="button"
              className="flex items-center justify-between w-full text-sm font-semibold text-slate-800 mb-2"
              onClick={() => setRoleSectionOpen((v) => !v)}
            >
              Column Role
              <span className="text-xs text-slate-500">{roleSectionOpen ? "접기" : "펼치기"}</span>
            </button>
            {roleSectionOpen && (
              <div className="space-y-3">
                <p className="text-[11px] text-slate-500">{COLUMN_ROLE_INFERENCE_NOTE}</p>
                {!editingId && (
                  <p className="text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded p-2">
                    매핑을 먼저 저장하면 컬럼 역할을 DB에 저장할 수 있습니다.
                  </p>
                )}
                <div className="flex flex-wrap gap-2">
                  <Button
                    variant="secondary"
                    icon={<Sparkles className="w-3 h-3" />}
                    disabled={roleInferring}
                    onClick={handleApplyInferred}
                  >
                    {roleInferring ? "추론 중..." : "표준 역할 적용"}
                  </Button>
                  <Button variant="secondary" icon={<CheckCircle className="w-3 h-3" />} onClick={handleValidateRoles}>
                    역할 검증
                  </Button>
                  <Button
                    variant="primary"
                    icon={<Save className="w-3 h-3" />}
                    disabled={roleSaving || !editingId}
                    onClick={handleSaveRoles}
                  >
                    {roleSaving ? "저장 중..." : "컬럼 역할 저장"}
                  </Button>
                </div>
                {roleLoading && <p className="text-xs text-slate-400">컬럼 역할 불러오는 중...</p>}
                <RoleCoverageCard summary={roleSummary} />
                <ValidationPanel validation={roleValidation} />
                <div className="border-t border-slate-100 pt-3">
                  <button
                    type="button"
                    className="flex items-center justify-between w-full text-sm font-semibold text-slate-800 mb-2"
                    onClick={() => setTemplateSectionOpen((v) => !v)}
                  >
                    {RECIPE_TEMPLATE_SECTION_TITLE}
                    <span className="text-xs text-slate-500">{templateSectionOpen ? "접기" : "펼치기"}</span>
                  </button>
                  {templateSectionOpen && (
                    <RecipeTemplatesSection
                      catalog={templateCatalog}
                      loading={templateLoading}
                      error={templateError}
                      expandedType={expandedTemplateType}
                      mappingId={editingId}
                      onToggle={(type) => setExpandedTemplateType((prev) => (prev === type ? null : type))}
                      onPreview={(tpl) => {
                        setRecipePreviewTemplate(tpl);
                        setRecipePreviewOpen(true);
                      }}
                    />
                  )}
                </div>
              </div>
            )}
          </div>
        </div>
      </Modal>

      <Modal
        open={previewOpen}
        title={`변환 미리보기 - ${previewTitle}`}
        onClose={() => setPreviewOpen(false)}
        size="xl"
        footer={<Button variant="secondary" onClick={() => setPreviewOpen(false)}>닫기</Button>}
      >
        <div className="overflow-x-auto -mx-5 px-5">
          <DataTable
            columns={previewRows.length ? Object.keys(previewRows[0]).map((k) => ({ key: k, header: k })) : []}
            data={previewRows}
          />
        </div>
      </Modal>

      {recipePreviewTemplate && editingId && (
        <FeatureRecipePreviewModal
          open={recipePreviewOpen}
          onClose={() => {
            setRecipePreviewOpen(false);
            setRecipePreviewTemplate(null);
          }}
          template={recipePreviewTemplate}
          mappingId={editingId}
          columns={form.columns}
          columnRoles={columnRoles}
        />
      )}

      <Modal
        open={!!deleteTarget}
        title="삭제 확인"
        onClose={() => { setDeleteTarget(null); setDeleteBlockers(null); }}
        footer={(
          <>
            <Button variant="secondary" onClick={() => { setDeleteTarget(null); setDeleteBlockers(null); }}>취소</Button>
            <Button variant="danger" onClick={handleDelete} disabled={deleteBlockers?.can_delete === false}>삭제</Button>
          </>
        )}
      >
        <p className="text-sm text-slate-600">
          <strong>{deleteTarget?.mapping_name}</strong> 매핑을 삭제하시겠습니까? 연결된 Column Role도 함께 삭제됩니다.
        </p>
        {deleteBlockers && !deleteBlockers.can_delete && (
          <div className="mt-3 text-xs text-amber-800 bg-amber-50 border border-amber-200 rounded-lg p-3 space-y-1">
            <p className="font-medium">아래 연결 때문에 삭제할 수 없습니다.</p>
            {deleteBlockers.blockers.map((b) => (
              <p key={b.code}>• {b.message}</p>
            ))}
            <p className="text-slate-600 pt-1">
              <Link to="/feature-recipes" className="text-blue-600 hover:underline">Feature Recipe</Link>
              {" "}화면에서 연결된 Recipe를 먼저 삭제·비활성화하거나 다른 매핑으로 변경하세요.
            </p>
          </div>
        )}
      </Modal>
    </div>
  );
}
