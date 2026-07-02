import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Plus, Plug, Trash2, Eye, Pencil, Upload } from "lucide-react";
import { deleteApi, extractApiErrorMessage, fetchApi, postApi, putApi, PagedData } from "@/api/client";
import { Button } from "@/components/Button";
import { DataTable } from "@/components/DataTable";
import { Modal } from "@/components/Modal";
import { StatusBadge } from "@/components/StatusBadge";
import { Pagination, LoadingState, ErrorState } from "@/components/Pagination";
import { SelectInput, TextInput } from "@/components/SearchPanel";
import { useToast } from "@/hooks/useToast";
import { PageHeader } from "@/layouts/MainLayout";
import {
  defaultIngestionPeriod,
  formatDisplayDateTime,
  INGESTION_LIMIT_OPTIONS,
  isPeriodWithinRange,
  SourceDataRange,
  toNaiveApiDateTime,
  validateCsvIngestionPeriod,
} from "@/utils/ingestionPeriod";

interface DataSource {
  source_id: string;
  source_name: string;
  source_type: string;
  data_domain: string;
  connection_info: Record<string, string>;
  active_yn: boolean;
  last_loaded_at: string | null;
  created_at?: string | null;
}

interface ConnectionTestResult {
  success: boolean;
  message: string;
  latency_ms: number;
  error_message: string | null;
  sample_row_count: number;
  columns?: string[];
}

interface DeleteBlocker {
  code: string;
  count?: number;
  message: string;
  items?: { mapping_id: string; mapping_name: string }[];
}

interface DeleteBlockersResponse {
  source_id: string;
  can_delete: boolean;
  blockers: DeleteBlocker[];
}

const EMPTY_FORM = {
  source_name: "",
  source_type: "DB_POSTGRES",
  data_domain: "HEAT_DEMAND",
  host: "postgres",
  port: "5432",
  database: "thermops",
  schema: "public",
  table: "",
  username: "thermops",
  password: "thermops",
  query: "",
  timestamp_column: "measured_at",
  base_url: "http://localhost:8000/api/v1",
  endpoint: "/sample-external/heat-demand",
  method: "GET",
  item_path: "data.items",
  auth_type: "NONE",
  api_key_header: "",
  api_key: "",
  file_path: "",
  active_yn: true,
};

function isCsvType(t: string) {
  return t === "CSV" || t === "FILE_CSV";
}

function isDbType(t: string) {
  return t === "DB_POSTGRES" || t === "DB";
}

function isApiType(t: string) {
  return t === "REST_API" || t === "API";
}

function formFromSource(ds: DataSource) {
  const ci = ds.connection_info || {};
  return {
    source_name: ds.source_name,
    source_type: ds.source_type,
    data_domain: ds.data_domain,
    host: ci.host || "",
    port: String(ci.port || "5432"),
    database: ci.database || "",
    schema: ci.schema || "public",
    table: ci.table || "",
    username: ci.username || "",
    password: ci.password || "",
    query: ci.query || "",
    timestamp_column: ci.timestamp_column || "measured_at",
    base_url: ci.base_url || "",
    endpoint: ci.endpoint || "",
    method: ci.method || "GET",
    item_path: ci.item_path || "items",
    auth_type: ci.auth_type || "NONE",
    api_key_header: ci.api_key_header || "",
    api_key: ci.api_key || "",
    file_path: ci.file_path || "",
    active_yn: ds.active_yn,
  };
}

function buildConnectionInfo(form: typeof EMPTY_FORM) {
  if (isCsvType(form.source_type)) {
    return {
      file_path: form.file_path,
      encoding: "utf-8",
      delimiter: ",",
    };
  }
  if (isApiType(form.source_type)) {
    return {
      base_url: form.base_url,
      endpoint: form.endpoint,
      method: form.method || "GET",
      headers: {},
      query_params: { start_at: "{start_at}", end_at: "{end_at}" },
      auth_type: form.auth_type || "NONE",
      api_key_header: form.api_key_header || null,
      api_key: form.api_key || null,
      item_path: form.item_path || "data.items",
      pagination: { type: "NONE" },
    };
  }
  return {
    host: form.host,
    port: Number(form.port || 5432),
    database: form.database,
    schema: form.schema || "public",
    table: form.table,
    username: form.username,
    password: form.password,
    query: form.query || null,
    timestamp_column: form.timestamp_column || "measured_at",
  };
}

export default function DataSourcesPage() {
  const { showToast } = useToast();
  const [items, setItems] = useState<DataSource[]>([]);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [createOpen, setCreateOpen] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<DataSource | null>(null);
  const [deleteBlockers, setDeleteBlockers] = useState<DeleteBlockersResponse | null>(null);
  const [detail, setDetail] = useState<DataSource | null>(null);
  const [editTarget, setEditTarget] = useState<DataSource | null>(null);
  const [testResult, setTestResult] = useState<ConnectionTestResult | null>(null);
  const [form, setForm] = useState(EMPTY_FORM);
  const [saving, setSaving] = useState(false);
  const [ingesting, setIngesting] = useState<string | null>(null);
  const [ingestTarget, setIngestTarget] = useState<DataSource | null>(null);
  const [sourceRange, setSourceRange] = useState<SourceDataRange | null>(null);
  const [rangeLoading, setRangeLoading] = useState(false);
  const [ingestForm, setIngestForm] = useState({
    start_at: "",
    end_at: "",
    limit: "",
    load_mode: "UPSERT",
  });

  const load = async (p = page) => {
    setLoading(true);
    setError("");
    try {
      const res = await fetchApi<PagedData<DataSource>>("/data-sources", { page: p, size: 20 });
      setItems(res.items);
      setTotalPages(res.total_pages);
    } catch {
      setError("데이터 소스 목록을 불러오지 못했습니다.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(page); }, [page]);

  const buildPayload = () => ({
    source_name: form.source_name,
    source_type: form.source_type,
    data_domain: form.data_domain,
    connection_info: buildConnectionInfo(form),
    active_yn: form.active_yn,
  });

  const handleCreate = async () => {
    if (!form.source_name.trim()) {
      showToast("warning", "소스명을 입력하세요.");
      return;
    }
    setSaving(true);
    try {
      await postApi("/data-sources", buildPayload());
      showToast("success", "데이터 소스가 등록되었습니다.");
      setCreateOpen(false);
      setForm(EMPTY_FORM);
      load(1);
      setPage(1);
    } catch {
      showToast("error", "등록에 실패했습니다.");
    } finally {
      setSaving(false);
    }
  };

  const handleUpdate = async () => {
    if (!editTarget || !form.source_name.trim()) {
      showToast("warning", "소스명을 입력하세요.");
      return;
    }
    setSaving(true);
    try {
      await putApi(`/data-sources/${editTarget.source_id}`, {
        source_name: form.source_name,
        source_type: form.source_type,
        connection_info: buildConnectionInfo(form),
        active_yn: form.active_yn,
      });
      showToast("success", "데이터 소스가 수정되었습니다.");
      setEditTarget(null);
      load();
    } catch {
      showToast("error", "수정에 실패했습니다.");
    } finally {
      setSaving(false);
    }
  };

  const openDelete = async (row: DataSource) => {
    setDeleteTarget(row);
    setDeleteBlockers(null);
    try {
      const res = await fetchApi<DeleteBlockersResponse>(`/data-sources/${row.source_id}/delete-blockers`);
      setDeleteBlockers(res);
    } catch {
      setDeleteBlockers(null);
    }
  };

  const handleDelete = async () => {
    if (!deleteTarget) return;
    try {
      await deleteApi(`/data-sources/${deleteTarget.source_id}`);
      showToast("success", "데이터 소스가 삭제되었습니다.");
      setDeleteTarget(null);
      load();
    } catch (err) {
      showToast("error", extractApiErrorMessage(err, "삭제에 실패했습니다."));
    }
  };

  const handleDetail = async (row: DataSource) => {
    try {
      const res = await fetchApi<DataSource>(`/data-sources/${row.source_id}`);
      setDetail(res);
    } catch {
      showToast("error", "상세 정보를 불러오지 못했습니다.");
    }
  };

  const openEdit = (row: DataSource) => {
    setEditTarget(row);
    setForm(formFromSource(row));
  };

  const handleTest = async (row: DataSource) => {
    try {
      const res = await postApi<ConnectionTestResult>(`/data-sources/${row.source_id}/test-connection`);
      setTestResult(res);
    } catch {
      setTestResult({
        success: false,
        message: "연결 테스트에 실패했습니다.",
        latency_ms: 0,
        error_message: "API 요청 오류",
        sample_row_count: 0,
      });
    }
  };

  const loadSourceRange = useCallback(async (row: DataSource) => {
    if (!isCsvType(row.source_type)) {
      setSourceRange(null);
      setIngestForm((f) => ({ ...f, start_at: "", end_at: "" }));
      return;
    }
    setRangeLoading(true);
    try {
      const range = await fetchApi<SourceDataRange>(`/data-sources/${encodeURIComponent(row.source_id)}/source-range`);
      setSourceRange(range);
      if (range.exists) {
        const { start, end } = defaultIngestionPeriod(range);
        setIngestForm((f) => ({ ...f, start_at: start, end_at: end }));
      } else {
        setIngestForm((f) => ({ ...f, start_at: "", end_at: "" }));
      }
    } catch {
      setSourceRange(null);
      setIngestForm((f) => ({ ...f, start_at: "", end_at: "" }));
    } finally {
      setRangeLoading(false);
    }
  }, []);

  const openIngestModal = (row: DataSource) => {
    setIngestTarget(row);
    setSourceRange(null);
    setIngestForm({ start_at: "", end_at: "", limit: "", load_mode: "UPSERT" });
    void loadSourceRange(row);
  };

  const validateIngest = (): string | null => {
    if (!ingestTarget) return "적재 대상이 없습니다.";
    if (isCsvType(ingestTarget.source_type)) {
      return validateCsvIngestionPeriod(ingestForm.start_at, ingestForm.end_at, sourceRange);
    }
    if (ingestForm.start_at && ingestForm.end_at && ingestForm.start_at > ingestForm.end_at) {
      return "시작 시각은 종료 시각보다 이전이어야 합니다.";
    }
    return null;
  };

  const runIngest = async () => {
    if (!ingestTarget) return;
    const validationError = validateIngest();
    if (validationError) {
      showToast("warning", validationError);
      return;
    }
    setIngesting(ingestTarget.source_id);
    const params = new URLSearchParams({ source_id: ingestTarget.source_id, load_mode: ingestForm.load_mode });
    if (ingestForm.start_at.trim()) params.set("start_at", toNaiveApiDateTime(ingestForm.start_at.trim()));
    if (ingestForm.end_at.trim()) params.set("end_at", toNaiveApiDateTime(ingestForm.end_at.trim()));
    if (ingestForm.limit.trim()) params.set("limit", ingestForm.limit.trim());
    try {
      const res = await postApi<{
        job_id: string;
        status: string;
        source_type?: string;
        connector_type?: string;
        inserted_count?: number;
        updated_count?: number;
        failed_count?: number;
        skipped_count?: number;
      }>(`/ingestion-jobs?${params.toString()}`);
      const inserted = res.inserted_count ?? 0;
      const updated = res.updated_count ?? 0;
      const failed = res.failed_count ?? 0;
      const skipped = res.skipped_count ?? 0;
      showToast(
        "success",
        `[${res.source_type ?? ingestTarget.source_type}] 신규 ${inserted} / 갱신 ${updated} / 실패 ${failed} / 건너뜀 ${skipped} — ${res.job_id}`,
      );
      setIngestTarget(null);
      load();
    } catch (err: unknown) {
      const ax = err as { response?: { data?: { detail?: string | { message?: string; connector_type?: string; error_code?: string } } } };
      const detail = ax.response?.data?.detail;
      const msg = typeof detail === "string"
        ? detail
        : detail?.message || "적재 실행에 실패했습니다.";
      const connector = typeof detail === "object" && detail?.connector_type ? ` [${detail.connector_type}]` : "";
      showToast("error", `${msg}${connector}`);
    } finally {
      setIngesting(null);
    }
  };

  const handleIngest = (row: DataSource) => openIngestModal(row);

  const isCsvIngest = ingestTarget ? isCsvType(ingestTarget.source_type) : false;
  const csvPeriodInRange = isCsvIngest && sourceRange?.exists
    ? isPeriodWithinRange(ingestForm.start_at, ingestForm.end_at, sourceRange.min_at, sourceRange.max_at)
    : true;
  const ingestBlocked = Boolean(validateIngest()) || (isCsvIngest && rangeLoading);

  const rangeBoxClass = isCsvIngest && !sourceRange?.exists
    ? "bg-amber-50 border-amber-200 text-amber-900"
    : isCsvIngest && ingestForm.start_at && ingestForm.end_at && !csvPeriodInRange
      ? "bg-red-50 border-red-200 text-red-900"
      : "bg-slate-50 border-slate-200 text-slate-700";

  const sourceFormFields = (
    <div className="space-y-3">
      <div>
        <label className="block text-xs text-slate-500 mb-1">소스명</label>
        <TextInput value={form.source_name} onChange={(v) => setForm({ ...form, source_name: v })} placeholder="열수요 실적 DB" />
      </div>
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="block text-xs text-slate-500 mb-1">유형</label>
          <SelectInput value={form.source_type} onChange={(v) => setForm({ ...form, source_type: v })}
            options={[
              { value: "DB_POSTGRES", label: "PostgreSQL" },
              { value: "REST_API", label: "REST API" },
              { value: "CSV", label: "CSV" },
              { value: "FILE_CSV", label: "FILE CSV" },
            ]} />
        </div>
        <div>
          <label className="block text-xs text-slate-500 mb-1">도메인</label>
          <SelectInput value={form.data_domain} onChange={(v) => setForm({ ...form, data_domain: v })}
            options={[
              { value: "HEAT_DEMAND", label: "열수요" },
              { value: "WEATHER", label: "기상" },
              { value: "OPERATION", label: "운영" },
              { value: "CALENDAR", label: "캘린더" },
            ]} />
        </div>
      </div>
      {isCsvType(form.source_type) ? (
        <div>
          <label className="block text-xs text-slate-500 mb-1">CSV 파일 경로</label>
          <TextInput value={form.file_path} onChange={(v) => setForm({ ...form, file_path: v })} placeholder="/path/to/data.csv" />
        </div>
      ) : isApiType(form.source_type) ? (
        <>
          <div>
            <label className="block text-xs text-slate-500 mb-1">Base URL</label>
            <TextInput value={form.base_url} onChange={(v) => setForm({ ...form, base_url: v })} placeholder="http://localhost:8000/api/v1" />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs text-slate-500 mb-1">Endpoint</label>
              <TextInput value={form.endpoint} onChange={(v) => setForm({ ...form, endpoint: v })} placeholder="/sample-external/heat-demand" />
            </div>
            <div>
              <label className="block text-xs text-slate-500 mb-1">Item Path</label>
              <TextInput value={form.item_path} onChange={(v) => setForm({ ...form, item_path: v })} placeholder="data.items" />
            </div>
          </div>
        </>
      ) : (
        <>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs text-slate-500 mb-1">호스트</label>
              <TextInput value={form.host} onChange={(v) => setForm({ ...form, host: v })} placeholder="postgres" />
            </div>
            <div>
              <label className="block text-xs text-slate-500 mb-1">포트</label>
              <TextInput value={form.port} onChange={(v) => setForm({ ...form, port: v })} />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs text-slate-500 mb-1">데이터베이스</label>
              <TextInput value={form.database} onChange={(v) => setForm({ ...form, database: v })} />
            </div>
            <div>
              <label className="block text-xs text-slate-500 mb-1">스키마</label>
              <TextInput value={form.schema} onChange={(v) => setForm({ ...form, schema: v })} />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs text-slate-500 mb-1">테이블</label>
              <TextInput value={form.table} onChange={(v) => setForm({ ...form, table: v })} />
            </div>
            <div>
              <label className="block text-xs text-slate-500 mb-1">시간 컬럼</label>
              <TextInput value={form.timestamp_column} onChange={(v) => setForm({ ...form, timestamp_column: v })} />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs text-slate-500 mb-1">사용자</label>
              <TextInput value={form.username} onChange={(v) => setForm({ ...form, username: v })} />
            </div>
            <div>
              <label className="block text-xs text-slate-500 mb-1">비밀번호</label>
              <TextInput value={form.password} onChange={(v) => setForm({ ...form, password: v })} />
            </div>
          </div>
        </>
      )}
      {editTarget && (
        <div>
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={form.active_yn} onChange={(e) => setForm({ ...form, active_yn: e.target.checked })} />
            활성 상태
          </label>
        </div>
      )}
    </div>
  );

  if (loading && !items.length) return <LoadingState />;
  if (error && !items.length) return <ErrorState message={error} onRetry={() => load()} />;

  return (
    <div>
      <PageHeader
        title="데이터 소스 관리"
        description="원천 데이터 소스를 등록하고 연결 상태를 확인합니다."
        breadcrumbs={[
          { label: "데이터 관리", path: "/data/sources" },
          { label: "데이터 소스" },
        ]}
        actions={<Button icon={<Plus className="w-4 h-4" />} onClick={() => { setForm(EMPTY_FORM); setCreateOpen(true); }}>신규 등록</Button>}
      />

      <DataTable
        loading={loading}
        emptyMessage="등록된 데이터 소스가 없습니다. REST API, DB, CSV 소스를 신규 등록하세요."
        columns={[
          { key: "source_id", header: "ID", width: "120px" },
          { key: "source_name", header: "소스명" },
          { key: "source_type", header: "유형" },
          { key: "data_domain", header: "도메인" },
          { key: "active_yn", header: "상태", render: (r) => <StatusBadge status={r.active_yn ? "ACTIVE" : "INACTIVE"} /> },
          { key: "last_loaded_at", header: "최근 적재", render: (r) => r.last_loaded_at ? new Date(r.last_loaded_at as string).toLocaleString("ko-KR") : "-" },
          {
            key: "actions", header: "작업", render: (r) => {
              const row = r as unknown as DataSource;
              return (
                <div className="flex flex-wrap gap-1" onClick={(e) => e.stopPropagation()}>
                  <Button variant="ghost" icon={<Eye className="w-3 h-3" />} onClick={() => handleDetail(row)}>상세</Button>
                  <Button variant="secondary" icon={<Pencil className="w-3 h-3" />} onClick={() => openEdit(row)}>수정</Button>
                  <Button variant="secondary" icon={<Plug className="w-3 h-3" />} onClick={() => handleTest(row)}>연결 테스트</Button>
                  <Button variant="secondary" icon={<Upload className="w-3 h-3" />}
                    disabled={ingesting === row.source_id}
                    onClick={() => handleIngest(row)}>
                    {ingesting === row.source_id ? "적재 중..." : "적재 실행"}
                  </Button>
                  <Button variant="danger" icon={<Trash2 className="w-3 h-3" />} onClick={() => void openDelete(row)}>삭제</Button>
                </div>
              );
            },
          },
        ]}
        data={items as unknown as Record<string, unknown>[]}
      />
      <Pagination page={page} totalPages={totalPages} onChange={setPage} />

      <Modal open={createOpen} title="데이터 소스 등록" onClose={() => setCreateOpen(false)}
        footer={<>
          <Button variant="secondary" onClick={() => setCreateOpen(false)}>취소</Button>
          <Button onClick={handleCreate} disabled={saving}>{saving ? "저장 중..." : "저장"}</Button>
        </>}>
        {sourceFormFields}
      </Modal>

      <Modal open={!!editTarget} title="데이터 소스 수정" onClose={() => setEditTarget(null)}
        footer={<>
          <Button variant="secondary" onClick={() => setEditTarget(null)}>취소</Button>
          <Button onClick={handleUpdate} disabled={saving}>{saving ? "저장 중..." : "저장"}</Button>
        </>}>
        {sourceFormFields}
      </Modal>

      <Modal open={!!detail} title="데이터 소스 상세" onClose={() => setDetail(null)} size="lg"
        footer={<Button variant="secondary" onClick={() => setDetail(null)}>닫기</Button>}>
        {detail && (
          <dl className="grid grid-cols-2 gap-3 text-sm">
            <div><dt className="text-slate-500">ID</dt><dd className="font-medium">{detail.source_id}</dd></div>
            <div><dt className="text-slate-500">소스명</dt><dd className="font-medium">{detail.source_name}</dd></div>
            <div><dt className="text-slate-500">유형</dt><dd>{detail.source_type}</dd></div>
            <div><dt className="text-slate-500">도메인</dt><dd>{detail.data_domain}</dd></div>
            <div><dt className="text-slate-500">상태</dt><dd><StatusBadge status={detail.active_yn ? "ACTIVE" : "INACTIVE"} /></dd></div>
            <div><dt className="text-slate-500">최근 적재</dt><dd>{detail.last_loaded_at ? new Date(detail.last_loaded_at).toLocaleString("ko-KR") : "-"}</dd></div>
            <div className="col-span-2"><dt className="text-slate-500">연결 정보</dt>
              <dd className="mt-1 font-mono text-xs bg-slate-50 p-2 rounded">{JSON.stringify(detail.connection_info, null, 2)}</dd>
            </div>
          </dl>
        )}
      </Modal>

      <Modal open={!!testResult} title="연결 테스트 결과" onClose={() => setTestResult(null)}
        footer={<Button variant="secondary" onClick={() => setTestResult(null)}>닫기</Button>}>
        {testResult && (
          <dl className="space-y-3 text-sm">
            <div className="flex items-center gap-2">
              <dt className="text-slate-500 w-28">결과</dt>
              <dd><StatusBadge status={testResult.success ? "SUCCESS" : "FAILED"} /></dd>
            </div>
            <div className="flex gap-2">
              <dt className="text-slate-500 w-28">응답시간</dt>
              <dd>{testResult.latency_ms} ms</dd>
            </div>
            <div className="flex gap-2">
              <dt className="text-slate-500 w-28">샘플 데이터</dt>
              <dd>{testResult.sample_row_count.toLocaleString()} 건</dd>
            </div>
            {testResult.columns && testResult.columns.length > 0 && (
              <div>
                <dt className="text-slate-500 mb-1">컬럼 목록</dt>
                <dd className="text-xs bg-slate-50 p-2 rounded font-mono">{testResult.columns.join(", ")}</dd>
              </div>
            )}
            {testResult.error_message && (
              <div>
                <dt className="text-slate-500 mb-1">오류 메시지</dt>
                <dd className="text-red-600 bg-red-50 p-2 rounded text-xs">{testResult.error_message}</dd>
              </div>
            )}
            <div>
              <dt className="text-slate-500 mb-1">메시지</dt>
              <dd className="text-slate-700">{testResult.message}</dd>
            </div>
          </dl>
        )}
      </Modal>

      <Modal open={!!ingestTarget} title={`데이터 적재 — ${ingestTarget?.source_name ?? ""}`}
        onClose={() => { setIngestTarget(null); setSourceRange(null); }}
        footer={<>
          <Button variant="secondary" onClick={() => { setIngestTarget(null); setSourceRange(null); }}>취소</Button>
          <Button onClick={runIngest} disabled={!!ingesting || ingestBlocked}>
            {ingesting ? "적재 중..." : "적재 실행"}
          </Button>
        </>}>
        {ingestTarget && (
          <div className="space-y-3 text-sm">
            <p className="text-slate-500">
              유형: <strong>{ingestTarget.source_type}</strong> · 도메인: {ingestTarget.data_domain}
            </p>
            {isCsvIngest && (
              <div className={`rounded border p-3 text-xs ${rangeBoxClass}`}>
                {rangeLoading ? (
                  <p>CSV 데이터 기간을 조회하는 중...</p>
                ) : sourceRange?.exists ? (
                  <>
                    <p className="font-medium mb-1">사용 가능한 데이터 기간</p>
                    <p>
                      {formatDisplayDateTime(sourceRange.min_at)} ~ {formatDisplayDateTime(sourceRange.max_at)}
                      {" "}(총 {sourceRange.row_count.toLocaleString()}행 · 시각 유효 {sourceRange.valid_timestamp_count.toLocaleString()}행)
                    </p>
                    <p className="mt-1 text-slate-500">시각 컬럼: {sourceRange.timestamp_column}</p>
                  </>
                ) : (
                  <p>CSV 파일에서 시각 컬럼(measured_at)을 찾을 수 없거나 파싱할 수 없습니다. 파일 경로와 컬럼을 확인하세요.</p>
                )}
              </div>
            )}
            {(isDbType(ingestTarget.source_type) || isApiType(ingestTarget.source_type)) && (
              <p className="text-xs text-amber-700 bg-amber-50 p-2 rounded">
                DB/API 소스는 start_at/end_at으로 기간 필터를 지정할 수 있습니다. 미입력 시 전체(또는 connector 기본) 범위로 조회합니다.
              </p>
            )}
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs text-slate-500 mb-1">시작 시각 (start_at)</label>
                {isCsvIngest ? (
                  <input
                    type="datetime-local"
                    className="w-full border border-slate-300 rounded px-3 py-2 text-sm"
                    value={ingestForm.start_at}
                    onChange={(e) => setIngestForm({ ...ingestForm, start_at: e.target.value })}
                    disabled={rangeLoading || !sourceRange?.exists}
                  />
                ) : (
                  <TextInput value={ingestForm.start_at} onChange={(v) => setIngestForm({ ...ingestForm, start_at: v })}
                    placeholder="2026-05-22T00:00:00" />
                )}
              </div>
              <div>
                <label className="block text-xs text-slate-500 mb-1">종료 시각 (end_at)</label>
                {isCsvIngest ? (
                  <input
                    type="datetime-local"
                    className="w-full border border-slate-300 rounded px-3 py-2 text-sm"
                    value={ingestForm.end_at}
                    onChange={(e) => setIngestForm({ ...ingestForm, end_at: e.target.value })}
                    disabled={rangeLoading || !sourceRange?.exists}
                  />
                ) : (
                  <TextInput value={ingestForm.end_at} onChange={(v) => setIngestForm({ ...ingestForm, end_at: v })}
                    placeholder="2026-05-23T23:00:00" />
                )}
              </div>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs text-slate-500 mb-1">적재 건수 제한</label>
                <SelectInput
                  value={ingestForm.limit}
                  onChange={(v) => setIngestForm({ ...ingestForm, limit: v })}
                  options={INGESTION_LIMIT_OPTIONS.map((o) => ({ value: o.value, label: o.label }))}
                />
              </div>
              <div>
                <label className="block text-xs text-slate-500 mb-1">load_mode</label>
                <SelectInput value={ingestForm.load_mode} onChange={(v) => setIngestForm({ ...ingestForm, load_mode: v })}
                  options={[
                    { value: "UPSERT", label: "UPSERT (신규+갱신)" },
                    { value: "INSERT_ONLY", label: "INSERT_ONLY (중복 건너뜀)" },
                  ]} />
              </div>
            </div>
            {isCsvIngest ? (
              <p className="text-xs text-slate-400">
                CSV 적재는 파일 내 사용 가능한 기간 안에서만 실행됩니다. 적재 건수 제한 기본값은 무제한입니다.
              </p>
            ) : (
              <p className="text-xs text-slate-400">start_at/end_at 미입력 시 connector 기본 동작으로 실행됩니다.</p>
            )}
          </div>
        )}
      </Modal>

      <Modal open={!!deleteTarget} title="삭제 확인" onClose={() => { setDeleteTarget(null); setDeleteBlockers(null); }}
        footer={<>
          <Button variant="secondary" onClick={() => { setDeleteTarget(null); setDeleteBlockers(null); }}>취소</Button>
          <Button variant="danger" onClick={handleDelete} disabled={deleteBlockers?.can_delete === false}>삭제</Button>
        </>}>
        <p className="text-sm text-slate-600">
          <strong>{deleteTarget?.source_name}</strong> 소스를 삭제하시겠습니까? 이 작업은 되돌릴 수 없습니다.
        </p>
        {deleteBlockers && !deleteBlockers.can_delete && (
          <div className="mt-3 text-xs text-amber-800 bg-amber-50 border border-amber-200 rounded-lg p-3 space-y-1">
            <p className="font-medium">아래 연결 때문에 삭제할 수 없습니다.</p>
            {deleteBlockers.blockers.map((b) => (
              <p key={b.code}>• {b.message}</p>
            ))}
            <p className="text-slate-600 pt-1">
              <Link to="/data/mappings" className="text-blue-600 hover:underline">데이터 매핑</Link>
              {" "}화면에서 연결된 매핑을 먼저 삭제하거나, 소스를 비활성화하세요.
            </p>
          </div>
        )}
      </Modal>
    </div>
  );
}
