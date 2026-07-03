import { useCallback, useEffect, useState } from "react";
import { Plus, Play, Eye, Save } from "lucide-react";
import { fetchApi, postApi, putApi, PagedData } from "@/api/client";
import { Button } from "@/components/Button";
import { DataTable } from "@/components/DataTable";
import { Modal } from "@/components/Modal";
import { SelectInput, TextInput } from "@/components/SearchPanel";
import { LoadingState } from "@/components/Pagination";
import { useToast } from "@/hooks/useToast";
import type { ApiConnectorCallLog, ApiConnectorLoadRun, ApiConnectorOperation } from "@/types/apiConnector";
import { EMPTY_MESSAGES, HELP_TEXTS } from "@/constants/displayLabels";

interface DataSourceOption {
  source_id: string;
  source_name: string;
  source_type: string;
}

const EMPTY_OP = {
  data_source_id: "",
  operation_name: "",
  endpoint_path: "",
  http_method: "GET",
  response_format: "JSON",
  response_item_path: "data.items",
  target_table: "",
};

type SubTab = "operations" | "call-logs" | "load-runs";

export function ApiConnectorPanel() {
  const { showToast } = useToast();
  const [subTab, setSubTab] = useState<SubTab>("operations");
  const [sources, setSources] = useState<DataSourceOption[]>([]);
  const [operations, setOperations] = useState<ApiConnectorOperation[]>([]);
  const [callLogs, setCallLogs] = useState<ApiConnectorCallLog[]>([]);
  const [loadRuns, setLoadRuns] = useState<ApiConnectorLoadRun[]>([]);
  const [loading, setLoading] = useState(true);
  const [createOpen, setCreateOpen] = useState(false);
  const [form, setForm] = useState(EMPTY_OP);
  const [credentialForm, setCredentialForm] = useState({
    data_source_id: "",
    secret_value: "",
    encoding_policy: "STORE_DECODED_ENCODE_ON_CALL",
    key_name: "serviceKey",
  });
  const [detail, setDetail] = useState<Record<string, unknown> | null>(null);
  const [previewResult, setPreviewResult] = useState<Record<string, unknown> | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [srcRes, ops, logs, runs] = await Promise.all([
        fetchApi<PagedData<DataSourceOption>>("/data-sources", { page: 1, size: 200 }),
        fetchApi<ApiConnectorOperation[]>("/api-connectors/operations"),
        fetchApi<ApiConnectorCallLog[]>("/api-connectors/call-logs"),
        fetchApi<ApiConnectorLoadRun[]>("/api-connectors/load-runs"),
      ]);
      const srcItems = srcRes.items || [];
      setSources(srcItems.filter((s) => ["REST_API", "API"].includes(s.source_type)));
      setOperations(ops);
      setCallLogs(logs);
      setLoadRuns(runs);
    } catch {
      showToast("error", "REST API 연결 정보를 불러오지 못했습니다.");
    } finally {
      setLoading(false);
    }
  }, [showToast]);

  useEffect(() => { void load(); }, [load]);

  const handleCreate = async () => {
    if (!form.data_source_id || !form.operation_name || !form.endpoint_path) {
      showToast("warning", "데이터 소스·작업명·endpoint를 입력하세요.");
      return;
    }
    try {
      await postApi("/api-connectors/operations", {
        ...form,
        target_table: form.target_table || undefined,
      });
      showToast("success", "API 작업이 등록되었습니다.");
      setCreateOpen(false);
      setForm(EMPTY_OP);
      load();
    } catch {
      showToast("error", "API 작업 등록에 실패했습니다.");
    }
  };

  const handleSaveCredential = async () => {
    if (!credentialForm.data_source_id || !credentialForm.secret_value) {
      showToast("warning", "데이터 소스와 인증 키를 입력하세요.");
      return;
    }
    try {
      const res = await putApi<Record<string, unknown>>(
        `/api-connectors/data-sources/${credentialForm.data_source_id}/credential`,
        {
          credential_type: "API_KEY",
          key_location: "QUERY",
          key_name: credentialForm.key_name,
          secret_value: credentialForm.secret_value,
          encoding_policy: credentialForm.encoding_policy,
        },
      );
      showToast("success", `인증 정보 저장됨 (${String(res.secret_value_masked || "****")})`);
      setCredentialForm((f) => ({ ...f, secret_value: "" }));
    } catch {
      showToast("error", "인증 정보 저장에 실패했습니다.");
    }
  };

  const handleTestCall = async (op: ApiConnectorOperation) => {
    try {
      const res = await postApi<Record<string, unknown>>(
        `/api-connectors/operations/${op.operation_id}/test-call`,
        { runtime_params: {} },
      );
      setDetail(res);
      showToast("success", `테스트 호출 성공 (${res.item_count}건)`);
      load();
    } catch {
      showToast("error", "테스트 호출에 실패했습니다.");
    }
  };

  const handleRequestPreview = async (op: ApiConnectorOperation) => {
    try {
      const res = await postApi<Record<string, unknown>>(
        `/api-connectors/operations/${op.operation_id}/request-preview`,
        { runtime_params: {} },
      );
      setPreviewResult(res);
    } catch {
      showToast("error", "요청 미리보기에 실패했습니다.");
    }
  };

  if (loading) return <LoadingState />;

  return (
    <div className="mt-8 border-t pt-6">
      <h2 className="text-lg font-semibold text-slate-800 mb-1">REST API 연결</h2>
      <p className="text-sm text-slate-500 mb-2">외부 REST API endpoint를 API 작업 단위로 등록·테스트·적재합니다.</p>
      <div className="bg-amber-50 border border-amber-100 rounded p-3 mb-4 text-xs text-amber-900">
        {HELP_TEXTS.serviceKeyEncoding}
      </div>

      <div className="flex gap-2 mb-4">
        {[
          ["operations", "API 작업"],
          ["call-logs", "호출 이력"],
          ["load-runs", "적재 이력"],
        ].map(([id, label]) => (
          <button
            key={id}
            type="button"
            onClick={() => setSubTab(id as SubTab)}
            className={`px-3 py-1.5 text-sm rounded border ${
              subTab === id ? "bg-blue-50 border-blue-200 text-blue-700" : "bg-white text-slate-600"
            }`}
          >
            {label}
          </button>
        ))}
        <Button variant="secondary" icon={<Plus className="w-4 h-4" />} onClick={() => setCreateOpen(true)}>
          API 작업 등록
        </Button>
      </div>

      {subTab === "operations" && (
        operations.length === 0 ? (
          <div className="text-center py-12 text-slate-500 bg-slate-50 rounded border border-dashed text-sm">
            {EMPTY_MESSAGES.apiConnectorOperations}
          </div>
        ) : (
          <DataTable
            columns={[
              { key: "operation_name", header: "API 작업명" },
              { key: "data_source_id", header: "데이터 소스" },
              { key: "endpoint_path", header: "endpoint" },
              { key: "response_item_path", header: "응답 데이터 경로", render: (r) => String(r.response_item_path || "-") },
              {
                key: "actions",
                header: "작업",
                render: (r) => {
                  const row = r as unknown as ApiConnectorOperation;
                  return (
                    <div className="flex gap-1">
                      <Button variant="ghost" icon={<Eye className="w-3 h-3" />} onClick={() => void handleRequestPreview(row)}>
                        요청 미리보기
                      </Button>
                      <Button variant="ghost" icon={<Play className="w-3 h-3" />} onClick={() => void handleTestCall(row)}>
                        테스트 호출
                      </Button>
                    </div>
                  );
                },
              },
            ]}
            data={operations as unknown as Record<string, unknown>[]}
          />
        )
      )}

      {subTab === "call-logs" && (
        <DataTable
          columns={[
            { key: "called_at", header: "호출 시각" },
            { key: "operation_id", header: "API 작업" },
            { key: "http_status", header: "HTTP" },
            { key: "response_item_count", header: "항목 수" },
            { key: "success_yn", header: "성공", render: (r) => (r.success_yn ? "예" : "아니오") },
          ]}
          data={callLogs as unknown as Record<string, unknown>[]}
          emptyMessage="호출 이력이 없습니다."
        />
      )}

      {subTab === "load-runs" && (
        <DataTable
          columns={[
            { key: "started_at", header: "시작" },
            { key: "operation_id", header: "API 작업" },
            { key: "target_table", header: "적재 대상" },
            { key: "run_status", header: "상태" },
            { key: "inserted_count", header: "적재 건수" },
          ]}
          data={loadRuns as unknown as Record<string, unknown>[]}
          emptyMessage="적재 이력이 없습니다."
        />
      )}

      <div className="mt-6 p-4 bg-slate-50 rounded border">
        <h3 className="text-sm font-semibold mb-2">인증 정보 (serviceKey)</h3>
        <p className="text-xs text-slate-500 mb-3">{HELP_TEXTS.secretMasking}</p>
        <div className="grid grid-cols-2 gap-3 max-w-2xl">
          <SelectInput
            value={credentialForm.data_source_id}
            onChange={(v) => setCredentialForm({ ...credentialForm, data_source_id: v })}
            options={[{ value: "", label: "데이터 소스 선택" }, ...sources.map((s) => ({ value: s.source_id, label: s.source_name }))]}
          />
          <label className="block text-xs text-slate-500 mb-1">serviceKey (Decoding 키 권장)</label>
          <input
            type="password"
            value={credentialForm.secret_value}
            onChange={(e) => setCredentialForm({ ...credentialForm, secret_value: e.target.value })}
            className="w-full border border-slate-200 rounded-md px-2 py-1.5 text-sm bg-slate-50"
          />
        </div>
        <Button className="mt-3" variant="secondary" icon={<Save className="w-4 h-4" />} onClick={() => void handleSaveCredential()}>
          인증 정보 저장
        </Button>
      </div>

      <Modal open={createOpen} onClose={() => setCreateOpen(false)} title="API 작업 등록">
        <div className="space-y-3 text-sm">
          <SelectInput
            value={form.data_source_id}
            onChange={(v) => setForm({ ...form, data_source_id: v })}
            options={[{ value: "", label: "데이터 소스" }, ...sources.map((s) => ({ value: s.source_id, label: s.source_name }))]}
          />
          <label className="block text-xs text-slate-500 mb-1">API 작업명</label>
          <TextInput value={form.operation_name} onChange={(v) => setForm({ ...form, operation_name: v })} />
          <label className="block text-xs text-slate-500 mb-1">endpoint 경로</label>
          <TextInput value={form.endpoint_path} onChange={(v) => setForm({ ...form, endpoint_path: v })} />
          <label className="block text-xs text-slate-500 mb-1">응답 데이터 경로</label>
          <TextInput value={form.response_item_path} onChange={(v) => setForm({ ...form, response_item_path: v })} />
          <label className="block text-xs text-slate-500 mb-1">적재 대상 테이블 (선택)</label>
          <TextInput value={form.target_table} onChange={(v) => setForm({ ...form, target_table: v })} />
          <Button onClick={() => void handleCreate()}>저장</Button>
        </div>
      </Modal>

      <Modal open={!!previewResult} onClose={() => setPreviewResult(null)} title="요청 미리보기">
        {previewResult && (
          <pre className="text-xs bg-slate-50 p-3 rounded overflow-auto max-h-64">
            {JSON.stringify(previewResult, null, 2)}
          </pre>
        )}
      </Modal>

      <Modal open={!!detail} onClose={() => setDetail(null)} title="테스트 호출 결과">
        {detail && (
          <pre className="text-xs bg-slate-50 p-3 rounded overflow-auto max-h-64">
            {JSON.stringify(detail, null, 2)}
          </pre>
        )}
      </Modal>
    </div>
  );
}
