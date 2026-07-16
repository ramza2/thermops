import { useCallback, useEffect, useState } from "react";
import { Play, Plus, RefreshCw } from "lucide-react";
import {
  activateDataLoadSchedule,
  createDataLoadSchedule,
  deactivateDataLoadSchedule,
  listDataLoadScheduleRuns,
  listDataLoadSchedules,
  listDueDataLoadSchedules,
  previewCronExpression,
  previewNextRun,
  retryDataLoadScheduleRun,
  runDataLoadScheduleNow,
  runDueDataLoadSchedules,
  updateDataLoadSchedule,
  validateCronExpression,
} from "@/api/dataLoadSchedules";
import {
  listRunDueWorkerInstances,
  listRunDueWorkerLocks,
  listRunDueWorkerRuns,
  markStaleRunDueWorkers,
  runDueWorkerOnce,
} from "@/api/runDueWorker";
import { fetchApi } from "@/api/client";
import { Button } from "@/components/Button";
import { Column, DataTable } from "@/components/DataTable";
import { Modal } from "@/components/Modal";
import { StatusBadge } from "@/components/StatusBadge";
import { LoadingState, ErrorState } from "@/components/Pagination";
import { SelectInput, TextInput } from "@/components/SearchPanel";
import { useToast } from "@/hooks/useToast";
import { PageHeader } from "@/layouts/MainLayout";
import {
  EMPTY_MESSAGES,
  HELP_TEXTS,
  PAGE_DESCRIPTIONS,
  PAGE_TITLES,
  lifecycleStatusLabel,
} from "@/constants/displayLabels";
import type { CronPreviewResult, DataLoadSchedule, DataLoadScheduleRun } from "@/types/dataLoadSchedule";
import type { RunDueWorkerInstance, RunDueWorkerLock, RunDueWorkerRun } from "@/api/runDueWorker";
import { CRON_EXAMPLES, LOAD_WINDOW_OPTIONS, SCHEDULE_TYPE_OPTIONS } from "@/types/dataLoadSchedule";

type Tab = "schedules" | "runs" | "due" | "worker" | "help";
type ScheduleRow = DataLoadSchedule & Record<string, unknown>;
type RunRow = DataLoadScheduleRun & Record<string, unknown>;
type WorkerInstanceRow = RunDueWorkerInstance & Record<string, unknown>;
type WorkerRunRow = RunDueWorkerRun & Record<string, unknown>;

const scheduleColumns: Column<ScheduleRow>[] = [
  { key: "schedule_name", header: "일정명" },
  { key: "operation_name", header: "API 작업", render: (r) => r.operation_name || r.operation_id },
  { key: "schedule_type", header: "스케줄 유형" },
  {
    key: "cron_expression",
    header: "CRON 표현식",
    render: (r) => (r.schedule_type === "CRON" ? (r.cron_expression || "-") : "-"),
  },
  { key: "active_yn", header: "사용", render: (r) => (r.active_yn ? "사용" : "중지") },
  { key: "last_run_at", header: "마지막 실행", render: (r) => r.last_run_at?.slice(0, 19) || "-" },
  { key: "last_success_at", header: "마지막 성공 시각", render: (r) => r.last_success_at?.slice(0, 19) || "-" },
  { key: "next_run_at", header: "다음 실행 예정 시각", render: (r) => r.next_run_at?.slice(0, 19) || "-" },
  {
    key: "last_run_status",
    header: "최근 상태",
    render: (r) => <StatusBadge status={lifecycleStatusLabel(r.last_run_status)} />,
  },
];

const runColumns: Column<RunRow>[] = [
  { key: "schedule_name", header: "일정명" },
  { key: "run_source", header: "실행 출처" },
  { key: "started_at", header: "시작", render: (r) => r.started_at?.slice(0, 19) || "-" },
  { key: "finished_at", header: "종료", render: (r) => r.finished_at?.slice(0, 19) || "-" },
  { key: "run_status", header: "상태", render: (r) => <StatusBadge status={lifecycleStatusLabel(r.run_status)} /> },
  { key: "write_mode", header: "적재 방식", render: (r) => String(r.write_mode || (r.result_summary as Record<string, unknown> | undefined)?.write_mode || "-") },
  { key: "inserted_count", header: "신규" },
  { key: "updated_count", header: "갱신", render: (r) => String(r.updated_count ?? (r.result_summary as Record<string, unknown> | undefined)?.updated_count ?? 0) },
  { key: "skipped_count", header: "제외", render: (r) => String(r.skipped_count ?? (r.result_summary as Record<string, unknown> | undefined)?.skipped_count ?? 0) },
  { key: "error_message", header: "오류", render: (r) => r.error_message?.slice(0, 40) || "-" },
];

const workerInstanceColumns: Column<WorkerInstanceRow>[] = [
  { key: "worker_name", header: "Worker명" },
  { key: "worker_mode", header: "실행 모드" },
  { key: "status", header: "상태", render: (r) => <StatusBadge status={lifecycleStatusLabel(r.status)} /> },
  { key: "last_heartbeat_at", header: "Worker 상태 신호", render: (r) => r.last_heartbeat_at?.slice(0, 19) || "-" },
  { key: "last_run_status", header: "최근 실행", render: (r) => lifecycleStatusLabel(r.last_run_status) },
  { key: "consecutive_failure_count", header: "연속 실패" },
  { key: "total_run_count", header: "총 실행" },
  { key: "poll_interval_seconds", header: "실행 확인 주기(초)" },
];

const workerRunColumns: Column<WorkerRunRow>[] = [
  { key: "worker_name", header: "Worker명" },
  { key: "run_mode", header: "실행 모드" },
  { key: "started_at", header: "시작", render: (r) => r.started_at?.slice(0, 19) || "-" },
  { key: "run_status", header: "상태", render: (r) => <StatusBadge status={lifecycleStatusLabel(r.run_status)} /> },
  { key: "due_schedule_count", header: "실행 대상" },
  { key: "executed_schedule_count", header: "처리" },
  { key: "failed_schedule_count", header: "실패" },
];

const dueColumns: Column<ScheduleRow>[] = [
  { key: "schedule_name", header: "일정명" },
  { key: "schedule_type", header: "유형" },
  {
    key: "cron_expression",
    header: "CRON 표현식",
    render: (r) => (r.schedule_type === "CRON" ? (r.cron_expression || "-") : "-"),
  },
  { key: "next_run_at", header: "다음 실행 예정 시각", render: (r) => r.next_run_at?.slice(0, 19) || "-" },
];

interface ConnectorOp {
  operation_id: string;
  operation_name: string;
}

const EMPTY_FORM = {
  schedule_name: "",
  schedule_description: "",
  operation_id: "",
  schedule_type: "DAILY",
  cron_expression: "0 9 * * 1-5",
  timezone: "Asia/Seoul",
  run_policy: "LOAD_RUN",
  load_window_type: "NONE",
  window_offset_minutes: "60",
  runtime_params_template: '{\n  "bas_ymd": "{{today:YYYYMMDD}}"\n}',
  retry_enabled_yn: false,
  max_retry_count: "1",
  retry_interval_minutes: "10",
  start_at: "",
};

export default function DataLoadSchedulesPage() {
  const { showToast } = useToast();
  const [tab, setTab] = useState<Tab>("schedules");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [schedules, setSchedules] = useState<DataLoadSchedule[]>([]);
  const [runs, setRuns] = useState<DataLoadScheduleRun[]>([]);
  const [due, setDue] = useState<DataLoadSchedule[]>([]);
  const [operations, setOperations] = useState<ConnectorOp[]>([]);
  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<DataLoadSchedule | null>(null);
  const [form, setForm] = useState(EMPTY_FORM);
  const [nextPreview, setNextPreview] = useState<string>("");
  const [cronPreview, setCronPreview] = useState<CronPreviewResult | null>(null);
  const [runDueResult, setRunDueResult] = useState<Record<string, unknown> | null>(null);
  const [runningId, setRunningId] = useState<string | null>(null);
  const [workerInstances, setWorkerInstances] = useState<RunDueWorkerInstance[]>([]);
  const [workerRuns, setWorkerRuns] = useState<RunDueWorkerRun[]>([]);
  const [workerLocks, setWorkerLocks] = useState<RunDueWorkerLock[]>([]);
  const [workerLoading, setWorkerLoading] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [schedRes, runRes, dueRes, opsRes] = await Promise.all([
        listDataLoadSchedules(),
        listDataLoadScheduleRuns(),
        listDueDataLoadSchedules(),
        fetchApi<ConnectorOp[]>("/api-connectors/operations").catch(() => []),
      ]);
      setSchedules(schedRes);
      setRuns(runRes);
      setDue(dueRes);
      setOperations(opsRes);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "조회 실패");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const loadWorker = useCallback(async () => {
    setWorkerLoading(true);
    try {
      const [instRes, runRes, lockRes] = await Promise.all([
        listRunDueWorkerInstances(),
        listRunDueWorkerRuns(30),
        listRunDueWorkerLocks(),
      ]);
      setWorkerInstances(instRes);
      setWorkerRuns(runRes);
      setWorkerLocks(lockRes);
    } catch (e: unknown) {
      showToast("error", e instanceof Error ? e.message : "Worker 상태 조회 실패");
    } finally {
      setWorkerLoading(false);
    }
  }, [showToast]);

  useEffect(() => {
    if (tab === "worker") void loadWorker();
  }, [tab, loadWorker]);

  const openCreate = () => {
    setEditing(null);
    setForm(EMPTY_FORM);
    setNextPreview("");
    setCronPreview(null);
    setModalOpen(true);
  };

  const openEdit = (row: DataLoadSchedule) => {
    setEditing(row);
    setForm({
      schedule_name: row.schedule_name,
      schedule_description: row.schedule_description || "",
      operation_id: row.operation_id,
      schedule_type: row.schedule_type,
      cron_expression: row.cron_expression || "0 9 * * 1-5",
      timezone: row.timezone || "Asia/Seoul",
      run_policy: row.run_policy,
      load_window_type: row.load_window_type,
      window_offset_minutes: String(row.window_offset_minutes ?? 60),
      runtime_params_template: JSON.stringify(row.runtime_params_template || {}, null, 2),
      retry_enabled_yn: row.retry_enabled_yn,
      max_retry_count: String(row.max_retry_count ?? 0),
      retry_interval_minutes: String(row.retry_interval_minutes ?? 10),
      start_at: row.start_at ? row.start_at.slice(0, 16) : "",
    });
    setNextPreview(row.next_run_at || "");
    setCronPreview(null);
    setModalOpen(true);
  };

  const parseTemplate = () => {
    try {
      return JSON.parse(form.runtime_params_template || "{}") as Record<string, unknown>;
    } catch {
      throw new Error("실행 파라미터 템플릿 JSON 형식이 올바르지 않습니다.");
    }
  };

  const handleSave = async () => {
    if (!form.schedule_name || !form.operation_id) {
      showToast("warning", "일정명과 API 작업을 입력하세요.");
      return;
    }
    try {
      const body: Record<string, unknown> = {
        schedule_name: form.schedule_name,
        schedule_description: form.schedule_description || null,
        operation_id: form.operation_id,
        schedule_type: form.schedule_type,
        cron_expression: form.schedule_type === "CRON" ? form.cron_expression : null,
        timezone: form.timezone || "Asia/Seoul",
        run_policy: form.run_policy,
        load_window_type: form.load_window_type,
        window_offset_minutes: form.window_offset_minutes ? Number(form.window_offset_minutes) : null,
        runtime_params_template: parseTemplate(),
        retry_enabled_yn: form.retry_enabled_yn,
        max_retry_count: Number(form.max_retry_count || 0),
        retry_interval_minutes: Number(form.retry_interval_minutes || 10),
        start_at: form.start_at ? new Date(form.start_at).toISOString() : null,
      };
      if (editing) {
        await updateDataLoadSchedule(editing.schedule_id, body);
        showToast("success", "적재 일정이 수정되었습니다.");
      } else {
        await createDataLoadSchedule(body);
        showToast("success", "적재 일정이 등록되었습니다.");
      }
      setModalOpen(false);
      await load();
    } catch (e: unknown) {
      showToast("error", e instanceof Error ? e.message : "저장 실패");
    }
  };

  const handlePreviewNext = async () => {
    try {
      const res = await previewNextRun({
        schedule_type: form.schedule_type,
        cron_expression: form.schedule_type === "CRON" ? form.cron_expression : null,
        timezone: form.timezone || "Asia/Seoul",
        start_at: form.start_at ? new Date(form.start_at).toISOString() : null,
        count: 10,
      }) as CronPreviewResult & { next_run_at?: string; next_runs?: string[] };
      setNextPreview(res.next_run_at || "-");
      if (form.schedule_type === "CRON") {
        setCronPreview(res);
      }
    } catch (e: unknown) {
      showToast("error", e instanceof Error ? e.message : "미리보기 실패");
    }
  };

  const handleValidateCron = async () => {
    try {
      const res = await validateCronExpression({
        cron_expression: form.cron_expression,
        timezone: form.timezone || "Asia/Seoul",
        count: 10,
      }) as CronPreviewResult;
      setCronPreview(res);
      if (res.valid) {
        showToast("success", "CRON 표현식이 유효합니다.");
        setNextPreview(res.next_runs?.[0] || res.next_run_at || "");
      } else {
        showToast("error", (res.errors || []).join(" ") || "CRON 표현식이 올바르지 않습니다.");
      }
    } catch (e: unknown) {
      showToast("error", e instanceof Error ? e.message : "CRON 검증 실패");
    }
  };

  const handlePreviewCron = async () => {
    try {
      const res = await previewCronExpression({
        cron_expression: form.cron_expression,
        timezone: form.timezone || "Asia/Seoul",
        count: 10,
      }) as CronPreviewResult;
      setCronPreview(res);
      if (!res.valid) {
        showToast("error", (res.errors || []).join(" ") || "CRON 미리보기 실패");
        return;
      }
      setNextPreview(res.next_runs?.[0] || "");
      showToast("success", "다음 실행 예정 미리보기를 갱신했습니다.");
    } catch (e: unknown) {
      showToast("error", e instanceof Error ? e.message : "CRON 미리보기 실패");
    }
  };

  const handleRunNow = async (scheduleId: string) => {
    setRunningId(scheduleId);
    try {
      await runDataLoadScheduleNow(scheduleId);
      showToast("success", "수동 적재 실행이 완료되었습니다.");
      await load();
    } catch (e: unknown) {
      showToast("error", e instanceof Error ? e.message : "실행 실패");
    } finally {
      setRunningId(null);
    }
  };

  const handleRunDue = async () => {
    try {
      const res = await runDueDataLoadSchedules();
      setRunDueResult(res);
      showToast("success", "run-due 실행이 완료되었습니다.");
      await load();
    } catch (e: unknown) {
      showToast("error", e instanceof Error ? e.message : "run-due 실패");
    }
  };

  const handleWorkerOnce = async () => {
    try {
      await runDueWorkerOnce();
      showToast("success", "Worker 1회 실행이 완료되었습니다.");
      await loadWorker();
    } catch (e: unknown) {
      showToast("error", e instanceof Error ? e.message : "1회 실행 실패");
    }
  };

  const handleMarkStale = async () => {
    try {
      const marked = await markStaleRunDueWorkers();
      showToast("success", `STALE 처리 ${marked.length}건`);
      await loadWorker();
    } catch (e: unknown) {
      showToast("error", e instanceof Error ? e.message : "STALE 처리 실패");
    }
  };

  const handleRetry = async (runId: string) => {
    try {
      await retryDataLoadScheduleRun(runId);
      showToast("success", "재시도가 완료되었습니다.");
      await load();
    } catch (e: unknown) {
      showToast("error", e instanceof Error ? e.message : "재시도 실패");
    }
  };

  if (loading) return <LoadingState />;
  if (error) return <ErrorState message={error} onRetry={() => void load()} />;

  return (
    <div>
      <PageHeader title={PAGE_TITLES.dataLoadSchedules} description={PAGE_DESCRIPTIONS.dataLoadSchedules} />
      <p className="text-xs text-slate-600 bg-slate-50 border border-slate-100 rounded p-2 mb-4">
        {HELP_TEXTS.dataLoadSchedulerIntro}
      </p>

      <div className="flex flex-wrap gap-2 mb-4">
        {[
          ["schedules", "일정 목록"],
          ["runs", "실행 이력"],
          ["due", "실행 대상 일정"],
          ["worker", "Worker 상태"],
          ["help", "도움말"],
        ].map(([id, label]) => (
          <button
            key={id}
            type="button"
            onClick={() => setTab(id as Tab)}
            className={`px-3 py-1.5 text-sm rounded border ${tab === id ? "bg-blue-50 border-blue-200 text-blue-700" : "bg-white text-slate-600"}`}
          >
            {label}
          </button>
        ))}
        {tab === "schedules" && (
          <Button icon={<Plus className="w-4 h-4" />} onClick={openCreate}>일정 등록</Button>
        )}
        {tab === "due" && (
          <Button icon={<RefreshCw className="w-4 h-4" />} onClick={handleRunDue}>run-due 실행</Button>
        )}
        {tab === "worker" && (
          <>
            <Button icon={<Play className="w-4 h-4" />} onClick={() => void handleWorkerOnce()}>1회 실행</Button>
            <Button variant="secondary" icon={<RefreshCw className="w-4 h-4" />} onClick={() => void loadWorker()}>새로고침</Button>
            <Button variant="secondary" onClick={() => void handleMarkStale()}>STALE 표시</Button>
          </>
        )}
      </div>

      {tab === "schedules" && (
        schedules.length === 0 ? (
          <div className="text-center py-12 text-slate-500 bg-slate-50 rounded border border-dashed text-sm">
            {EMPTY_MESSAGES.dataLoadSchedules}
          </div>
        ) : (
          <DataTable
            columns={[
              ...scheduleColumns,
              {
                key: "actions",
                header: "액션",
                render: (r) => (
                  <div className="flex gap-1">
                    <Button variant="secondary" icon={<Play className="w-3 h-3" />} disabled={runningId === r.schedule_id}
                      onClick={() => void handleRunNow(r.schedule_id)}>실행</Button>
                    <Button variant="secondary" onClick={() => openEdit(r)}>수정</Button>
                    <Button variant="secondary" onClick={() => void (r.active_yn ? deactivateDataLoadSchedule(r.schedule_id) : activateDataLoadSchedule(r.schedule_id)).then(load)}>
                      {r.active_yn ? "비활성화" : "활성화"}
                    </Button>
                  </div>
                ),
              },
            ]}
            data={schedules as ScheduleRow[]}
          />
        )
      )}

      {tab === "runs" && (
        runs.length === 0 ? (
          <div className="text-center py-12 text-slate-500 bg-slate-50 rounded border border-dashed text-sm">
            실행 이력이 없습니다.
          </div>
        ) : (
          <DataTable
            columns={[
              ...runColumns,
              {
                key: "retry",
                header: "재시도",
                render: (r) => r.run_status === "FAILED" ? (
                  <Button variant="secondary" onClick={() => void handleRetry(r.schedule_run_id)}>재시도</Button>
                ) : "-",
              },
            ]}
            data={runs as RunRow[]}
          />
        )
      )}

      {tab === "due" && (
        <div className="space-y-4">
          <p className="text-sm text-slate-600">현재 시각 기준 실행 대상 일정(due) {due.length}건</p>
          {runDueResult && (
            <pre className="text-xs bg-slate-50 border rounded p-3 overflow-auto">{JSON.stringify(runDueResult, null, 2)}</pre>
          )}
          {due.length === 0 ? (
            <div className="text-center py-8 text-slate-500 border border-dashed rounded">실행 대상 일정이 없습니다.</div>
          ) : (
            <DataTable columns={dueColumns} data={due as ScheduleRow[]} />
          )}
        </div>
      )}

      {tab === "worker" && (
        <div className="space-y-6">
          <p className="text-sm text-slate-600">
            적재 일정 실행 Worker는 run-due를 주기적으로 호출합니다. CRON 일정도 실행 대상 일정(due) 건수에 포함됩니다.
            중복 실행 방지 잠금: {workerLocks.length ? workerLocks.map((l) => `${l.lock_key} → ${l.owner_instance_id}`).join(", ") : "없음"}
          </p>
          {workerLoading ? <LoadingState /> : (
            <>
              <div>
                <h3 className="text-sm font-medium text-slate-700 mb-2">적재 일정 실행 Worker</h3>
                {workerInstances.length === 0 ? (
                  <div className="text-center py-8 text-slate-500 border border-dashed rounded text-sm">{EMPTY_MESSAGES.runDueWorkerInstances}</div>
                ) : (
                  <DataTable columns={workerInstanceColumns} data={workerInstances as WorkerInstanceRow[]} />
                )}
              </div>
              <div>
                <h3 className="text-sm font-medium text-slate-700 mb-2">최근 Worker 실행 이력</h3>
                {workerRuns.length === 0 ? (
                  <div className="text-center py-8 text-slate-500 border border-dashed rounded text-sm">{EMPTY_MESSAGES.runDueWorkerRuns}</div>
                ) : (
                  <DataTable columns={workerRunColumns} data={workerRuns as WorkerRunRow[]} />
                )}
              </div>
            </>
          )}
        </div>
      )}

      {tab === "help" && (
        <div className="text-sm text-slate-700 space-y-2 bg-slate-50 border rounded p-4">
          <p>{HELP_TEXTS.dataLoadSchedulerHelp1}</p>
          <p>{HELP_TEXTS.dataLoadSchedulerHelp2}</p>
          <p>{HELP_TEXTS.dataLoadSchedulerHelp3}</p>
          <p>{HELP_TEXTS.dataLoadCronHelp1}</p>
          <p>{HELP_TEXTS.dataLoadCronHelp2}</p>
          <p>{HELP_TEXTS.dataLoadCronHelp3}</p>
          <p>{HELP_TEXTS.runDueWorkerHelp1}</p>
          <p>{HELP_TEXTS.runDueWorkerHelp2}</p>
          <p>{HELP_TEXTS.runDueWorkerHelp3}</p>
          <p>{HELP_TEXTS.runDueWorkerHelp4}</p>
          <p>{HELP_TEXTS.runDueWorkerHelp5}</p>
          <p>재실행 시 동일 키 데이터는 적재 방식(신규 행 추가/중복 제외/있으면 갱신, 없으면 추가)에 따라 신규 건수가 0이 될 수 있습니다.</p>
          <p>재시도 정책: 일정별 retry_enabled_yn, max_retry_count, retry_interval_minutes 설정</p>
          <p>실행 파라미터 템플릿 예: {`{"bas_ymd": "{{today:YYYYMMDD}}"}`}</p>
        </div>
      )}

      <Modal open={modalOpen} title={editing ? "적재 일정 수정" : "적재 일정 등록"} onClose={() => setModalOpen(false)}
        footer={<>
          <Button variant="secondary" onClick={() => setModalOpen(false)}>취소</Button>
          <Button onClick={handleSave}>저장</Button>
        </>}>
        <div className="space-y-3 text-sm">
          <div><label className="text-xs text-slate-500">일정명</label><TextInput value={form.schedule_name} onChange={(v) => setForm({ ...form, schedule_name: v })} /></div>
          <div><label className="text-xs text-slate-500">API 작업</label>
            <SelectInput value={form.operation_id} onChange={(v) => setForm({ ...form, operation_id: v })}
              options={[{ value: "", label: "선택" }, ...operations.map((o) => ({ value: o.operation_id, label: o.operation_name }))]} />
          </div>
          <div><label className="text-xs text-slate-500">스케줄 유형</label>
            <SelectInput value={form.schedule_type} onChange={(v) => setForm({ ...form, schedule_type: v })} options={SCHEDULE_TYPE_OPTIONS} />
          </div>
          {form.schedule_type === "CRON" && (
            <div className="space-y-2 border rounded p-3 bg-slate-50">
              <div>
                <label className="text-xs text-slate-500">CRON 표현식</label>
                <TextInput value={form.cron_expression} onChange={(v) => setForm({ ...form, cron_expression: v })} />
              </div>
              <div>
                <label className="text-xs text-slate-500">시간대</label>
                <TextInput value={form.timezone} onChange={(v) => setForm({ ...form, timezone: v })} />
              </div>
              <div className="flex flex-wrap gap-2">
                {CRON_EXAMPLES.map((ex) => (
                  <Button key={ex.expression} variant="secondary" onClick={() => setForm({ ...form, cron_expression: ex.expression })}>
                    {ex.label}
                  </Button>
                ))}
              </div>
              <div className="text-xs text-slate-600 space-y-1">
                <p>THERMOps는 5-field CRON 표현식을 지원합니다.</p>
                <p>형식: 분 시 일 월 요일</p>
                <p>0 또는 7은 일요일로 처리됩니다.</p>
                <p>?, L, W, # 같은 Quartz 문법은 현재 지원하지 않습니다.</p>
                <p>CRON 일정도 run-due Worker가 다음 실행 예정 시각에 맞춰 자동 실행합니다.</p>
                <p>Worker 중단으로 놓친 여러 실행 시각을 한 번에 catch-up 하지는 않습니다.</p>
              </div>
              <div className="flex flex-wrap gap-2">
                <Button variant="secondary" onClick={() => void handleValidateCron()}>CRON 검증</Button>
                <Button variant="secondary" onClick={() => void handlePreviewCron()}>다음 실행 예정 미리보기</Button>
              </div>
              {cronPreview && (
                <div className="text-xs space-y-1">
                  {cronPreview.explanation && <p>{cronPreview.explanation}</p>}
                  {cronPreview.next_runs && cronPreview.next_runs.length > 0 && (
                    <ul className="list-disc pl-4">
                      {cronPreview.next_runs.slice(0, 10).map((t) => (
                        <li key={t}>{t.slice(0, 19)}</li>
                      ))}
                    </ul>
                  )}
                  {(cronPreview.errors || []).map((err) => (
                    <p key={err} className="text-red-600">{err}</p>
                  ))}
                </div>
              )}
            </div>
          )}
          <div><label className="text-xs text-slate-500">적재 기간(load window)</label>
            <SelectInput value={form.load_window_type} onChange={(v) => setForm({ ...form, load_window_type: v })} options={LOAD_WINDOW_OPTIONS} />
          </div>
          <div><label className="text-xs text-slate-500">실행 파라미터 템플릿 (JSON)</label>
            <textarea className="w-full border rounded p-2 font-mono text-xs h-28" value={form.runtime_params_template}
              onChange={(e) => setForm({ ...form, runtime_params_template: e.target.value })} />
          </div>
          <label className="flex items-center gap-2 text-xs">
            <input type="checkbox" checked={form.retry_enabled_yn} onChange={(e) => setForm({ ...form, retry_enabled_yn: e.target.checked })} />
            재시도 정책 사용
          </label>
          <div className="flex gap-2 items-end">
            <Button variant="secondary" onClick={() => void handlePreviewNext()}>다음 실행 예정 시각 미리보기</Button>
            {nextPreview && <span className="text-xs text-slate-600">다음 실행 예정: {nextPreview}</span>}
          </div>
        </div>
      </Modal>
    </div>
  );
}
