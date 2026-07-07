import { useCallback, useEffect, useMemo, useState } from "react";
import { ChevronLeft, ChevronRight, Loader2, Plus, Trash2 } from "lucide-react";
import {
  apiConnectorErrorMessage,
  createApiConnectorOperation,
  getApiConnectorCredential,
  getApiConnectorOperation,
  replaceApiConnectorParams,
  testApiConnectorCall,
  requestApiConnectorPreview,
  loadApiConnectorPreview,
  runApiConnectorLoad,
  transformApiConnectorPreview,
  updateApiConnectorOperation,
  upsertApiConnectorCredential,
  upsertApiConnectorPagination,
  upsertApiConnectorTransformConfig,
} from "@/api/apiConnectors";
import { getStandardTargetTables, validateTargetTable } from "@/api/standardDatasets";
import { Button } from "@/components/Button";
import { Modal } from "@/components/Modal";
import { SelectInput, TextInput } from "@/components/SearchPanel";
import { useToast } from "@/hooks/useToast";
import type {
  ApiConnectorPagination,
  ApiConnectorParam,
  ApiConnectorTestCallResult,
  ApiConnectorTransformConfig,
} from "@/types/apiConnector";
import { PARAM_QUICK_ADD, WIZARD_STEP_TITLES as STEP_TITLES } from "@/types/apiConnector";
import type { StandardTargetTable } from "@/types/standardDatasets";
import {
  computeColumnMatching,
  normalizePreviewItems,
  safeJsonStringify,
} from "@/utils/apiConnectorDisplay";
import { EMPTY_MESSAGES, HELP_TEXTS } from "@/constants/displayLabels";

interface DataSourceOption {
  source_id: string;
  source_name: string;
  source_type: string;
  connection_info?: Record<string, string>;
}

interface WizardProps {
  open: boolean;
  onClose: () => void;
  onCompleted: () => void;
  sources: DataSourceOption[];
  editOperationId?: string | null;
}

const EMPTY_PARAM = (): ApiConnectorParam => ({
  param_name: "",
  display_name: "",
  param_location: "QUERY",
  param_type: "STRING",
  required_yn: false,
  default_value: "",
  example_value: "",
  value_source: "USER_INPUT",
  encode_yn: true,
  sort_order: 0,
});

const DEFAULT_PAGINATION: ApiConnectorPagination = {
  pagination_type: "NONE",
  page_param_name: "pageNo",
  size_param_name: "numOfRows",
  page_start: 1,
  page_size: 100,
  max_pages: 1,
  stop_condition: "EMPTY_ITEMS",
};

const DEFAULT_TRANSFORM: ApiConnectorTransformConfig = {
  transform_type: "NONE",
  source_system: "HEAT_DEMAND_API",
  external_code_group: "NODE",
  external_code_field: "ND_ID",
  external_name_field: "ND_KORN_NM",
  date_field: "BAS_YMD",
  date_format: "YYYYMMDD",
  hour_column_prefix: "HTDND_AMNT_",
  hour_column_suffix: "HR",
  hour_start: 1,
  hour_end: 24,
  value_output_field: "heat_demand",
  measured_at_output_field: "measured_at",
  entity_id_output_field: "entity_id",
  entity_code_output_field: "site_id",
  external_code_output_field: "external_node_id",
  external_name_output_field: "external_node_name",
  timestamp_policy: "HOUR_LABEL_AS_END",
  hour_24_policy: "NEXT_DAY_00",
  unmapped_policy: "FAIL_LOAD",
  null_value_policy: "SKIP_NULL",
  numeric_parse_policy: "ALLOW_COMMA",
  active_yn: true,
  station_code_field: "stnId",
  observed_at_field: "tm",
  special_day_name_field: "dateName",
  default_special_day_type: "PUBLIC_HOLIDAY",
  public_holiday_field: "isHoliday",
  calendar_mode: "FULL_CALENDAR_WITH_OVERLAY",
  hour_generation_yn: false,
  station_unmapped_policy: "WARN_ONLY",
  store_raw_json: true,
};

export function ApiConnectorOperationWizard({
  open,
  onClose,
  onCompleted,
  sources,
  editOperationId,
}: WizardProps) {
  const { showToast } = useToast();
  const [step, setStep] = useState(0);
  const [busy, setBusy] = useState(false);
  const [operationId, setOperationId] = useState<string | null>(null);
  const [targetTables, setTargetTables] = useState<StandardTargetTable[]>([]);
  const [credentialMasked, setCredentialMasked] = useState<string | null>(null);

  const [basic, setBasic] = useState({
    data_source_id: "",
    operation_name: "",
    operation_description: "",
    http_method: "GET",
    endpoint_path: "",
    request_content_type: "QUERY",
    response_format: "JSON",
  });
  const [credential, setCredential] = useState({
    credential_type: "API_KEY",
    key_location: "QUERY",
    key_name: "serviceKey",
    secret_value: "",
    encoding_policy: "STORE_DECODED_ENCODE_ON_CALL",
  });
  const [params, setParams] = useState<ApiConnectorParam[]>([]);
  const [pagination, setPagination] = useState<ApiConnectorPagination>({ ...DEFAULT_PAGINATION });
  const [responsePath, setResponsePath] = useState({
    response_item_path: "data.items",
    result_array_mode: "AUTO",
    sampleJson: "",
  });
  const [target, setTarget] = useState({ standard_dataset_id: "", target_table: "" });
  const [transform, setTransform] = useState<ApiConnectorTransformConfig>({ ...DEFAULT_TRANSFORM });
  const [targetValidation, setTargetValidation] = useState<string | null>(null);

  const [requestPreview, setRequestPreview] = useState<Record<string, unknown> | null>(null);
  const [testResult, setTestResult] = useState<ApiConnectorTestCallResult | null>(null);
  const [loadPreviewResult, setLoadPreviewResult] = useState<Record<string, unknown> | null>(null);
  const [transformPreviewResult, setTransformPreviewResult] = useState<Record<string, unknown> | null>(null);
  const [loadRunResult, setLoadRunResult] = useState<Record<string, unknown> | null>(null);

  const restSources = useMemo(
    () => sources.filter((s) => ["REST_API", "API"].includes(s.source_type)),
    [sources],
  );

  const selectedSource = restSources.find((s) => s.source_id === basic.data_source_id);
  const baseUrl = selectedSource?.connection_info?.base_url || "(데이터 소스 base_url)";

  const reset = useCallback(() => {
    setStep(0);
    setOperationId(editOperationId || null);
    setBasic({
      data_source_id: restSources[0]?.source_id || "",
      operation_name: "",
      operation_description: "",
      http_method: "GET",
      endpoint_path: "",
      request_content_type: "QUERY",
      response_format: "JSON",
    });
    setCredential({
      credential_type: "API_KEY",
      key_location: "QUERY",
      key_name: "serviceKey",
      secret_value: "",
      encoding_policy: "STORE_DECODED_ENCODE_ON_CALL",
    });
    setParams([]);
    setPagination({ ...DEFAULT_PAGINATION });
    setResponsePath({ response_item_path: "data.items", result_array_mode: "AUTO", sampleJson: "" });
    setTarget({ standard_dataset_id: "", target_table: "" });
    setTransform({ ...DEFAULT_TRANSFORM });
    setCredentialMasked(null);
    setRequestPreview(null);
    setTestResult(null);
    setLoadPreviewResult(null);
    setTransformPreviewResult(null);
    setLoadRunResult(null);
    setTargetValidation(null);
  }, [editOperationId, restSources]);

  useEffect(() => {
    if (!open) return;
    reset();
    void getStandardTargetTables({ mapping_supported: true, active_only: true })
      .then((res) => setTargetTables(res.items || []))
      .catch(() => setTargetTables([]));
  }, [open, reset]);

  useEffect(() => {
    if (!open || !editOperationId) return;
    void (async () => {
      try {
        const detail = await getApiConnectorOperation(editOperationId);
        setOperationId(detail.operation_id);
        setBasic({
          data_source_id: detail.data_source_id,
          operation_name: detail.operation_name,
          operation_description: detail.operation_description || "",
          http_method: detail.http_method || "GET",
          endpoint_path: detail.endpoint_path,
          request_content_type: detail.request_content_type || "QUERY",
          response_format: detail.response_format || "JSON",
        });
        setParams(detail.params || []);
        if (detail.pagination) setPagination(detail.pagination);
        setResponsePath((r) => ({
          ...r,
          response_item_path: detail.response_item_path || "data.items",
          result_array_mode: detail.result_array_mode || "AUTO",
        }));
        setTarget({
          standard_dataset_id: detail.standard_dataset_id || "",
          target_table: detail.target_table || "",
        });
        if (detail.transform_config) {
          setTransform({ ...DEFAULT_TRANSFORM, ...detail.transform_config });
        }
        const cred = await getApiConnectorCredential(detail.data_source_id);
        if (cred) {
          setCredentialMasked(cred.secret_value_masked || null);
          setCredential((c) => ({
            ...c,
            credential_type: cred.credential_type,
            key_location: cred.key_location,
            key_name: cred.key_name,
            encoding_policy: cred.encoding_policy,
            secret_value: "",
          }));
        }
      } catch {
        showToast("error", "API 작업 정보를 불러오지 못했습니다.");
      }
    })();
  }, [open, editOperationId, showToast]);

  const localPreviewItems = useMemo(() => {
    if (!responsePath.sampleJson.trim()) return [];
    try {
      const parsed = JSON.parse(responsePath.sampleJson);
      return normalizePreviewItems(parsed, responsePath.response_item_path);
    } catch {
      return [];
    }
  }, [responsePath.sampleJson, responsePath.response_item_path]);

  const selectedTargetMeta = targetTables.find((t) => t.target_table === target.target_table);

  const columnMatching = useMemo(() => {
    const sampleFields =
      testResult?.sample_items?.[0]
        ? Object.keys(testResult.sample_items[0])
        : localPreviewItems[0]
          ? Object.keys(localPreviewItems[0])
          : [];
    const targetCols = selectedTargetMeta?.standard_columns || [];
    return computeColumnMatching(sampleFields, targetCols);
  }, [testResult, localPreviewItems, selectedTargetMeta]);

  const validateStep = (idx: number): string | null => {
    if (idx === 0) {
      if (!basic.data_source_id) return "데이터 소스를 선택하세요.";
      if (!basic.operation_name.trim()) return "API 작업명을 입력하세요.";
      if (!basic.endpoint_path.trim()) return "endpoint 경로를 입력하세요.";
    }
    if (idx === 2) {
      const names = params.map((p) => p.param_name.trim()).filter(Boolean);
      if (new Set(names).size !== names.length) return "요청 파라미터 이름이 중복됩니다.";
      for (const p of params) {
        if (!p.param_name.trim()) return "빈 파라미터 이름이 있습니다.";
        if (p.required_yn && !p.default_value && !p.example_value && p.value_source !== "SECRET_REF") {
          return `필수 파라미터 '${p.param_name}'에 기본값 또는 예시값을 입력하세요.`;
        }
      }
    }
    if (idx === 4 && basic.response_format !== "TEXT" && !responsePath.response_item_path.trim()) {
      return "응답 데이터 경로를 입력하세요.";
    }
    return null;
  };

  const persistOperation = async (): Promise<string> => {
    if (credential.secret_value.trim()) {
      const credRes = await upsertApiConnectorCredential(basic.data_source_id, {
        credential_type: credential.credential_type,
        key_location: credential.key_location,
        key_name: credential.key_name,
        secret_value: credential.secret_value,
        encoding_policy: credential.encoding_policy,
      });
      setCredentialMasked(credRes.secret_value_masked || "****");
      setCredential((c) => ({ ...c, secret_value: "" }));
    }

    const body = {
      ...basic,
      response_item_path: responsePath.response_item_path || undefined,
      result_array_mode: responsePath.result_array_mode,
      target_table: target.target_table || undefined,
      standard_dataset_id: target.standard_dataset_id || undefined,
    };

    let opId = operationId;
    if (opId) {
      await updateApiConnectorOperation(opId, body);
    } else {
      const created = await createApiConnectorOperation(body);
      opId = created.operation_id;
      setOperationId(opId);
    }

    await replaceApiConnectorParams(
      opId,
      params.map((p, i) => ({ ...p, sort_order: i, active_yn: true })),
    );
    await upsertApiConnectorPagination(opId, pagination);
    await upsertApiConnectorTransformConfig(opId, transform);
    return opId;
  };

  const handleNext = async () => {
    const err = validateStep(step);
    if (err) {
      showToast("warning", err);
      return;
    }
    if (step === 6) {
      setBusy(true);
      try {
        if (target.target_table) {
          const v = await validateTargetTable(target.target_table);
          if (!v.valid) {
            setTargetValidation(v.warnings?.[0] || "적재 대상 테이블을 사용할 수 없습니다.");
            setBusy(false);
            return;
          }
          setTargetValidation(null);
        }
        await persistOperation();
        setStep(7);
      } catch (e) {
        showToast("error", apiConnectorErrorMessage(e, "저장에 실패했습니다."));
      } finally {
        setBusy(false);
      }
      return;
    }
    setStep((s) => Math.min(s + 1, STEP_TITLES.length - 1));
  };

  const handleBack = () => setStep((s) => Math.max(s - 1, 0));

  const handleFinalSave = async () => {
    setBusy(true);
    try {
      await persistOperation();
      showToast("success", "API 작업이 저장되었습니다.");
      onCompleted();
      onClose();
    } catch (e) {
      showToast("error", apiConnectorErrorMessage(e, "저장에 실패했습니다."));
    } finally {
      setBusy(false);
    }
  };

  const handleRequestPreview = async () => {
    if (!operationId) return;
    setBusy(true);
    try {
      const res = await requestApiConnectorPreview(operationId);
      setRequestPreview(res as unknown as Record<string, unknown>);
    } catch (e) {
      showToast("error", apiConnectorErrorMessage(e, "요청 미리보기에 실패했습니다."));
    } finally {
      setBusy(false);
    }
  };

  const handleTestCall = async () => {
    if (!operationId) return;
    setBusy(true);
    try {
      const res = await testApiConnectorCall(operationId);
      setTestResult(res);
      showToast(res.success ? "success" : "warning", res.message || `테스트 호출 완료 (${res.item_count}건)`);
    } catch (e) {
      showToast("error", apiConnectorErrorMessage(e, "테스트 호출에 실패했습니다. endpoint·파라미터·인증 정보를 확인하세요."));
    } finally {
      setBusy(false);
    }
  };

  const handleTransformPreview = async () => {
    if (!operationId) return;
    setBusy(true);
    try {
      const rawItems = localPreviewItems.length > 0 ? localPreviewItems : testResult?.sample_items;
      const res = await transformApiConnectorPreview(
        operationId,
        rawItems && rawItems.length > 0 ? { raw_items: rawItems as Record<string, unknown>[] } : {},
      );
      setTransformPreviewResult(res as unknown as Record<string, unknown>);
    } catch (e) {
      showToast("error", apiConnectorErrorMessage(e, "변환 미리보기에 실패했습니다."));
    } finally {
      setBusy(false);
    }
  };

  const handleLoadPreview = async () => {
    if (!operationId || !target.target_table) return;
    setBusy(true);
    try {
      const res = await loadApiConnectorPreview(operationId);
      setLoadPreviewResult(res as unknown as Record<string, unknown>);
    } catch (e) {
      showToast("error", apiConnectorErrorMessage(e, "적재 미리보기에 실패했습니다."));
    } finally {
      setBusy(false);
    }
  };

  const handleLoadRun = async () => {
    if (!operationId || !target.target_table) return;
    if (!window.confirm(
      "현재 API 응답 데이터를 적재 대상 테이블에 INSERT합니다. 중복 처리와 upsert는 후속 단계에서 고도화됩니다.",
    )) return;
    setBusy(true);
    try {
      const res = await runApiConnectorLoad(operationId);
      setLoadRunResult(res as unknown as Record<string, unknown>);
      showToast("success", `적재 실행 완료 (${res.inserted_count}건 적재)`);
      onCompleted();
    } catch (e) {
      showToast("error", apiConnectorErrorMessage(e, "적재 실행에 실패했습니다."));
    } finally {
      setBusy(false);
    }
  };

  const addParam = (preset?: (typeof PARAM_QUICK_ADD)[0]) => {
    const row = EMPTY_PARAM();
    if (preset) {
      row.param_name = preset.param_name;
      row.display_name = preset.display_name;
      row.param_type = preset.param_type;
      row.value_source = preset.value_source || "USER_INPUT";
      if (preset.param_type === "SECRET") row.value_source = "SECRET_REF";
    }
    setParams((p) => [...p, { ...row, sort_order: p.length }]);
  };

  const renderStep = () => {
    switch (step) {
      case 0:
        return (
          <div className="space-y-3 text-sm">
            <SelectInput
              value={basic.data_source_id}
              onChange={(v) => setBasic({ ...basic, data_source_id: v })}
              options={[
                { value: "", label: "REST API 데이터 소스 선택" },
                ...restSources.map((s) => ({ value: s.source_id, label: s.source_name })),
              ]}
            />
            {restSources.length === 0 && (
              <p className="text-amber-700 text-xs bg-amber-50 p-2 rounded">{EMPTY_MESSAGES.dataSources}</p>
            )}
            <label className="block text-xs text-slate-500">API 작업명</label>
            <TextInput value={basic.operation_name} onChange={(v) => setBasic({ ...basic, operation_name: v })} />
            <label className="block text-xs text-slate-500">설명</label>
            <TextInput value={basic.operation_description} onChange={(v) => setBasic({ ...basic, operation_description: v })} />
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs text-slate-500 mb-1">HTTP Method</label>
                <SelectInput value={basic.http_method} onChange={(v) => setBasic({ ...basic, http_method: v })} options={[{ value: "GET", label: "GET" }, { value: "POST", label: "POST" }]} />
              </div>
              <div>
                <label className="block text-xs text-slate-500 mb-1">Response Format</label>
                <SelectInput value={basic.response_format} onChange={(v) => setBasic({ ...basic, response_format: v })} options={[{ value: "JSON", label: "JSON" }, { value: "XML", label: "XML" }, { value: "TEXT", label: "TEXT" }]} />
              </div>
            </div>
            <p className="text-xs text-slate-500">Base URL: <span className="font-mono">{baseUrl}</span></p>
            <label className="block text-xs text-slate-500">Endpoint Path</label>
            <TextInput value={basic.endpoint_path} onChange={(v) => setBasic({ ...basic, endpoint_path: v })} placeholder="/sample-external/heat-demand" />
            <label className="block text-xs text-slate-500">Request Content Type</label>
            <SelectInput value={basic.request_content_type} onChange={(v) => setBasic({ ...basic, request_content_type: v })} options={[{ value: "QUERY", label: "QUERY" }, { value: "JSON_BODY", label: "JSON_BODY" }, { value: "FORM", label: "FORM" }]} />
          </div>
        );
      case 1:
        return (
          <div className="space-y-3 text-sm">
            <div className="bg-amber-50 border border-amber-100 rounded p-3 text-xs text-amber-900">{HELP_TEXTS.serviceKeyEncoding}</div>
            <p className="text-xs text-slate-500">{HELP_TEXTS.secretMasking}</p>
            {credentialMasked && (
              <p className="text-xs text-green-700">저장된 인증 키: <strong>{credentialMasked}</strong></p>
            )}
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs text-slate-500 mb-1">인증 유형</label>
                <SelectInput value={credential.credential_type} onChange={(v) => setCredential({ ...credential, credential_type: v })} options={[
                  { value: "NONE", label: "NONE" }, { value: "API_KEY", label: "API_KEY" },
                  { value: "BEARER_TOKEN", label: "BEARER_TOKEN" }, { value: "BASIC_AUTH", label: "BASIC_AUTH" },
                ]} />
              </div>
              <div>
                <label className="block text-xs text-slate-500 mb-1">키 위치</label>
                <SelectInput value={credential.key_location} onChange={(v) => setCredential({ ...credential, key_location: v })} options={[{ value: "QUERY", label: "QUERY" }, { value: "HEADER", label: "HEADER" }]} />
              </div>
            </div>
            <label className="block text-xs text-slate-500">키 이름</label>
            <TextInput value={credential.key_name} onChange={(v) => setCredential({ ...credential, key_name: v })} />
            <label className="block text-xs text-slate-500">Secret (새로 입력 시에만 저장)</label>
            <input type="password" value={credential.secret_value} onChange={(e) => setCredential({ ...credential, secret_value: e.target.value })} className="w-full border border-slate-200 rounded-md px-2 py-1.5 text-sm" autoComplete="off" />
            <label className="block text-xs text-slate-500">Encoding Policy</label>
            <SelectInput value={credential.encoding_policy} onChange={(v) => setCredential({ ...credential, encoding_policy: v })} options={[
              { value: "STORE_DECODED_ENCODE_ON_CALL", label: "Decoding 키 권장 (호출 시 1회 인코딩)" },
              { value: "STORE_AS_IS", label: "Encoding 키 그대로 저장 (이중 인코딩 위험)" },
            ]} />
          </div>
        );
      case 2:
        return (
          <div className="space-y-3 text-sm">
            <div className="flex flex-wrap gap-2">
              <Button variant="secondary" icon={<Plus className="w-3 h-3" />} onClick={() => addParam()}>파라미터 추가</Button>
              {PARAM_QUICK_ADD.map((p) => (
                <Button key={p.param_name} variant="ghost" onClick={() => addParam(p)}>+ {p.param_name}</Button>
              ))}
            </div>
            {params.length === 0 ? (
              <p className="text-slate-500 text-xs py-4 text-center border border-dashed rounded">요청 파라미터가 없습니다. 필요 시 추가하세요.</p>
            ) : (
              <div className="space-y-2 max-h-80 overflow-y-auto">
                {params.map((p, idx) => (
                  <div key={idx} className="border rounded p-2 grid grid-cols-12 gap-2 items-start">
                    <div className="col-span-3">
                      <label className="text-xs text-slate-400">이름</label>
                      <TextInput value={p.param_name} onChange={(v) => { const n = [...params]; n[idx] = { ...p, param_name: v }; setParams(n); }} />
                    </div>
                    <div className="col-span-3">
                      <label className="text-xs text-slate-400">표시명</label>
                      <TextInput value={p.display_name || ""} onChange={(v) => { const n = [...params]; n[idx] = { ...p, display_name: v }; setParams(n); }} />
                    </div>
                    <div className="col-span-2">
                      <label className="text-xs text-slate-400">위치</label>
                      <SelectInput value={p.param_location} onChange={(v) => { const n = [...params]; n[idx] = { ...p, param_location: v }; setParams(n); }} options={[{ value: "QUERY", label: "QUERY" }, { value: "HEADER", label: "HEADER" }, { value: "BODY", label: "BODY" }]} />
                    </div>
                    <div className="col-span-2">
                      <label className="text-xs text-slate-400">타입</label>
                      <SelectInput value={p.param_type} onChange={(v) => { const n = [...params]; n[idx] = { ...p, param_type: v, value_source: v === "SECRET" ? "SECRET_REF" : p.value_source }; setParams(n); }} options={["STRING", "NUMBER", "INTEGER", "BOOLEAN", "DATE", "DATETIME", "SECRET"].map((t) => ({ value: t, label: t }))} />
                    </div>
                    <div className="col-span-2 flex gap-2 pt-5">
                      <label className="text-xs flex items-center gap-1"><input type="checkbox" checked={p.required_yn} onChange={(e) => { const n = [...params]; n[idx] = { ...p, required_yn: e.target.checked }; setParams(n); }} />필수</label>
                      <button type="button" className="text-red-500" onClick={() => setParams(params.filter((_, i) => i !== idx))}><Trash2 className="w-4 h-4" /></button>
                    </div>
                    <div className="col-span-4">
                      <label className="text-xs text-slate-400">기본값</label>
                      <TextInput value={p.default_value || ""} onChange={(v) => { const n = [...params]; n[idx] = { ...p, default_value: v }; setParams(n); }} />
                    </div>
                    <div className="col-span-3">
                      <label className="text-xs text-slate-400">value_source</label>
                      <SelectInput value={p.value_source} onChange={(v) => { const n = [...params]; n[idx] = { ...p, value_source: v }; setParams(n); }} options={["USER_INPUT", "DEFAULT", "SECRET_REF", "SYSTEM_DATE", "RUNTIME"].map((t) => ({ value: t, label: t }))} />
                    </div>
                    <div className="col-span-2 pt-5">
                      <label className="text-xs flex items-center gap-1"><input type="checkbox" checked={p.encode_yn} onChange={(e) => { const n = [...params]; n[idx] = { ...p, encode_yn: e.target.checked }; setParams(n); }} />URL encode</label>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        );
      case 3:
        return (
          <div className="space-y-3 text-sm">
            <p className="text-xs text-slate-500">과도한 호출 방지를 위해 max_pages는 제한됩니다. OFFSET_LIMIT/NEXT_LINK는 후속 단계에서 지원 예정입니다.</p>
            <label className="block text-xs text-slate-500">페이징 방식</label>
            <SelectInput value={pagination.pagination_type} onChange={(v) => setPagination({ ...pagination, pagination_type: v })} options={[
              { value: "NONE", label: "NONE" },
              { value: "PAGE_NO", label: "PAGE_NO" },
              { value: "OFFSET_LIMIT", label: "OFFSET_LIMIT (후속 지원)" },
              { value: "NEXT_LINK", label: "NEXT_LINK (후속 지원)" },
            ]} />
            {pagination.pagination_type === "PAGE_NO" && (
              <div className="grid grid-cols-2 gap-3">
                <div><label className="text-xs text-slate-500">page_param_name</label><TextInput value={pagination.page_param_name || ""} onChange={(v) => setPagination({ ...pagination, page_param_name: v })} /></div>
                <div><label className="text-xs text-slate-500">size_param_name</label><TextInput value={pagination.size_param_name || ""} onChange={(v) => setPagination({ ...pagination, page_size: pagination.page_size, size_param_name: v })} /></div>
                <div><label className="text-xs text-slate-500">page_start</label><TextInput value={String(pagination.page_start ?? 1)} onChange={(v) => setPagination({ ...pagination, page_start: Number(v) || 1 })} /></div>
                <div><label className="text-xs text-slate-500">page_size</label><TextInput value={String(pagination.page_size ?? 100)} onChange={(v) => setPagination({ ...pagination, page_size: Number(v) || 100 })} /></div>
                <div><label className="text-xs text-slate-500">max_pages</label><TextInput value={String(pagination.max_pages ?? 1)} onChange={(v) => setPagination({ ...pagination, max_pages: Math.min(Number(v) || 1, 5) })} /></div>
                <div><label className="text-xs text-slate-500">stop_condition</label><SelectInput value={pagination.stop_condition || "EMPTY_ITEMS"} onChange={(v) => setPagination({ ...pagination, stop_condition: v })} options={[{ value: "EMPTY_ITEMS", label: "EMPTY_ITEMS" }, { value: "PAGE_REACH_MAX", label: "PAGE_REACH_MAX" }]} /></div>
              </div>
            )}
            {(pagination.pagination_type === "OFFSET_LIMIT" || pagination.pagination_type === "NEXT_LINK") && (
              <p className="text-amber-700 text-xs">현재 Backend는 PAGE_NO 페이징만 지원합니다. NONE 또는 PAGE_NO를 사용하세요.</p>
            )}
          </div>
        );
      case 4:
        return (
          <div className="space-y-3 text-sm">
            <p className="text-xs text-slate-500">{HELP_TEXTS.responseItemPath}</p>
            <label className="block text-xs text-slate-500">응답 데이터 경로 (dot path)</label>
            <TextInput value={responsePath.response_item_path} onChange={(v) => setResponsePath({ ...responsePath, response_item_path: v })} placeholder="data.items" />
            <label className="block text-xs text-slate-500">result_array_mode</label>
            <SelectInput value={responsePath.result_array_mode} onChange={(v) => setResponsePath({ ...responsePath, result_array_mode: v })} options={[{ value: "AUTO", label: "AUTO" }, { value: "ARRAY", label: "ARRAY" }, { value: "SINGLE_OBJECT", label: "SINGLE_OBJECT" }]} />
            {basic.response_format === "TEXT" && (
              <p className="text-amber-700 text-xs">TEXT 형식은 preview만 지원하며 row 추출은 제한됩니다.</p>
            )}
            <label className="block text-xs text-slate-500">샘플 JSON (붙여넣기로 경로 검증)</label>
            <textarea value={responsePath.sampleJson} onChange={(e) => setResponsePath({ ...responsePath, sampleJson: e.target.value })} className="w-full border rounded p-2 font-mono text-xs h-32" placeholder='{"data":{"items":[...]}}' />
            {responsePath.sampleJson && (
              <div>
                <p className="text-xs font-medium mb-1">추출 미리보기: {localPreviewItems.length}건</p>
                {localPreviewItems.length === 0 ? (
                  <p className="text-amber-700 text-xs">경로가 올바르지 않거나 항목이 없습니다.</p>
                ) : (
                  <pre className="text-xs bg-slate-50 p-2 rounded max-h-40 overflow-auto">{safeJsonStringify(localPreviewItems.slice(0, 3))}</pre>
                )}
              </div>
            )}
          </div>
        );
      case 5:
        return (
          <div className="space-y-3 text-sm">
            <h3 className="font-medium text-slate-800">변환 설정</h3>
            <p className="text-xs text-slate-500">{HELP_TEXTS.connectorCleanSeedHint}</p>
            <label className="block text-xs text-slate-500">변환 유형</label>
            <SelectInput
              value={transform.transform_type}
              onChange={(v) => {
                const defaults: Partial<ApiConnectorTransformConfig> =
                  v === "ASOS_HOURLY_TO_CANONICAL"
                    ? { source_system: "KMA_ASOS_API", station_unmapped_policy: "WARN_ONLY" }
                    : v === "CALENDAR_SPECIAL_DAY_TO_DATE" || v === "CALENDAR_DATE_TO_HOUR"
                      ? {
                          source_system: "KASI_SPECIAL_DAY_API",
                          date_field: "locdate",
                          date_format: "YYYYMMDD",
                          calendar_mode: "FULL_CALENDAR_WITH_OVERLAY",
                        }
                      : v === "WIDE_HOUR_TO_LONG"
                        ? { source_system: "HEAT_DEMAND_API" }
                        : {};
                setTransform({ ...transform, transform_type: v, ...defaults });
              }}
              options={[
                { value: "NONE", label: "변환 없음" },
                { value: "WIDE_HOUR_TO_LONG", label: "열수요 wide-hour 변환" },
                { value: "ASOS_HOURLY_TO_CANONICAL", label: "ASOS 관측 기상 변환" },
                { value: "CALENDAR_SPECIAL_DAY_TO_DATE", label: "Calendar/특일 날짜 변환" },
                { value: "CALENDAR_DATE_TO_HOUR", label: "Calendar 시간 행 생성" },
              ]}
            />
            {transform.transform_type === "WIDE_HOUR_TO_LONG" && (
              <>
                <p className="text-xs text-slate-500">{HELP_TEXTS.wideHourTransform}</p>
                <p className="text-xs text-amber-800 bg-amber-50 p-2 rounded">{HELP_TEXTS.wideHourTimestampPolicy}</p>
                <p className="text-xs text-slate-600">{HELP_TEXTS.wideHourUnmapped}</p>
                <div className="grid grid-cols-2 gap-3">
                  <div><label className="text-xs text-slate-500">외부 지점 코드 필드</label><TextInput value={transform.external_code_field || "ND_ID"} onChange={(v) => setTransform({ ...transform, external_code_field: v })} /></div>
                  <div><label className="text-xs text-slate-500">외부 지점명 필드</label><TextInput value={transform.external_name_field || "ND_KORN_NM"} onChange={(v) => setTransform({ ...transform, external_name_field: v })} /></div>
                  <div><label className="text-xs text-slate-500">날짜 필드</label><TextInput value={transform.date_field || "BAS_YMD"} onChange={(v) => setTransform({ ...transform, date_field: v })} /></div>
                  <div><label className="text-xs text-slate-500">날짜 형식</label><TextInput value={transform.date_format || "YYYYMMDD"} onChange={(v) => setTransform({ ...transform, date_format: v })} /></div>
                  <div><label className="text-xs text-slate-500">시간 컬럼 prefix</label><TextInput value={transform.hour_column_prefix || "HTDND_AMNT_"} onChange={(v) => setTransform({ ...transform, hour_column_prefix: v })} /></div>
                  <div><label className="text-xs text-slate-500">시간 컬럼 suffix</label><TextInput value={transform.hour_column_suffix || "HR"} onChange={(v) => setTransform({ ...transform, hour_column_suffix: v })} /></div>
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="text-xs text-slate-500">시간 해석 방식</label>
                    <SelectInput value={transform.timestamp_policy || "HOUR_LABEL_AS_END"} onChange={(v) => setTransform({ ...transform, timestamp_policy: v })} options={[
                      { value: "HOUR_LABEL_AS_END", label: "HOUR_LABEL_AS_END (1HR→01:00)" },
                      { value: "HOUR_LABEL_AS_START", label: "HOUR_LABEL_AS_START (1HR→00:00)" },
                    ]} />
                  </div>
                  <div>
                    <label className="text-xs text-slate-500">24시간 처리</label>
                    <SelectInput value={transform.hour_24_policy || "NEXT_DAY_00"} onChange={(v) => setTransform({ ...transform, hour_24_policy: v })} options={[
                      { value: "NEXT_DAY_00", label: "NEXT_DAY_00 (다음날 00:00)" },
                      { value: "SAME_DAY_23", label: "SAME_DAY_23 (당일 23:00)" },
                    ]} />
                  </div>
                  <div>
                    <label className="text-xs text-slate-500">미매핑 처리 방식</label>
                    <SelectInput value={transform.unmapped_policy || "FAIL_LOAD"} onChange={(v) => setTransform({ ...transform, unmapped_policy: v })} options={[
                      { value: "FAIL_LOAD", label: "FAIL_LOAD (적재 중단)" },
                      { value: "SKIP_UNMAPPED", label: "SKIP_UNMAPPED (해당 item skip)" },
                      { value: "LOG_ONLY", label: "LOG_ONLY (entity 없이 변환)" },
                    ]} />
                  </div>
                  <div>
                    <label className="text-xs text-slate-500">NULL 값 처리</label>
                    <SelectInput value={transform.null_value_policy || "SKIP_NULL"} onChange={(v) => setTransform({ ...transform, null_value_policy: v })} options={[
                      { value: "SKIP_NULL", label: "SKIP_NULL" },
                      { value: "INSERT_NULL", label: "INSERT_NULL" },
                      { value: "FAIL_ON_NULL", label: "FAIL_ON_NULL" },
                    ]} />
                  </div>
                </div>
              </>
            )}
            {transform.transform_type === "ASOS_HOURLY_TO_CANONICAL" && (
              <>
                <p className="text-xs text-blue-800 bg-blue-50 p-2 rounded">{HELP_TEXTS.asosWeatherTransform}</p>
                <p className="text-xs text-slate-600">{HELP_TEXTS.asosStationPrerequisite}</p>
                <div className="grid grid-cols-2 gap-3">
                  <div><label className="text-xs text-slate-500">source_system</label><TextInput value={transform.source_system || "KMA_ASOS_API"} onChange={(v) => setTransform({ ...transform, source_system: v })} /></div>
                  <div><label className="text-xs text-slate-500">station_code</label><TextInput value={transform.station_code_field || "stnId"} onChange={(v) => setTransform({ ...transform, station_code_field: v })} /></div>
                  <div><label className="text-xs text-slate-500">observed_at</label><TextInput value={transform.observed_at_field || "tm"} onChange={(v) => setTransform({ ...transform, observed_at_field: v })} /></div>
                  <div>
                    <label className="text-xs text-slate-500">미등록 관측소 정책</label>
                    <SelectInput value={transform.station_unmapped_policy || "WARN_ONLY"} onChange={(v) => setTransform({ ...transform, station_unmapped_policy: v })} options={[
                      { value: "WARN_ONLY", label: "WARN_ONLY" },
                      { value: "LOG_UNMAPPED", label: "LOG_UNMAPPED" },
                      { value: "FAIL_LOAD", label: "FAIL_LOAD" },
                    ]} />
                  </div>
                  <div><label className="text-xs text-slate-500">temperature (ta)</label><TextInput value={transform.value_field_mappings_json?.temperature || "ta"} onChange={(v) => setTransform({ ...transform, value_field_mappings_json: { ...(transform.value_field_mappings_json || {}), temperature: v } })} /></div>
                  <div><label className="text-xs text-slate-500">humidity (hm)</label><TextInput value={transform.value_field_mappings_json?.humidity || "hm"} onChange={(v) => setTransform({ ...transform, value_field_mappings_json: { ...(transform.value_field_mappings_json || {}), humidity: v } })} /></div>
                  <div><label className="text-xs text-slate-500">wind_speed (ws)</label><TextInput value={transform.value_field_mappings_json?.wind_speed || "ws"} onChange={(v) => setTransform({ ...transform, value_field_mappings_json: { ...(transform.value_field_mappings_json || {}), wind_speed: v } })} /></div>
                  <div><label className="text-xs text-slate-500">precipitation (rn)</label><TextInput value={transform.value_field_mappings_json?.precipitation || "rn"} onChange={(v) => setTransform({ ...transform, value_field_mappings_json: { ...(transform.value_field_mappings_json || {}), precipitation: v } })} /></div>
                </div>
                <label className="flex items-center gap-2 text-xs"><input type="checkbox" checked={transform.store_raw_json !== false} onChange={(e) => setTransform({ ...transform, store_raw_json: e.target.checked })} />raw_json 저장</label>
              </>
            )}
            {(transform.transform_type === "CALENDAR_SPECIAL_DAY_TO_DATE" || transform.transform_type === "CALENDAR_DATE_TO_HOUR") && (
              <>
                <p className="text-xs text-blue-800 bg-blue-50 p-2 rounded">{HELP_TEXTS.calendarTransform}</p>
                {transform.transform_type === "CALENDAR_DATE_TO_HOUR" && (
                  <p className="text-xs text-slate-600">{HELP_TEXTS.calendarHourTransform}</p>
                )}
                <p className="text-xs text-slate-600">{HELP_TEXTS.calendarMultiOperationHint}</p>
                <div className="grid grid-cols-2 gap-3">
                  <div><label className="text-xs text-slate-500">source_system</label><TextInput value={transform.source_system || "KASI_SPECIAL_DAY_API"} onChange={(v) => setTransform({ ...transform, source_system: v })} /></div>
                  <div>
                    <label className="text-xs text-slate-500">calendar mode</label>
                    <SelectInput value={transform.calendar_mode || "FULL_CALENDAR_WITH_OVERLAY"} onChange={(v) => setTransform({ ...transform, calendar_mode: v })} options={[
                      { value: "SPECIAL_DAYS_ONLY", label: "SPECIAL_DAYS_ONLY" },
                      { value: "FULL_CALENDAR_WITH_OVERLAY", label: "FULL_CALENDAR_WITH_OVERLAY" },
                    ]} />
                  </div>
                  <div><label className="text-xs text-slate-500">calendar_year</label><TextInput value={String(transform.calendar_year ?? "")} onChange={(v) => setTransform({ ...transform, calendar_year: v ? Number(v) : null })} /></div>
                  <div><label className="text-xs text-slate-500">calendar_month (선택)</label><TextInput value={String(transform.calendar_month ?? "")} onChange={(v) => setTransform({ ...transform, calendar_month: v ? Number(v) : null })} /></div>
                  <div><label className="text-xs text-slate-500">locdate</label><TextInput value={transform.date_field || "locdate"} onChange={(v) => setTransform({ ...transform, date_field: v })} /></div>
                  <div><label className="text-xs text-slate-500">date format</label><TextInput value={transform.date_format || "YYYYMMDD"} onChange={(v) => setTransform({ ...transform, date_format: v })} /></div>
                  <div><label className="text-xs text-slate-500">dateName</label><TextInput value={transform.special_day_name_field || "dateName"} onChange={(v) => setTransform({ ...transform, special_day_name_field: v })} /></div>
                  <div><label className="text-xs text-slate-500">isHoliday</label><TextInput value={transform.public_holiday_field || "isHoliday"} onChange={(v) => setTransform({ ...transform, public_holiday_field: v })} /></div>
                  <div>
                    <label className="text-xs text-slate-500">special_day_type (기본)</label>
                    <SelectInput value={transform.default_special_day_type || "PUBLIC_HOLIDAY"} onChange={(v) => setTransform({ ...transform, default_special_day_type: v })} options={[
                      { value: "PUBLIC_HOLIDAY", label: "PUBLIC_HOLIDAY" },
                      { value: "NATIONAL_HOLIDAY", label: "NATIONAL_HOLIDAY" },
                      { value: "ANNIVERSARY", label: "ANNIVERSARY" },
                      { value: "SOLAR_TERM", label: "SOLAR_TERM" },
                      { value: "MISC_SPECIAL_DAY", label: "MISC_SPECIAL_DAY" },
                      { value: "CUSTOM", label: "CUSTOM" },
                    ]} />
                  </div>
                  {transform.transform_type === "CALENDAR_DATE_TO_HOUR" && (
                    <>
                      <div><label className="text-xs text-slate-500">hour_start</label><TextInput value={String(transform.hour_start ?? 0)} onChange={(v) => setTransform({ ...transform, hour_start: Number(v) })} /></div>
                      <div><label className="text-xs text-slate-500">hour_end</label><TextInput value={String(transform.hour_end ?? 23)} onChange={(v) => setTransform({ ...transform, hour_end: Number(v) })} /></div>
                    </>
                  )}
                </div>
              </>
            )}
            {transform.transform_type !== "NONE" && (
              <div className="flex flex-wrap gap-2">
                <Button variant="secondary" disabled={!operationId || busy} onClick={() => void handleTransformPreview()}>변환 미리보기</Button>
                {transform.transform_type === "WIDE_HOUR_TO_LONG" && (
                  <Button variant="ghost" onClick={() => window.open("/external-code-mappings", "_blank")}>외부 코드 매핑 화면</Button>
                )}
                {transform.transform_type === "ASOS_HOURLY_TO_CANONICAL" && (
                  <Button variant="ghost" onClick={() => window.open("/prediction-entities", "_blank")}>ASOS 관측소 기준정보</Button>
                )}
              </div>
            )}
            {transformPreviewResult && (
              <div className="border rounded p-2 text-xs space-y-1">
                <p>변환 유형: {String((transformPreviewResult.transform_summary as Record<string, unknown> | undefined)?.transform_type ?? transform.transform_type)}</p>
                <p>원본 {String(transformPreviewResult.raw_item_count)}건 → 변환 {String(transformPreviewResult.transformed_row_count)}행 · 경고 {String((transformPreviewResult.warnings as unknown[] | undefined)?.length ?? 0)}건</p>
                {(transformPreviewResult.transform_summary as Record<string, unknown> | undefined)?.date_row_count != null && (
                  <p>날짜 {String((transformPreviewResult.transform_summary as Record<string, unknown>).date_row_count)}행 · 시간 {String((transformPreviewResult.transform_summary as Record<string, unknown>).hour_row_count)}행</p>
                )}
                {(transformPreviewResult.unmapped_codes as unknown[] | undefined)?.length ? (
                  <p className="text-amber-700">미매핑 코드 {(transformPreviewResult.unmapped_codes as unknown[]).length}건</p>
                ) : null}
                <pre className="bg-slate-50 p-2 rounded max-h-32 overflow-auto">{safeJsonStringify((transformPreviewResult.sample_rows as unknown[])?.slice(0, 3))}</pre>
              </div>
            )}
          </div>
        );
      case 6:
        return (
          <div className="space-y-3 text-sm">
            <p className="text-xs text-slate-500">ACTIVE 상태이며 물리 테이블이 생성된 표준 데이터셋만 선택할 수 있습니다.</p>
            {targetTables.length === 0 ? (
              <p className="text-amber-700 text-xs bg-amber-50 p-2 rounded">적재 가능한 표준 데이터셋이 없습니다. 표준 데이터셋 Wizard에서 물리 테이블을 먼저 생성하세요.</p>
            ) : (
              <SelectInput
                value={target.target_table}
                onChange={(v) => {
                  const meta = targetTables.find((t) => t.target_table === v);
                  setTarget({ target_table: v, standard_dataset_id: meta?.dataset_type_id || "" });
                  setTargetValidation(null);
                }}
                options={[
                  { value: "", label: "적재 대상 테이블 선택 (선택)" },
                  ...targetTables.map((t) => ({
                    value: t.target_table,
                    label: `${t.dataset_type_name} — ${t.target_table}`,
                  })),
                ]}
              />
            )}
            {selectedTargetMeta && (
              <div className="text-xs text-slate-600 space-y-1 border rounded p-2">
                <p>내부 테이블: <code>{selectedTargetMeta.target_table}</code></p>
                <p>데이터 분류: {selectedTargetMeta.dataset_category || selectedTargetMeta.category || "-"}</p>
                <p>업무 영역: {selectedTargetMeta.business_domain || "-"}</p>
                <p>컬럼: {selectedTargetMeta.standard_columns.join(", ") || "-"}</p>
              </div>
            )}
            {targetValidation && <p className="text-red-600 text-xs">{targetValidation}</p>}
            {columnMatching.rows.length > 0 && (
              <div>
                <p className="text-xs font-medium mb-1">컬럼 매칭 미리보기 (동일 컬럼명 / Data Mapping)</p>
                <table className="w-full text-xs border">
                  <thead><tr className="bg-slate-50"><th className="p-1 text-left">원천 필드</th><th className="p-1 text-left">대상 컬럼</th><th className="p-1 text-left">상태</th></tr></thead>
                  <tbody>
                    {columnMatching.rows.map((r, i) => (
                      <tr key={i} className="border-t">
                        <td className="p-1">{r.source_field}</td>
                        <td className="p-1">{r.target_column || "-"}</td>
                        <td className="p-1">{r.status === "matched" ? "매칭됨" : r.status === "no_target" ? "대상 컬럼 없음" : "원천 필드 없음"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        );
      case 7:
        return (
          <div className="space-y-3 text-sm">
            {!operationId && <p className="text-amber-700 text-xs">이전 단계에서 저장이 완료되어야 테스트 호출이 가능합니다.</p>}
            <div className="flex flex-wrap gap-2">
              <Button variant="secondary" disabled={!operationId || busy} onClick={() => void handleRequestPreview()}>요청 미리보기</Button>
              <Button disabled={!operationId || busy} onClick={() => void handleTestCall()}>테스트 호출</Button>
            </div>
            {requestPreview && (
              <div className="border rounded p-2 text-xs">
                <p className="font-medium">Masked URL</p>
                <p className="font-mono break-all">{String(requestPreview.masked_url)}</p>
                <p className="mt-1">actual_call_ready: {requestPreview.actual_call_ready ? "예" : "아니오"}</p>
                {(requestPreview.warnings as string[] | undefined)?.map((w, i) => <p key={i} className="text-amber-700">{w}</p>)}
              </div>
            )}
            {testResult && (
              <div className="border rounded p-2 text-xs space-y-1">
                <p>HTTP {testResult.http_status} · {testResult.duration_ms}ms · {testResult.item_count}건</p>
                {testResult.sample_items && testResult.sample_items.length > 0 && (
                  <pre className="bg-slate-50 p-2 rounded max-h-40 overflow-auto">{safeJsonStringify(testResult.sample_items.slice(0, 5))}</pre>
                )}
                {testResult.snapshot_id && <p>스냅샷 ID: {testResult.snapshot_id}</p>}
              </div>
            )}
          </div>
        );
      case 8:
        return (
          <div className="space-y-3 text-sm">
            <div className="border rounded p-3 space-y-1 text-xs">
              <p><strong>작업명:</strong> {basic.operation_name}</p>
              <p><strong>endpoint:</strong> {basic.endpoint_path}</p>
              <p><strong>응답 경로:</strong> {responsePath.response_item_path}</p>
              <p><strong>변환:</strong> {{
                NONE: "없음",
                WIDE_HOUR_TO_LONG: "열수요 wide-hour 변환",
                ASOS_HOURLY_TO_CANONICAL: "ASOS 관측 기상 변환",
                CALENDAR_SPECIAL_DAY_TO_DATE: "Calendar/특일 날짜 변환",
                CALENDAR_DATE_TO_HOUR: "Calendar 시간 행 생성",
              }[transform.transform_type] || transform.transform_type}</p>
              <p><strong>파라미터:</strong> {params.length}개</p>
              <p><strong>페이징:</strong> {pagination.pagination_type}</p>
              <p><strong>적재 대상:</strong> {target.target_table || "(미설정)"}</p>
              <p><strong>인증:</strong> {credentialMasked || "(미저장)"}</p>
            </div>
            <div className="flex flex-wrap gap-2">
              <Button onClick={() => void handleFinalSave()} disabled={busy}>{busy ? <Loader2 className="w-4 h-4 animate-spin" /> : "저장"}</Button>
              <Button variant="secondary" disabled={!operationId || !target.target_table || busy} onClick={() => void handleLoadPreview()}>적재 미리보기</Button>
              <Button variant="secondary" disabled={!operationId || !target.target_table || busy} onClick={() => void handleLoadRun()}>적재 실행</Button>
            </div>
            {loadPreviewResult && (
              <div className="text-xs space-y-1 border rounded p-2">
                <p>원본 {String(loadPreviewResult.raw_item_count ?? loadPreviewResult.api_item_count ?? "-")}건 · 변환 {String(loadPreviewResult.transformed_row_count ?? loadPreviewResult.item_count ?? "-")}행</p>
                {(loadPreviewResult.unmapped_codes as unknown[] | undefined)?.length ? (
                  <p className="text-amber-700">미매핑 코드 {(loadPreviewResult.unmapped_codes as unknown[]).length}건 — 외부 코드 매핑을 확인하세요.</p>
                ) : null}
                <pre className="bg-slate-50 p-2 rounded max-h-32 overflow-auto">{safeJsonStringify(loadPreviewResult)}</pre>
              </div>
            )}
            {loadRunResult && (
              <div className="text-xs text-green-700 space-y-1">
                <p>적재 완료: {String(loadRunResult.status ?? loadRunResult.run_status)} — {String(loadRunResult.inserted_count)}건</p>
                {(loadRunResult.result_summary as Record<string, unknown> | undefined)?.transform_summary ? (
                  <p>변환 요약: {safeJsonStringify((loadRunResult.result_summary as Record<string, unknown>).transform_summary)}</p>
                ) : null}
              </div>
            )}
          </div>
        );
      default:
        return null;
    }
  };

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={`REST API 작업 만들기 — ${STEP_TITLES[step]} (${step + 1}/${STEP_TITLES.length})`}
      size="xl"
      footer={
        <div className="flex justify-between w-full">
          <Button variant="ghost" onClick={onClose}>닫기</Button>
          <div className="flex gap-2">
            {step > 0 && <Button variant="secondary" icon={<ChevronLeft className="w-4 h-4" />} onClick={handleBack}>이전</Button>}
            {step < STEP_TITLES.length - 1 && (
              <Button icon={<ChevronRight className="w-4 h-4" />} onClick={() => void handleNext()} disabled={busy}>
                {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : "다음"}
              </Button>
            )}
          </div>
        </div>
      }
    >
      <div className="flex gap-1 mb-4 flex-wrap">
        {STEP_TITLES.map((t, i) => (
          <span key={t} className={`text-xs px-2 py-0.5 rounded ${i === step ? "bg-blue-100 text-blue-800" : "bg-slate-100 text-slate-500"}`}>{i + 1}. {t}</span>
        ))}
      </div>
      {renderStep()}
    </Modal>
  );
}
