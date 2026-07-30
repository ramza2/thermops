import { useCallback, useEffect, useMemo, useState, type ChangeEvent } from "react";
import type {
  VisualPipelineComponentConfigSchema,
  VisualPipelineNodeConfigValues,
} from "@/types/visualPipeline";
import type { DatasetCategoryOption, StandardDatasetType } from "@/types/standardDatasets";
import { getStandardDatasetMetadataOptions } from "@/api/standardDatasets";
import { VpColumnListField } from "@/components/visualPipeline/config/VpColumnListField";
import { VpConfigFieldShell } from "@/components/visualPipeline/config/VpConfigFieldShell";
import {
  DEFAULT_DATASET_CATEGORY,
  STANDARD_DATASET_INLINE_CREATE_HINT,
  STANDARD_DATASET_LIST_HINT,
  STANDARD_DATASET_SEARCH_HINT,
  STANDARD_DATASET_SEARCH_PLACEHOLDER,
  createInlineStandardDataset,
  createStandardDatasetErrorMessage,
  fetchActiveStandardDatasets,
  fetchStandardDatasetById,
  formatStandardDatasetOptionLabel,
  mergeStandardDatasetItems,
  selectedStandardDatasetMissingLabel,
  suggestStandardTargetTable,
} from "@/constants/standardDatasetList";

const INPUT_CLASS =
  "h-8 px-2.5 text-xs border border-slate-300 rounded-md w-full focus:outline-none focus:ring-1 focus:ring-blue-500 bg-white disabled:bg-slate-50 disabled:text-slate-400";

const BTN_SECONDARY =
  "inline-flex items-center justify-center h-8 px-2.5 text-xs font-medium border border-slate-300 rounded-md bg-white text-slate-700 hover:bg-slate-50 disabled:opacity-50";
const BTN_GHOST =
  "inline-flex items-center justify-center h-8 px-2 text-xs font-medium text-slate-600 hover:bg-slate-100 rounded-md disabled:opacity-50";
const BTN_PRIMARY =
  "inline-flex items-center justify-center h-8 px-2.5 text-xs font-medium rounded-md bg-blue-700 text-white hover:bg-blue-800 disabled:opacity-50";

const WRITE_MODE_OPTIONS = ["INSERT_ONLY", "DEDUPLICATE", "UPSERT"] as const;
const DUPLICATE_POLICY_OPTIONS = ["KEEP_FIRST", "KEEP_LAST", "ERROR"] as const;
const NULL_UPDATE_OPTIONS = ["KEEP_EXISTING", "OVERWRITE_WITH_NULL"] as const;

export type VpUpsertLoadConfigFormProps = {
  values: VisualPipelineNodeConfigValues;
  schema?: VisualPipelineComponentConfigSchema | null;
  fieldWarnings?: Record<string, string>;
  onChange: (patch: Record<string, unknown>) => void;
  disabled?: boolean;
};

function strVal(values: VisualPipelineNodeConfigValues, key: string): string {
  const v = values[key];
  return v == null ? "" : String(v);
}

function boolVal(values: VisualPipelineNodeConfigValues, key: string, fallback = false): boolean {
  const v = values[key];
  if (typeof v === "boolean") return v;
  return fallback;
}

const EMPTY_CREATE = {
  dataset_type_name: "",
  dataset_type_code: "",
  dataset_category: DEFAULT_DATASET_CATEGORY,
  business_domain: "",
  description: "",
  target_table: "",
  column_name: "",
};

export function VpUpsertLoadConfigForm({ values, fieldWarnings, onChange, disabled }: VpUpsertLoadConfigFormProps) {
  const writeMode = strVal(values, "write_mode");
  const conflictRequired = writeMode === "DEDUPLICATE" || writeMode === "UPSERT";
  const warn = (key: string) => fieldWarnings?.[key];
  const selectedId = strVal(values, "standard_dataset_id");

  const patchText = (key: string) => (e: ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    const raw = e.target.value;
    onChange({ [key]: raw === "" ? undefined : raw });
  };

  const [datasets, setDatasets] = useState<StandardDatasetType[]>([]);
  const [datasetsLoadError, setDatasetsLoadError] = useState(false);
  const [datasetsLoading, setDatasetsLoading] = useState(false);
  const [searchDraft, setSearchDraft] = useState("");
  const [searchApplied, setSearchApplied] = useState("");
  const [selectedLabel, setSelectedLabel] = useState<string | null>(null);
  const [selectedMissingMeta, setSelectedMissingMeta] = useState<StandardDatasetType | null>(null);
  const [showAdvancedId, setShowAdvancedId] = useState(false);
  const [createOpen, setCreateOpen] = useState(false);
  const [createForm, setCreateForm] = useState(EMPTY_CREATE);
  const [categoryOptions, setCategoryOptions] = useState<DatasetCategoryOption[]>([]);
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);
  const [createSuccess, setCreateSuccess] = useState<string | null>(null);
  const [suggestingTable, setSuggestingTable] = useState(false);

  const loadDatasets = useCallback(async (keyword?: string) => {
    setDatasetsLoading(true);
    try {
      const items = await fetchActiveStandardDatasets(keyword);
      setDatasets(items);
      setDatasetsLoadError(false);
    } catch {
      setDatasets([]);
      setDatasetsLoadError(true);
    } finally {
      setDatasetsLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadDatasets();
    void getStandardDatasetMetadataOptions()
      .then((opts) => setCategoryOptions(opts.dataset_categories || []))
      .catch(() => setCategoryOptions([]));
  }, [loadDatasets]);

  const selectedMissing =
    Boolean(selectedId) && !datasets.some((d) => d.dataset_type_id === selectedId);

  useEffect(() => {
    if (!selectedId || !selectedMissing) {
      if (!selectedMissing) {
        setSelectedLabel(null);
        setSelectedMissingMeta(null);
      }
      return;
    }
    let cancelled = false;
    void fetchStandardDatasetById(selectedId).then((item) => {
      if (cancelled) return;
      setSelectedMissingMeta(item);
      setSelectedLabel(item ? `${item.dataset_type_name} (${item.dataset_type_code})` : null);
    });
    return () => {
      cancelled = true;
    };
  }, [selectedId, selectedMissing]);

  const selectOptions = useMemo(() => {
    const opts = datasets.map((d) => ({
      value: d.dataset_type_id,
      label: formatStandardDatasetOptionLabel(d),
    }));
    if (selectedId && !opts.some((o) => o.value === selectedId)) {
      opts.unshift({
        value: selectedId,
        label: selectedStandardDatasetMissingLabel(selectedId, selectedLabel),
      });
    }
    return opts;
  }, [datasets, selectedId, selectedLabel]);

  const applyDatasetSelection = (item: StandardDatasetType) => {
    onChange({
      standard_dataset_id: item.dataset_type_id,
      target_table: item.target_table || undefined,
    });
    setCreateSuccess(null);
  };

  const handleSelectChange = (e: ChangeEvent<HTMLSelectElement>) => {
    const raw = e.target.value;
    if (!raw) {
      onChange({ standard_dataset_id: undefined });
      setCreateSuccess(null);
      return;
    }
    const found = datasets.find((d) => d.dataset_type_id === raw);
    if (found) {
      applyDatasetSelection(found);
      return;
    }
    // Preserve missing selection without wiping target_table.
    onChange({ standard_dataset_id: raw });
    setCreateSuccess(null);
  };

  const handleSuggestTable = async (code: string) => {
    if (!code.trim()) return;
    setSuggestingTable(true);
    try {
      const table = await suggestStandardTargetTable(code);
      if (table) setCreateForm((prev) => ({ ...prev, target_table: table }));
    } finally {
      setSuggestingTable(false);
    }
  };

  const handleCreate = async () => {
    if (disabled || creating) return;
    setCreateError(null);
    setCreateSuccess(null);
    setCreating(true);
    try {
      const columns = createForm.column_name.trim()
        ? [
            {
              column_name: createForm.column_name.trim(),
              data_type: "VARCHAR",
              data_length: 100,
              required: false,
              primary_key: false,
            },
          ]
        : [];
      const created = await createInlineStandardDataset({
        dataset_type_name: createForm.dataset_type_name,
        dataset_type_code: createForm.dataset_type_code,
        dataset_category: createForm.dataset_category,
        business_domain: createForm.business_domain,
        description: createForm.description,
        target_table: createForm.target_table,
        columns,
      });
      if (!created?.dataset_type_id) throw new Error("등록 응답에 dataset_type_id가 없습니다.");

      setDatasets((prev) => mergeStandardDatasetItems([created], prev));
      setSelectedLabel(`${created.dataset_type_name} (${created.dataset_type_code})`);
      applyDatasetSelection(created);

      setCreateSuccess("새 표준 데이터셋을 등록하고 현재 노드에 선택했습니다.");
      setCreateOpen(false);
      setCreateForm(EMPTY_CREATE);
    } catch (err) {
      setCreateError(createStandardDatasetErrorMessage(err));
    } finally {
      setCreating(false);
    }
  };

  const categorySelectOptions = useMemo(() => {
    const opts = categoryOptions.map((c) => ({ value: c.code, label: `${c.name} (${c.code})` }));
    if (!opts.some((o) => o.value === DEFAULT_DATASET_CATEGORY)) {
      opts.unshift({ value: DEFAULT_DATASET_CATEGORY, label: `사용자 정의 (${DEFAULT_DATASET_CATEGORY})` });
    }
    return opts;
  }, [categoryOptions]);

  const missingWarning =
    selectedMissing && selectedId
      ? selectedMissingMeta &&
          (selectedMissingMeta.active === false ||
            String(selectedMissingMeta.status || "").toUpperCase() === "ARCHIVED")
        ? "현재 선택된 표준 데이터셋은 보관되었거나 기본 목록에 없습니다. 다른 대상을 선택해 주세요."
        : "현재 선택된 표준 데이터셋은 기본 목록에 없습니다. 선택값은 유지됩니다."
      : null;

  return (
    <div className="space-y-3" data-testid="visual-pipeline-inspector-config-form">
      <section className="rounded-lg border border-slate-100 p-2.5 space-y-2.5">
        <div className="text-[9px] font-bold text-slate-400 uppercase tracking-wide">Target</div>

        <VpConfigFieldShell
          fieldKey="standard_dataset_id"
          label="표준 데이터셋"
          help="표준 데이터셋 참조. 선택 시 target_table을 함께 채웁니다."
          warning={warn("standard_dataset_id")}
        >
          <div className="space-y-2" data-testid="visual-pipeline-standard-dataset-picker">
            <p className="text-[10px] text-slate-500" data-testid="visual-pipeline-standard-dataset-list-hint">
              {STANDARD_DATASET_LIST_HINT}
            </p>
            <p className="text-[10px] text-slate-500" data-testid="visual-pipeline-standard-dataset-search-hint">
              {STANDARD_DATASET_SEARCH_HINT}
            </p>
            <div className="flex flex-wrap gap-1.5">
              <input
                type="text"
                value={searchDraft}
                onChange={(e) => setSearchDraft(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") {
                    setSearchApplied(searchDraft);
                    void loadDatasets(searchDraft);
                  }
                }}
                placeholder={STANDARD_DATASET_SEARCH_PLACEHOLDER}
                disabled={disabled}
                className={`${INPUT_CLASS} flex-1 min-w-[120px]`}
                data-testid="visual-pipeline-standard-dataset-search-input"
              />
              <button
                type="button"
                className={BTN_SECONDARY}
                disabled={disabled || datasetsLoading}
                data-testid="visual-pipeline-standard-dataset-search-button"
                onClick={() => {
                  setSearchApplied(searchDraft);
                  void loadDatasets(searchDraft);
                }}
              >
                검색
              </button>
              <button
                type="button"
                className={BTN_GHOST}
                disabled={disabled || datasetsLoading}
                onClick={() => {
                  setSearchDraft("");
                  setSearchApplied("");
                  void loadDatasets();
                }}
              >
                초기화
              </button>
              <button
                type="button"
                className={BTN_GHOST}
                disabled={disabled || datasetsLoading}
                data-testid="visual-pipeline-standard-dataset-refresh-button"
                onClick={() => void loadDatasets(searchApplied || undefined)}
              >
                새로고침
              </button>
            </div>
            <p className="text-[10px] text-slate-400">
              {datasetsLoading ? "목록 로딩 중…" : `로드됨 ${datasets.length}건`}
              {searchApplied ? ` · 검색어 "${searchApplied}"` : ""}
            </p>
            <select
              value={selectedId}
              onChange={handleSelectChange}
              disabled={disabled}
              className={INPUT_CLASS}
              data-testid="visual-pipeline-standard-dataset-select"
            >
              <option value="">표준 데이터셋 선택</option>
              {selectOptions.map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </select>
            {missingWarning && (
              <p className="text-[10px] text-amber-700" data-testid="visual-pipeline-standard-dataset-selected-missing">
                {missingWarning}
              </p>
            )}
            {datasetsLoadError && datasets.length === 0 && (
              <p className="text-[10px] text-red-700">표준 데이터셋 목록을 불러오지 못했습니다.</p>
            )}

            <div className="pt-1 space-y-2">
              <button
                type="button"
                className={BTN_SECONDARY}
                disabled={disabled}
                data-testid="visual-pipeline-standard-dataset-create-toggle"
                onClick={() => {
                  setCreateOpen((v) => !v);
                  setCreateError(null);
                }}
              >
                {createOpen ? "등록 취소" : "+ 새 표준 데이터셋 등록"}
              </button>
              {createOpen && (
                <div
                  className="rounded-md border border-slate-200 bg-slate-50 p-2.5 space-y-2"
                  data-testid="visual-pipeline-standard-dataset-create-form"
                >
                  <p className="text-[10px] text-amber-800" data-testid="visual-pipeline-standard-dataset-create-hint">
                    {STANDARD_DATASET_INLINE_CREATE_HINT}
                  </p>
                  <label className="block text-[10px] text-slate-500">데이터셋명 *</label>
                  <input
                    className={INPUT_CLASS}
                    value={createForm.dataset_type_name}
                    disabled={disabled || creating}
                    data-testid="visual-pipeline-standard-dataset-create-name"
                    onChange={(e) => setCreateForm({ ...createForm, dataset_type_name: e.target.value })}
                    placeholder="B20 Studio Upsert Dataset"
                  />
                  <label className="block text-[10px] text-slate-500">데이터셋 코드 *</label>
                  <input
                    className={INPUT_CLASS}
                    value={createForm.dataset_type_code}
                    disabled={disabled || creating}
                    data-testid="visual-pipeline-standard-dataset-create-code"
                    onChange={(e) => {
                      const code = e.target.value;
                      setCreateForm((prev) => ({ ...prev, dataset_type_code: code }));
                    }}
                    onBlur={() => void handleSuggestTable(createForm.dataset_type_code)}
                    placeholder="B20_UPSERT_SAMPLE"
                  />
                  <label className="block text-[10px] text-slate-500">데이터 분류 *</label>
                  <select
                    className={INPUT_CLASS}
                    value={createForm.dataset_category}
                    disabled={disabled || creating}
                    data-testid="visual-pipeline-standard-dataset-create-category"
                    onChange={(e) => setCreateForm({ ...createForm, dataset_category: e.target.value })}
                  >
                    {categorySelectOptions.map((o) => (
                      <option key={o.value} value={o.value}>
                        {o.label}
                      </option>
                    ))}
                  </select>
                  <label className="block text-[10px] text-slate-500">업무 영역</label>
                  <input
                    className={INPUT_CLASS}
                    value={createForm.business_domain}
                    disabled={disabled || creating}
                    onChange={(e) => setCreateForm({ ...createForm, business_domain: e.target.value })}
                    placeholder="선택 입력"
                  />
                  <label className="block text-[10px] text-slate-500">설명</label>
                  <input
                    className={INPUT_CLASS}
                    value={createForm.description}
                    disabled={disabled || creating}
                    onChange={(e) => setCreateForm({ ...createForm, description: e.target.value })}
                  />
                  <div className="flex items-end gap-1.5">
                    <div className="flex-1">
                      <label className="block text-[10px] text-slate-500">물리 테이블명 *</label>
                      <input
                        className={INPUT_CLASS}
                        value={createForm.target_table}
                        disabled={disabled || creating}
                        data-testid="visual-pipeline-standard-dataset-create-target-table"
                        onChange={(e) => setCreateForm({ ...createForm, target_table: e.target.value })}
                        placeholder="std_b20_upsert_sample"
                      />
                    </div>
                    <button
                      type="button"
                      className={BTN_GHOST}
                      disabled={disabled || creating || suggestingTable || !createForm.dataset_type_code.trim()}
                      data-testid="visual-pipeline-standard-dataset-suggest-table"
                      onClick={() => void handleSuggestTable(createForm.dataset_type_code)}
                    >
                      {suggestingTable ? "제안 중…" : "테이블명 제안"}
                    </button>
                  </div>
                  <label className="block text-[10px] text-slate-500">최소 컬럼 (선택)</label>
                  <input
                    className={INPUT_CLASS}
                    value={createForm.column_name}
                    disabled={disabled || creating}
                    data-testid="visual-pipeline-standard-dataset-create-column"
                    onChange={(e) => setCreateForm({ ...createForm, column_name: e.target.value })}
                    placeholder="비우면 columns=[] · 예: entity_id"
                  />
                  {createError && (
                    <p className="text-[10px] text-red-700" data-testid="visual-pipeline-standard-dataset-create-error">
                      {createError}
                    </p>
                  )}
                  <button
                    type="button"
                    className={BTN_PRIMARY}
                    disabled={disabled || creating}
                    data-testid="visual-pipeline-standard-dataset-create-submit"
                    onClick={() => void handleCreate()}
                  >
                    {creating ? "등록 중…" : "등록 후 선택"}
                  </button>
                </div>
              )}
              {createSuccess && (
                <p className="text-[10px] text-emerald-700" data-testid="visual-pipeline-standard-dataset-create-success">
                  {createSuccess}
                </p>
              )}
            </div>

            <button
              type="button"
              className={BTN_GHOST}
              disabled={disabled}
              data-testid="visual-pipeline-standard-dataset-advanced-toggle"
              onClick={() => setShowAdvancedId((v) => !v)}
            >
              {showAdvancedId ? "고급 ID 입력 숨기기" : "고급: ID 직접 입력"}
            </button>
            {showAdvancedId && (
              <input
                type="text"
                value={selectedId}
                onChange={patchText("standard_dataset_id")}
                placeholder="SD-001"
                disabled={disabled}
                className={INPUT_CLASS}
                data-testid="visual-pipeline-standard-dataset-id-input"
              />
            )}
          </div>
        </VpConfigFieldShell>

        <VpConfigFieldShell
          fieldKey="target_table"
          label="Target Table"
          required
          help="적재 대상 물리 테이블명. 표준 데이터셋 선택/생성 시 자동 채움, 수동 수정 가능"
          warning={warn("target_table")}
        >
          <input
            type="text"
            value={strVal(values, "target_table")}
            onChange={patchText("target_table")}
            placeholder="tb_sample_fact"
            disabled={disabled}
            className={INPUT_CLASS}
            data-testid="visual-pipeline-target-table-input"
          />
        </VpConfigFieldShell>
      </section>

      <section className="rounded-lg border border-slate-100 p-2.5 space-y-2.5">
        <div className="text-[9px] font-bold text-slate-400 uppercase tracking-wide">Write Policy</div>
        <VpConfigFieldShell fieldKey="write_mode" label="Write Mode" required warning={warn("write_mode")}>
          <select
            value={writeMode}
            onChange={patchText("write_mode")}
            disabled={disabled}
            className={INPUT_CLASS}
          >
            {!writeMode && <option value="">선택하세요</option>}
            {WRITE_MODE_OPTIONS.map((opt) => (
              <option key={opt} value={opt}>
                {opt}
              </option>
            ))}
          </select>
        </VpConfigFieldShell>
        <VpColumnListField
          fieldKey="conflict_key_columns_json"
          label="Conflict Key Columns"
          value={values.conflict_key_columns_json}
          placeholder="entity_id, measured_at"
          required={conflictRequired}
          help={
            conflictRequired
              ? "DEDUPLICATE/UPSERT 시 conflict key가 필요합니다 (저장은 차단하지 않음)."
              : "쉼표로 구분된 컬럼 목록 → string[]로 저장"
          }
          warning={warn("conflict_key_columns_json")}
          disabled={disabled}
          onChange={onChange}
        />
      </section>

      <section className="rounded-lg border border-slate-100 p-2.5 space-y-2.5">
        <div className="text-[9px] font-bold text-slate-400 uppercase tracking-wide">Dedup</div>
        <VpConfigFieldShell
          fieldKey="duplicate_within_batch_policy"
          label="Duplicate Within Batch"
          warning={warn("duplicate_within_batch_policy")}
        >
          <select
            value={strVal(values, "duplicate_within_batch_policy")}
            onChange={patchText("duplicate_within_batch_policy")}
            disabled={disabled}
            className={INPUT_CLASS}
          >
            {!strVal(values, "duplicate_within_batch_policy") && <option value="">선택하세요</option>}
            {DUPLICATE_POLICY_OPTIONS.map((opt) => (
              <option key={opt} value={opt}>
                {opt}
              </option>
            ))}
          </select>
        </VpConfigFieldShell>
        <VpConfigFieldShell
          fieldKey="null_update_policy"
          label="Null Update Policy"
          warning={warn("null_update_policy")}
        >
          <select
            value={strVal(values, "null_update_policy")}
            onChange={patchText("null_update_policy")}
            disabled={disabled}
            className={INPUT_CLASS}
          >
            {!strVal(values, "null_update_policy") && <option value="">선택하세요</option>}
            {NULL_UPDATE_OPTIONS.map((opt) => (
              <option key={opt} value={opt}>
                {opt}
              </option>
            ))}
          </select>
        </VpConfigFieldShell>
        <VpConfigFieldShell
          fieldKey="save_dedup_summary_yn"
          label="Save Dedup Summary"
          warning={warn("save_dedup_summary_yn")}
        >
          <label className="inline-flex items-center gap-2 text-[11px] text-slate-600">
            <input
              type="checkbox"
              checked={boolVal(values, "save_dedup_summary_yn", true)}
              onChange={(e) => onChange({ save_dedup_summary_yn: e.target.checked })}
              disabled={disabled}
              className="rounded border-slate-300"
            />
            중복 제거 요약 저장
          </label>
        </VpConfigFieldShell>
      </section>

      <div className="space-y-1 text-[9px] text-slate-500 leading-relaxed px-0.5">
        <p>설정 변경사항은 Graph 저장 시 함께 저장됩니다.</p>
        <p className="text-amber-700">
          실제 적재 정책 적용과 compile 연계는 R11-S6 이후 단계에서 적용됩니다.
        </p>
      </div>
    </div>
  );
}
