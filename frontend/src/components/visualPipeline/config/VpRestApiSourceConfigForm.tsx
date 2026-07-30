import { useCallback, useEffect, useMemo, useState, type ChangeEvent } from "react";
import type {
  VisualPipelineComponentConfigSchema,
  VisualPipelineNodeConfigValues,
} from "@/types/visualPipeline";
import { VpConfigFieldShell } from "@/components/visualPipeline/config/VpConfigFieldShell";
import { VpJsonTextareaField } from "@/components/visualPipeline/config/VpJsonTextareaField";
import {
  DATA_SOURCE_CREDENTIAL_REF_HELP,
  DATA_SOURCE_DOMAIN_OPTIONS,
  DATA_SOURCE_INLINE_CREATE_AUTH_HINT,
  DATA_SOURCE_LIST_HINT,
  DATA_SOURCE_SEARCH_HINT,
  DATA_SOURCE_SEARCH_PLACEHOLDER,
  DEFAULT_DATA_SOURCE_DOMAIN,
  type DataSourceListItem,
  createDataSourceErrorMessage,
  createRestDataSource,
  fetchDataSourceById,
  fetchDataSourcesPage,
  filterDataSourcesLocal,
  isRestApiDataSourceType,
  mergeDataSourcePages,
  selectedDataSourceMissingLabel,
} from "@/constants/dataSourceList";

const INPUT_CLASS =
  "h-8 px-2.5 text-xs border border-slate-300 rounded-md w-full focus:outline-none focus:ring-1 focus:ring-blue-500 bg-white disabled:bg-slate-50 disabled:text-slate-400";

const BTN_SECONDARY =
  "inline-flex items-center justify-center h-8 px-2.5 text-xs font-medium border border-slate-300 rounded-md bg-white text-slate-700 hover:bg-slate-50 disabled:opacity-50";
const BTN_GHOST =
  "inline-flex items-center justify-center h-8 px-2 text-xs font-medium text-slate-600 hover:bg-slate-100 rounded-md disabled:opacity-50";
const BTN_PRIMARY =
  "inline-flex items-center justify-center h-8 px-2.5 text-xs font-medium rounded-md bg-blue-700 text-white hover:bg-blue-800 disabled:opacity-50";

export type VpRestApiSourceConfigFormProps = {
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

const EMPTY_CREATE = {
  source_name: "",
  data_domain: DEFAULT_DATA_SOURCE_DOMAIN,
  base_url: "",
  endpoint: "",
  item_path: "data.items",
};

export function VpRestApiSourceConfigForm({
  values,
  fieldWarnings,
  onChange,
  disabled,
}: VpRestApiSourceConfigFormProps) {
  const patchText = (key: string) => (e: ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    const raw = e.target.value;
    onChange({ [key]: raw === "" ? undefined : raw });
  };
  const warn = (key: string) => fieldWarnings?.[key];
  const selectedId = strVal(values, "data_source_id");

  const [sources, setSources] = useState<DataSourceListItem[]>([]);
  const [sourcesPage, setSourcesPage] = useState(1);
  const [sourcesTotalPages, setSourcesTotalPages] = useState(1);
  const [sourcesTotalCount, setSourcesTotalCount] = useState(0);
  const [sourcesLoadError, setSourcesLoadError] = useState(false);
  const [sourcesLoading, setSourcesLoading] = useState(false);
  const [sourcesLoadingMore, setSourcesLoadingMore] = useState(false);
  const [searchDraft, setSearchDraft] = useState("");
  const [searchApplied, setSearchApplied] = useState("");
  const [selectedLabel, setSelectedLabel] = useState<string | null>(null);
  const [showAdvancedId, setShowAdvancedId] = useState(false);
  const [createOpen, setCreateOpen] = useState(false);
  const [createForm, setCreateForm] = useState(EMPTY_CREATE);
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);
  const [createSuccess, setCreateSuccess] = useState<string | null>(null);

  const loadSourcesPage = useCallback(async (page: number, mode: "replace" | "append") => {
    if (mode === "append") setSourcesLoadingMore(true);
    else setSourcesLoading(true);
    try {
      const res = await fetchDataSourcesPage(page);
      const items = res.items || [];
      setSources((prev) => (mode === "append" ? mergeDataSourcePages(prev, items) : items));
      setSourcesPage(res.page || page);
      setSourcesTotalPages(Math.max(1, res.total_pages || 1));
      setSourcesTotalCount(res.total_count ?? items.length);
      setSourcesLoadError(false);
    } catch {
      if (mode === "replace") {
        setSources([]);
        setSourcesPage(1);
        setSourcesTotalPages(1);
        setSourcesTotalCount(0);
        setSourcesLoadError(true);
      }
    } finally {
      setSourcesLoading(false);
      setSourcesLoadingMore(false);
    }
  }, []);

  useEffect(() => {
    void loadSourcesPage(1, "replace");
  }, [loadSourcesPage]);

  const restSources = useMemo(
    () => sources.filter((s) => isRestApiDataSourceType(s.source_type)),
    [sources],
  );

  const filteredSources = useMemo(
    () => filterDataSourcesLocal(restSources, searchApplied),
    [restSources, searchApplied],
  );

  const selectedMissing =
    Boolean(selectedId) && !restSources.some((s) => s.source_id === selectedId);

  useEffect(() => {
    if (!selectedId || !selectedMissing) {
      if (!selectedMissing) setSelectedLabel(null);
      return;
    }
    let cancelled = false;
    void fetchDataSourceById(selectedId).then((item) => {
      if (cancelled) return;
      setSelectedLabel(item?.source_name || null);
    });
    return () => {
      cancelled = true;
    };
  }, [selectedId, selectedMissing]);

  const selectOptions = useMemo(() => {
    const opts = filteredSources.map((s) => ({
      value: s.source_id,
      label: `${s.source_name} (${s.source_id})`,
    }));
    if (selectedId && !opts.some((o) => o.value === selectedId)) {
      opts.unshift({
        value: selectedId,
        label: selectedDataSourceMissingLabel(selectedId, selectedLabel),
      });
    }
    return opts;
  }, [filteredSources, selectedId, selectedLabel]);

  const handleSelectChange = (e: ChangeEvent<HTMLSelectElement>) => {
    const raw = e.target.value;
    onChange({ data_source_id: raw === "" ? undefined : raw });
    setCreateSuccess(null);
  };

  const handleCreate = async () => {
    if (disabled || creating) return;
    setCreateError(null);
    setCreateSuccess(null);
    setCreating(true);
    try {
      const created = await createRestDataSource({
        source_name: createForm.source_name,
        data_domain: createForm.data_domain,
        base_url: createForm.base_url,
        endpoint: createForm.endpoint,
        item_path: createForm.item_path,
        active_yn: true,
      });
      const sourceId = created.source_id;
      if (!sourceId) throw new Error("등록 응답에 source_id가 없습니다.");

      const provisional: DataSourceListItem = {
        source_id: sourceId,
        source_name: createForm.source_name.trim(),
        source_type: "REST_API",
        data_domain: createForm.data_domain,
        connection_info: { base_url: createForm.base_url.trim() },
      };
      setSources((prev) => mergeDataSourcePages([provisional], prev));
      setSelectedLabel(createForm.source_name.trim());
      onChange({ data_source_id: sourceId });

      void fetchDataSourceById(sourceId).then((item) => {
        if (!item) return;
        setSources((prev) => mergeDataSourcePages([item], prev));
        setSelectedLabel(item.source_name);
      });

      setCreateSuccess("새 Data Source를 등록하고 현재 노드에 선택했습니다.");
      setCreateOpen(false);
      setCreateForm(EMPTY_CREATE);
    } catch (err) {
      setCreateError(createDataSourceErrorMessage(err));
    } finally {
      setCreating(false);
    }
  };

  return (
    <div className="space-y-3" data-testid="visual-pipeline-inspector-config-form">
      <section className="rounded-lg border border-slate-100 p-2.5 space-y-2.5">
        <div className="text-[9px] font-bold text-slate-400 uppercase tracking-wide">연결</div>

        <VpConfigFieldShell
          fieldKey="data_source_id"
          label="Data Source"
          required
          help="REST Connector / Data Source 참조"
          warning={warn("data_source_id")}
        >
          <div className="space-y-2" data-testid="visual-pipeline-data-source-picker">
            <p className="text-[10px] text-slate-500" data-testid="visual-pipeline-data-source-list-hint">
              {DATA_SOURCE_LIST_HINT}
            </p>
            <p className="text-[10px] text-slate-500" data-testid="visual-pipeline-data-source-search-hint">
              {DATA_SOURCE_SEARCH_HINT}
            </p>
            <div className="flex flex-wrap gap-1.5">
              <input
                type="text"
                value={searchDraft}
                onChange={(e) => setSearchDraft(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") setSearchApplied(searchDraft);
                }}
                placeholder={DATA_SOURCE_SEARCH_PLACEHOLDER}
                disabled={disabled}
                className={`${INPUT_CLASS} flex-1 min-w-[120px]`}
                data-testid="visual-pipeline-data-source-search-input"
              />
              <button
                type="button"
                className={BTN_SECONDARY}
                disabled={disabled}
                data-testid="visual-pipeline-data-source-search-button"
                onClick={() => setSearchApplied(searchDraft)}
              >
                검색
              </button>
              <button
                type="button"
                className={BTN_GHOST}
                disabled={disabled}
                onClick={() => {
                  setSearchDraft("");
                  setSearchApplied("");
                }}
              >
                초기화
              </button>
              <button
                type="button"
                className={BTN_GHOST}
                disabled={disabled || sourcesLoading}
                data-testid="visual-pipeline-data-source-refresh-button"
                onClick={() => void loadSourcesPage(1, "replace")}
              >
                새로고침
              </button>
            </div>
            <p className="text-[10px] text-slate-400">
              {sourcesLoading
                ? "목록 로딩 중…"
                : `로드됨 ${restSources.length} / 전체 ${sourcesTotalCount || sources.length}건`}
              {searchApplied ? ` · 검색 ${filteredSources.length}건` : ""}
            </p>
            <select
              value={selectedId}
              onChange={handleSelectChange}
              disabled={disabled}
              className={INPUT_CLASS}
              data-testid="visual-pipeline-data-source-select"
            >
              <option value="">Data Source 선택</option>
              {selectOptions.map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </select>
            {selectedMissing && selectedId && (
              <p className="text-[10px] text-amber-700" data-testid="visual-pipeline-data-source-selected-missing">
                현재 선택값({selectedId})은 로드된 목록에 없습니다. 선택값은 유지됩니다.
              </p>
            )}
            {sourcesLoadError && restSources.length === 0 && (
              <p className="text-[10px] text-red-700">Data Source 목록을 불러오지 못했습니다.</p>
            )}
            {sourcesPage < sourcesTotalPages && (
              <button
                type="button"
                className={BTN_SECONDARY}
                disabled={disabled || sourcesLoadingMore}
                data-testid="visual-pipeline-data-source-load-more"
                onClick={() => void loadSourcesPage(sourcesPage + 1, "append")}
              >
                {sourcesLoadingMore ? "불러오는 중…" : "더 보기"}
              </button>
            )}

            <div className="pt-1 space-y-2">
              <button
                type="button"
                className={BTN_SECONDARY}
                disabled={disabled}
                data-testid="visual-pipeline-data-source-create-toggle"
                onClick={() => {
                  setCreateOpen((v) => !v);
                  setCreateError(null);
                }}
              >
                {createOpen ? "등록 취소" : "+ 새 Data Source 등록"}
              </button>
              {createOpen && (
                <div
                  className="rounded-md border border-slate-200 bg-slate-50 p-2.5 space-y-2"
                  data-testid="visual-pipeline-data-source-create-form"
                >
                  <p className="text-[10px] text-slate-600">
                    REST_API 유형만 등록합니다. source_type=REST_API (읽기 전용)
                  </p>
                  <p className="text-[10px] text-amber-800" data-testid="visual-pipeline-data-source-create-auth-hint">
                    {DATA_SOURCE_INLINE_CREATE_AUTH_HINT}
                  </p>
                  <label className="block text-[10px] text-slate-500">소스명 *</label>
                  <input
                    className={INPUT_CLASS}
                    value={createForm.source_name}
                    disabled={disabled || creating}
                    data-testid="visual-pipeline-data-source-create-name"
                    onChange={(e) => setCreateForm({ ...createForm, source_name: e.target.value })}
                    placeholder="B19 Studio REST Source"
                  />
                  <label className="block text-[10px] text-slate-500">Base URL *</label>
                  <input
                    className={INPUT_CLASS}
                    value={createForm.base_url}
                    disabled={disabled || creating}
                    data-testid="visual-pipeline-data-source-create-base-url"
                    onChange={(e) => setCreateForm({ ...createForm, base_url: e.target.value })}
                    placeholder="http://localhost:8000/api/v1"
                  />
                  <div className="grid grid-cols-2 gap-2">
                    <div>
                      <label className="block text-[10px] text-slate-500">Endpoint</label>
                      <input
                        className={INPUT_CLASS}
                        value={createForm.endpoint}
                        disabled={disabled || creating}
                        onChange={(e) => setCreateForm({ ...createForm, endpoint: e.target.value })}
                        placeholder="/sample-external/heat-demand"
                      />
                    </div>
                    <div>
                      <label className="block text-[10px] text-slate-500">Item Path</label>
                      <input
                        className={INPUT_CLASS}
                        value={createForm.item_path}
                        disabled={disabled || creating}
                        onChange={(e) => setCreateForm({ ...createForm, item_path: e.target.value })}
                        placeholder="data.items"
                      />
                    </div>
                  </div>
                  <label className="block text-[10px] text-slate-500">업무 영역 (data_domain)</label>
                  <select
                    className={INPUT_CLASS}
                    value={createForm.data_domain}
                    disabled={disabled || creating}
                    data-testid="visual-pipeline-data-source-create-domain"
                    onChange={(e) => setCreateForm({ ...createForm, data_domain: e.target.value })}
                  >
                    {DATA_SOURCE_DOMAIN_OPTIONS.map((o) => (
                      <option key={o.value} value={o.value}>
                        {o.label}
                      </option>
                    ))}
                  </select>
                  {createError && (
                    <p className="text-[10px] text-red-700" data-testid="visual-pipeline-data-source-create-error">
                      {createError}
                    </p>
                  )}
                  <button
                    type="button"
                    className={BTN_PRIMARY}
                    disabled={disabled || creating}
                    data-testid="visual-pipeline-data-source-create-submit"
                    onClick={() => void handleCreate()}
                  >
                    {creating ? "등록 중…" : "등록 후 선택"}
                  </button>
                </div>
              )}
              {createSuccess && (
                <p className="text-[10px] text-emerald-700" data-testid="visual-pipeline-data-source-create-success">
                  {createSuccess}
                </p>
              )}
            </div>

            <button
              type="button"
              className={BTN_GHOST}
              disabled={disabled}
              data-testid="visual-pipeline-data-source-advanced-toggle"
              onClick={() => setShowAdvancedId((v) => !v)}
            >
              {showAdvancedId ? "고급 ID 입력 숨기기" : "고급: ID 직접 입력"}
            </button>
            {showAdvancedId && (
              <input
                type="text"
                value={selectedId}
                onChange={patchText("data_source_id")}
                placeholder="DS-SAMPLE"
                disabled={disabled}
                className={INPUT_CLASS}
                data-testid="visual-pipeline-data-source-id-input"
              />
            )}
          </div>
        </VpConfigFieldShell>

        <VpConfigFieldShell
          fieldKey="operation_name"
          label="Operation Name"
          required
          warning={warn("operation_name")}
        >
          <input
            type="text"
            value={strVal(values, "operation_name")}
            onChange={patchText("operation_name")}
            placeholder="sample_fetch"
            disabled={disabled}
            className={INPUT_CLASS}
          />
        </VpConfigFieldShell>
        <VpConfigFieldShell
          fieldKey="credential_ref"
          label="Credential Ref"
          help={DATA_SOURCE_CREDENTIAL_REF_HELP}
          warning={warn("credential_ref")}
        >
          <input
            type="text"
            value={strVal(values, "credential_ref")}
            onChange={patchText("credential_ref")}
            placeholder="CRED-SAMPLE"
            disabled={disabled}
            className={INPUT_CLASS}
            autoComplete="off"
            data-testid="visual-pipeline-credential-ref-input"
          />
        </VpConfigFieldShell>
      </section>

      <section className="rounded-lg border border-slate-100 p-2.5 space-y-2.5">
        <div className="text-[9px] font-bold text-slate-400 uppercase tracking-wide">Request</div>
        <VpConfigFieldShell
          fieldKey="endpoint_path"
          label="Endpoint Path"
          required
          warning={warn("endpoint_path")}
        >
          <input
            type="text"
            value={strVal(values, "endpoint_path")}
            onChange={patchText("endpoint_path")}
            placeholder="/api/v1/sample"
            disabled={disabled}
            className={INPUT_CLASS}
          />
        </VpConfigFieldShell>
        <VpConfigFieldShell
          fieldKey="http_method"
          label="HTTP Method"
          required
          warning={warn("http_method")}
        >
          <select
            value={strVal(values, "http_method")}
            onChange={patchText("http_method")}
            disabled={disabled}
            className={INPUT_CLASS}
          >
            {!strVal(values, "http_method") && <option value="">선택하세요</option>}
            <option value="GET">GET</option>
            <option value="POST">POST</option>
          </select>
        </VpConfigFieldShell>
        <VpJsonTextareaField
          fieldKey="request_params"
          label="Request Params"
          value={values.request_params}
          placeholder={'{ "branch": "P001" }'}
          advanced
          disabled={disabled}
          warning={warn("request_params")}
          onChange={onChange}
        />
        <VpJsonTextareaField
          fieldKey="pagination"
          label="Pagination"
          value={values.pagination}
          placeholder={'{\n  "type": "NONE"\n}'}
          advanced
          disabled={disabled}
          warning={warn("pagination")}
          onChange={onChange}
        />
      </section>

      <section className="rounded-lg border border-slate-100 p-2.5 space-y-2.5">
        <div className="text-[9px] font-bold text-slate-400 uppercase tracking-wide">Response</div>
        <VpConfigFieldShell
          fieldKey="response_item_path"
          label="Response Item Path"
          help="JSON 응답에서 row array 위치 (JSONPath)"
          warning={warn("response_item_path")}
        >
          <input
            type="text"
            value={strVal(values, "response_item_path")}
            onChange={patchText("response_item_path")}
            placeholder="$.items"
            disabled={disabled}
            className={INPUT_CLASS}
          />
        </VpConfigFieldShell>
      </section>

      <div className="space-y-1 text-[9px] text-slate-500 leading-relaxed px-0.5">
        <p>설정 변경사항은 Graph 저장 시 함께 저장됩니다.</p>
        <p className="text-amber-700">비밀값은 저장하지 않고 Credential 참조만 저장하세요.</p>
      </div>
    </div>
  );
}
