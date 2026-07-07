import { useCallback, useEffect, useMemo, useState } from "react";
import { Eye, Play, Plus, RefreshCw, Upload } from "lucide-react";
import { fetchApi, PagedData } from "@/api/client";
import {
  apiConnectorErrorMessage,
  getApiConnectorLoadRun,
  getApiConnectorSnapshot,
  listApiConnectorCallLogs,
  listApiConnectorLoadRuns,
  listApiConnectorOperations,
  loadApiConnectorPreview,
  requestApiConnectorPreview,
  runApiConnectorLoad,
  testApiConnectorCall,
} from "@/api/apiConnectors";
import { ApiConnectorOperationWizard } from "@/components/ApiConnectorOperationWizard";
import { Button } from "@/components/Button";
import { DataTable } from "@/components/DataTable";
import { Modal } from "@/components/Modal";
import { LoadingState } from "@/components/Pagination";
import { useToast } from "@/hooks/useToast";
import type {
  ApiConnectorCallLog,
  ApiConnectorLoadRun,
  ApiConnectorOperation,
  ApiConnectorSnapshot,
} from "@/types/apiConnector";
import { safeJsonStringify } from "@/utils/apiConnectorDisplay";
import { EMPTY_MESSAGES, HELP_TEXTS, lifecycleStatusLabel } from "@/constants/displayLabels";

interface DataSourceOption {
  source_id: string;
  source_name: string;
  source_type: string;
  connection_info?: Record<string, string>;
}

type SubTab = "operations" | "call-logs" | "load-runs" | "snapshots";

export function ApiConnectorPanel() {
  const { showToast } = useToast();
  const [subTab, setSubTab] = useState<SubTab>("operations");
  const [sources, setSources] = useState<DataSourceOption[]>([]);
  const [operations, setOperations] = useState<ApiConnectorOperation[]>([]);
  const [callLogs, setCallLogs] = useState<ApiConnectorCallLog[]>([]);
  const [loadRuns, setLoadRuns] = useState<ApiConnectorLoadRun[]>([]);
  const [loading, setLoading] = useState(true);
  const [wizardOpen, setWizardOpen] = useState(false);
  const [editOpId, setEditOpId] = useState<string | null>(null);
  const [busyOpId, setBusyOpId] = useState<string | null>(null);

  const [previewModal, setPreviewModal] = useState<Record<string, unknown> | null>(null);
  const [testModal, setTestModal] = useState<Record<string, unknown> | null>(null);
  const [loadPreviewModal, setLoadPreviewModal] = useState<Record<string, unknown> | null>(null);
  const [callLogDetail, setCallLogDetail] = useState<ApiConnectorCallLog | null>(null);
  const [loadRunDetail, setLoadRunDetail] = useState<ApiConnectorLoadRun | null>(null);
  const [snapshotDetail, setSnapshotDetail] = useState<ApiConnectorSnapshot | null>(null);

  const opNameMap = useMemo(
    () => Object.fromEntries(operations.map((o) => [o.operation_id, o.operation_name])),
    [operations],
  );

  const snapshotRows = useMemo(
    () => callLogs.filter((l) => l.raw_response_snapshot_id),
    [callLogs],
  );

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [srcRes, ops, logs, runs] = await Promise.all([
        fetchApi<PagedData<DataSourceOption>>("/data-sources", { page: 1, size: 200 }),
        listApiConnectorOperations(),
        listApiConnectorCallLogs(),
        listApiConnectorLoadRuns(),
      ]);
      setSources(srcRes.items || []);
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

  const openWizard = (operationId?: string) => {
    setEditOpId(operationId || null);
    setWizardOpen(true);
  };

  const runAction = async (
    op: ApiConnectorOperation,
    action: "request-preview" | "test-call" | "load-preview" | "load-run",
  ) => {
    setBusyOpId(op.operation_id);
    try {
      if (action === "request-preview") {
        const res = await requestApiConnectorPreview(op.operation_id);
        setPreviewModal(res as unknown as Record<string, unknown>);
      } else if (action === "test-call") {
        const res = await testApiConnectorCall(op.operation_id);
        setTestModal(res as unknown as Record<string, unknown>);
        showToast("success", `테스트 호출 완료 (${res.item_count}건)`);
        void load();
      } else if (action === "load-preview") {
        if (!op.target_table) {
          showToast("warning", "적재 대상 테이블이 설정되지 않았습니다.");
          return;
        }
        const res = await loadApiConnectorPreview(op.operation_id);
        setLoadPreviewModal(res as unknown as Record<string, unknown>);
      } else if (action === "load-run") {
        if (!op.target_table) {
          showToast("warning", "적재 대상 테이블이 설정되지 않았습니다.");
          return;
        }
        if (!window.confirm(
          "현재 API 응답 데이터를 적재 대상 테이블에 INSERT합니다. 중복 처리와 upsert는 후속 단계에서 고도화됩니다.",
        )) return;
        const res = await runApiConnectorLoad(op.operation_id);
        showToast("success", `적재 실행 완료 (${res.inserted_count}건)`);
        setSubTab("load-runs");
        void load();
      }
    } catch (e) {
      showToast("error", apiConnectorErrorMessage(e, "요청에 실패했습니다."));
    } finally {
      setBusyOpId(null);
    }
  };

  const viewSnapshot = async (snapshotId: string) => {
    try {
      const snap = await getApiConnectorSnapshot(snapshotId);
      setSnapshotDetail(snap);
    } catch (e) {
      showToast("error", apiConnectorErrorMessage(e, "스냅샷을 불러오지 못했습니다."));
    }
  };

  const viewLoadRun = async (loadRunId: string) => {
    try {
      const run = await getApiConnectorLoadRun(loadRunId);
      setLoadRunDetail(run);
    } catch (e) {
      showToast("error", apiConnectorErrorMessage(e, "적재 이력을 불러오지 못했습니다."));
    }
  };

  if (loading) return <LoadingState />;

  return (
    <div className="mt-8 border-t pt-6" data-testid="api-connector-panel">
      <h2 className="text-lg font-semibold text-slate-800 mb-1">REST API 연결</h2>
      <p className="text-sm text-slate-500 mb-2">
        외부 REST API의 endpoint, 요청 파라미터, 인증 정보, 응답 데이터 경로를 등록하고 표준 데이터셋으로 적재합니다.
        API 작업 등록 후 <span className="text-slate-600">요청 미리보기</span>·<span className="text-slate-600">테스트 호출</span>·<span className="text-slate-600">적재 미리보기</span>·<span className="text-slate-600">적재 실행</span>을 사용할 수 있습니다.
      </p>
      <div className="bg-amber-50 border border-amber-100 rounded p-3 mb-4 text-xs text-amber-900">
        {HELP_TEXTS.serviceKeyEncoding}
      </div>
      <div className="bg-blue-50 border border-blue-100 rounded p-3 mb-4 text-xs text-blue-900 space-y-1">
        <p>기상청 단기예보 API 작업은 <a href="/predictions/jobs" className="underline text-blue-700">예측 작업</a> 화면의 단기예보 입력 생성기 설정에서 선택해 예측 실행 시 on-demand 호출됩니다. 예측 대상의 nx/ny 매핑이 필요합니다.</p>
        <p>{HELP_TEXTS.forecastProviderHint}</p>
        <p>{HELP_TEXTS.asosStationPrerequisite}</p>
        <p>{HELP_TEXTS.calendarMultiOperationHint}</p>
        <p>{HELP_TEXTS.restApiConnectorExternalCodeLink}</p>
      </div>

      <div className="flex flex-wrap gap-2 mb-4 items-center">
        {[
          ["operations", "API 작업"],
          ["call-logs", "호출 이력"],
          ["load-runs", "적재 이력"],
          ["snapshots", "원본 응답 스냅샷"],
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
        <Button variant="secondary" icon={<RefreshCw className="w-4 h-4" />} onClick={() => void load()}>
          새로고침
        </Button>
        <Button icon={<Plus className="w-4 h-4" />} onClick={() => openWizard()}>
          새 API 작업 만들기
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
              { key: "target_table", header: "적재 대상", render: (r) => String(r.target_table || "-") },
              {
                key: "actions",
                header: "작업",
                render: (r) => {
                  const row = r as unknown as ApiConnectorOperation;
                  const busy = busyOpId === row.operation_id;
                  return (
                    <div className="flex flex-wrap gap-1">
                      <Button variant="ghost" disabled={busy} onClick={() => openWizard(row.operation_id)}>수정</Button>
                      <Button variant="ghost" icon={<Eye className="w-3 h-3" />} disabled={busy} onClick={() => void runAction(row, "request-preview")}>요청 미리보기</Button>
                      <Button variant="ghost" icon={<Play className="w-3 h-3" />} disabled={busy} onClick={() => void runAction(row, "test-call")}>테스트 호출</Button>
                      <Button variant="ghost" icon={<Upload className="w-3 h-3" />} disabled={busy || !row.target_table} onClick={() => void runAction(row, "load-preview")}>적재 미리보기</Button>
                      <Button variant="ghost" disabled={busy || !row.target_table} onClick={() => void runAction(row, "load-run")}>적재 실행</Button>
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
            { key: "operation_id", header: "API 작업", render: (r) => opNameMap[String(r.operation_id)] || String(r.operation_id) },
            { key: "http_status", header: "HTTP" },
            { key: "response_item_count", header: "항목 수" },
            { key: "duration_ms", header: "ms" },
            { key: "success_yn", header: "성공", render: (r) => (r.success_yn ? "예" : "아니오") },
            {
              key: "detail",
              header: "상세",
              render: (r) => (
                <Button variant="ghost" onClick={() => setCallLogDetail(r as unknown as ApiConnectorCallLog)}>보기</Button>
              ),
            },
          ]}
          data={callLogs as unknown as Record<string, unknown>[]}
          emptyMessage="호출 이력이 없습니다."
        />
      )}

      {subTab === "load-runs" && (
        <DataTable
          columns={[
            { key: "started_at", header: "시작" },
            { key: "operation_id", header: "API 작업", render: (r) => opNameMap[String(r.operation_id)] || String(r.operation_id) },
            { key: "target_table", header: "적재 대상" },
            { key: "run_status", header: "상태", render: (r) => lifecycleStatusLabel(String(r.run_status), String(r.run_status)) },
            { key: "inserted_count", header: "적재" },
            { key: "error_count", header: "오류" },
            {
              key: "detail",
              header: "상세",
              render: (r) => (
                <Button variant="ghost" onClick={() => void viewLoadRun(String(r.load_run_id))}>보기</Button>
              ),
            },
          ]}
          data={loadRuns as unknown as Record<string, unknown>[]}
          emptyMessage="적재 이력이 없습니다."
        />
      )}

      {subTab === "snapshots" && (
        <DataTable
          columns={[
            { key: "called_at", header: "캡처 시각", render: (r) => String(r.called_at) },
            { key: "operation_id", header: "API 작업", render: (r) => opNameMap[String(r.operation_id)] || String(r.operation_id) },
            { key: "response_item_count", header: "항목 수" },
            {
              key: "snapshot",
              header: "스냅샷",
              render: (r) => (
                <Button variant="ghost" onClick={() => void viewSnapshot(String(r.raw_response_snapshot_id))}>보기</Button>
              ),
            },
          ]}
          data={snapshotRows as unknown as Record<string, unknown>[]}
          emptyMessage="저장된 원본 응답 스냅샷이 없습니다. 테스트 호출 후 생성됩니다."
        />
      )}

      <ApiConnectorOperationWizard
        open={wizardOpen}
        onClose={() => { setWizardOpen(false); setEditOpId(null); }}
        onCompleted={() => void load()}
        sources={sources}
        editOperationId={editOpId}
      />

      <Modal open={!!previewModal} onClose={() => setPreviewModal(null)} title="요청 미리보기" size="lg">
        {previewModal && (
          <pre className="text-xs bg-slate-50 p-3 rounded overflow-auto max-h-80">{safeJsonStringify(previewModal)}</pre>
        )}
      </Modal>

      <Modal open={!!testModal} onClose={() => setTestModal(null)} title="테스트 호출 결과" size="lg">
        {testModal && (
          <pre className="text-xs bg-slate-50 p-3 rounded overflow-auto max-h-80">{safeJsonStringify(testModal)}</pre>
        )}
      </Modal>

      <Modal open={!!loadPreviewModal} onClose={() => setLoadPreviewModal(null)} title="적재 미리보기" size="lg">
        {loadPreviewModal && (
          <pre className="text-xs bg-slate-50 p-3 rounded overflow-auto max-h-80">{safeJsonStringify(loadPreviewModal)}</pre>
        )}
      </Modal>

      <Modal open={!!callLogDetail} onClose={() => setCallLogDetail(null)} title="호출 이력 상세" size="lg">
        {callLogDetail && (
          <div className="text-xs space-y-2">
            <p><strong>URL:</strong> {callLogDetail.request_url_masked}</p>
            <p><strong>HTTP:</strong> {callLogDetail.http_status} · <strong>항목:</strong> {callLogDetail.response_item_count}</p>
            {callLogDetail.error_message && <p className="text-red-600">{callLogDetail.error_message}</p>}
            <pre className="bg-slate-50 p-2 rounded max-h-48 overflow-auto">{safeJsonStringify(callLogDetail.request_params_masked)}</pre>
            {callLogDetail.raw_response_snapshot_id && (
              <Button variant="secondary" onClick={() => void viewSnapshot(callLogDetail.raw_response_snapshot_id!)}>스냅샷 보기</Button>
            )}
          </div>
        )}
      </Modal>

      <Modal open={!!loadRunDetail} onClose={() => setLoadRunDetail(null)} title="적재 이력 상세" size="lg">
        {loadRunDetail && (
          <div className="text-xs space-y-2">
            <p><strong>상태:</strong> {lifecycleStatusLabel(loadRunDetail.run_status)}</p>
            <p><strong>적재:</strong> {loadRunDetail.inserted_count} · <strong>건너뜀:</strong> {loadRunDetail.skipped_count ?? 0} · <strong>오류:</strong> {loadRunDetail.error_count ?? 0}</p>
            {loadRunDetail.error_message && <p className="text-red-600">{loadRunDetail.error_message}</p>}
            <pre className="bg-slate-50 p-2 rounded max-h-48 overflow-auto">{safeJsonStringify(loadRunDetail)}</pre>
          </div>
        )}
      </Modal>

      <Modal open={!!snapshotDetail} onClose={() => setSnapshotDetail(null)} title="원본 응답 스냅샷" size="xl">
        {snapshotDetail && (
          <div className="text-xs space-y-3">
            <p>형식: {snapshotDetail.response_format} · 항목: {snapshotDetail.item_count} · 샘플만: {snapshotDetail.sample_only_yn ? "예" : "아니오"}</p>
            {snapshotDetail.normalized_items_json && (
              <div>
                <p className="font-medium mb-1">정규화 항목 (샘플)</p>
                <pre className="bg-slate-50 p-2 rounded max-h-48 overflow-auto">{safeJsonStringify(snapshotDetail.normalized_items_json.slice(0, 5))}</pre>
              </div>
            )}
            {snapshotDetail.raw_response_preview && (
              <details>
                <summary className="cursor-pointer font-medium">원본 응답 (일부)</summary>
                <pre className="bg-slate-50 p-2 rounded max-h-48 overflow-auto mt-1 whitespace-pre-wrap">{snapshotDetail.raw_response_preview}</pre>
              </details>
            )}
          </div>
        )}
      </Modal>
    </div>
  );
}
