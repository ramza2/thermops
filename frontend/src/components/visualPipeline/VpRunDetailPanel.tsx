import { useEffect, useState } from "react";
import { extractApiErrorMessage } from "@/api/client";
import {
  cancelVisualPipelineRun,
  getVisualPipelineRunProgress,
  listVisualPipelineRunEvents,
  retryVisualPipelineRun,
} from "@/api/visualPipelines";
import type {
  VisualPipelineRunEvent,
  VisualPipelineRunProgress,
  VisualPipelineRunResponse,
} from "@/types/visualPipeline";

interface VpRunDetailPanelProps {
  detail: VisualPipelineRunResponse | null;
  loading?: boolean;
  error?: string | null;
  onClose: () => void;
  testIdPrefix?: string;
  /** Called after a retry run is successfully enqueued. */
  onRetrySuccess?: (retryVisualRunId: string) => void;
  /** Called after soft-cancel request or PENDING cancel succeeds. */
  onCancelSuccess?: () => void;
}

function Field({ label, value }: { label: string; value?: string | number | null }) {
  return (
    <div className="min-w-0">
      <div className="text-[10px] text-slate-400">{label}</div>
      <div className="font-mono text-[11px] text-slate-700 break-all">{value ?? "-"}</div>
    </div>
  );
}

function modeLabel(mode?: string | null): string {
  if (mode === "SCHEDULED") return "스케줄 실행";
  if (mode === "MANUAL") return "즉시 실행";
  return mode ?? "-";
}

function eventTypeLabel(eventType: string): string {
  const map: Record<string, string> = {
    RUN_CREATED: "실행 생성",
    WORKER_CLAIMED: "Worker claim",
    RUN_STARTED: "실행 시작",
    STEP_STARTED: "단계 시작",
    STEP_COMPLETED: "단계 완료",
    LOAD_FINALIZE: "적재 마무리",
    RUN_COMPLETED: "실행 완료",
    RUN_FAILED: "실행 실패",
    RUN_CANCELLED: "실행 취소",
    RUN_CANCEL_REQUESTED: "중단 요청",
    RUN_RETRY_REQUESTED: "재시도 요청",
  };
  return map[eventType] ?? eventType;
}

function stepStatusTone(status: string): string {
  if (status === "completed") return "bg-emerald-50 text-emerald-700 border-emerald-200";
  if (status === "running") return "bg-sky-50 text-sky-700 border-sky-200";
  return "bg-slate-50 text-slate-500 border-slate-200";
}

function canRetryStatus(status?: string | null): boolean {
  const s = String(status || "").toUpperCase();
  return s === "FAILED" || s === "PARTIAL";
}

function canSoftCancelStatus(status?: string | null): boolean {
  return String(status || "").toUpperCase() === "RUNNING";
}

function cancelErrorMessage(codeOrMsg: string): string {
  const code = codeOrMsg.trim();
  if (code.includes("RUN_CANCEL_NOT_ALLOWED_STATUS") || code === "RUN_CANCEL_NOT_ALLOWED_STATUS") {
    return "현재 상태에서는 중단 요청을 할 수 없습니다.";
  }
  if (code.includes("RUN_CANCEL_CONFIRM_MISMATCH") || code === "RUN_CANCEL_CONFIRM_MISMATCH") {
    return "confirm_visual_run_id가 일치하지 않습니다.";
  }
  if (code.includes("RUN_CANCEL_REASON_REQUIRED") || code === "RUN_CANCEL_REASON_REQUIRED") {
    return "사유는 5자 이상 입력해야 합니다.";
  }
  if (code.includes("RUN_CANCEL_AUDIT_REQUIRED_FAILED") || code === "RUN_CANCEL_AUDIT_REQUIRED_FAILED") {
    return "Audit 기록 실패로 중단 요청을 접수하지 못했습니다.";
  }
  return codeOrMsg || "중단 요청에 실패했습니다.";
}

function retryErrorMessage(codeOrMsg: string): string {
  const code = codeOrMsg.trim();
  if (code.includes("RUN_RETRY_ACTIVE_RUN_EXISTS") || code === "RUN_RETRY_ACTIVE_RUN_EXISTS") {
    return "이 파이프라인에 실행 중이거나 대기 중인 Run이 있어 재시도할 수 없습니다.";
  }
  if (code.includes("RUN_RETRY_NOT_ALLOWED_STATUS") || code === "RUN_RETRY_NOT_ALLOWED_STATUS") {
    return "현재 상태에서는 재시도할 수 없습니다.";
  }
  if (code.includes("RUN_RETRY_MAX_ATTEMPT_EXCEEDED") || code === "RUN_RETRY_MAX_ATTEMPT_EXCEEDED") {
    return "최대 재시도 횟수를 초과했습니다.";
  }
  if (code.includes("RUN_RETRY_AUDIT_REQUIRED_FAILED") || code === "RUN_RETRY_AUDIT_REQUIRED_FAILED") {
    return "Audit 기록 실패로 재시도 Run을 생성하지 못했습니다.";
  }
  if (code.includes("RUN_RETRY_CONFIRM_MISMATCH") || code === "RUN_RETRY_CONFIRM_MISMATCH") {
    return "confirm_visual_run_id가 일치하지 않습니다.";
  }
  if (code.includes("RUN_RETRY_REASON_REQUIRED") || code === "RUN_RETRY_REASON_REQUIRED") {
    return "사유는 5자 이상 입력해야 합니다.";
  }
  return codeOrMsg || "재시도 요청에 실패했습니다.";
}

export function VpRunDetailPanel({
  detail,
  loading,
  error,
  onClose,
  testIdPrefix = "visual-pipeline-run-detail",
  onRetrySuccess,
  onCancelSuccess,
}: VpRunDetailPanelProps) {
  const [progress, setProgress] = useState<VisualPipelineRunProgress | null>(null);
  const [events, setEvents] = useState<VisualPipelineRunEvent[]>([]);
  const [progressLoading, setProgressLoading] = useState(false);
  const [progressError, setProgressError] = useState<string | null>(null);

  const [retryOpen, setRetryOpen] = useState(false);
  const [confirmRunId, setConfirmRunId] = useState("");
  const [retryReason, setRetryReason] = useState("");
  const [retrySubmitting, setRetrySubmitting] = useState(false);
  const [retryError, setRetryError] = useState<string | null>(null);
  const [retrySuccess, setRetrySuccess] = useState<string | null>(null);

  const [cancelOpen, setCancelOpen] = useState(false);
  const [cancelConfirmRunId, setCancelConfirmRunId] = useState("");
  const [cancelReason, setCancelReason] = useState("");
  const [cancelSubmitting, setCancelSubmitting] = useState(false);
  const [cancelError, setCancelError] = useState<string | null>(null);
  const [cancelSuccess, setCancelSuccess] = useState<string | null>(null);

  useEffect(() => {
    if (!detail?.pipeline_id || !detail.visual_run_id) {
      setProgress(null);
      setEvents([]);
      setProgressError(null);
      return;
    }
    let cancelled = false;
    setProgressLoading(true);
    setProgressError(null);
    void Promise.all([
      getVisualPipelineRunProgress(detail.pipeline_id, detail.visual_run_id),
      listVisualPipelineRunEvents(detail.pipeline_id, detail.visual_run_id, { limit: 50 }),
    ])
      .then(([progressRes, eventsRes]) => {
        if (cancelled) return;
        setProgress(progressRes);
        setEvents(eventsRes.items ?? []);
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        setProgress(null);
        setEvents([]);
        setProgressError(err instanceof Error ? err.message : "진행 상태를 불러오지 못했습니다.");
      })
      .finally(() => {
        if (!cancelled) setProgressLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [detail?.pipeline_id, detail?.visual_run_id]);

  useEffect(() => {
    setRetryOpen(false);
    setConfirmRunId("");
    setRetryReason("");
    setRetryError(null);
    setRetrySuccess(null);
    setCancelOpen(false);
    setCancelConfirmRunId("");
    setCancelReason("");
    setCancelError(null);
    setCancelSuccess(null);
  }, [detail?.visual_run_id]);

  const progressPercent =
    progress?.progress_percent != null ? Math.max(0, Math.min(100, progress.progress_percent)) : null;

  const retryable = canRetryStatus(detail?.run_status);
  const canConfirmRetry =
    !!detail &&
    confirmRunId.trim() === detail.visual_run_id &&
    retryReason.trim().length >= 5 &&
    !retrySubmitting;

  const softCancelable = canSoftCancelStatus(detail?.run_status);
  const cancelAlreadyRequested = Boolean(
    detail?.cancel_requested_at || progress?.cancel_requested_at || detail?.cancel_requested,
  );
  const canConfirmCancel =
    !!detail &&
    cancelConfirmRunId.trim() === detail.visual_run_id &&
    cancelReason.trim().length >= 5 &&
    !cancelSubmitting;

  const openRetry = () => {
    setRetryOpen(true);
    setConfirmRunId("");
    setRetryReason("");
    setRetryError(null);
  };

  const closeRetry = () => {
    if (retrySubmitting) return;
    setRetryOpen(false);
    setConfirmRunId("");
    setRetryReason("");
    setRetryError(null);
  };

  const submitRetry = async () => {
    if (!detail || !canConfirmRetry) return;
    setRetrySubmitting(true);
    setRetryError(null);
    try {
      const result = await retryVisualPipelineRun(detail.pipeline_id, detail.visual_run_id, {
        reason: retryReason.trim(),
        confirm_visual_run_id: confirmRunId.trim(),
        retry_mode: "SAME_SNAPSHOT",
      });
      setRetryOpen(false);
      setRetrySuccess(
        `재시도 Run이 생성되었습니다. (${result.retry_visual_run_id}) 실행 이력에서 진행 상태를 확인할 수 있습니다.`,
      );
      onRetrySuccess?.(result.retry_visual_run_id);
    } catch (err) {
      const raw = extractApiErrorMessage(err, "재시도 요청에 실패했습니다.");
      setRetryError(retryErrorMessage(raw));
    } finally {
      setRetrySubmitting(false);
    }
  };

  const openCancel = () => {
    setCancelOpen(true);
    setCancelConfirmRunId("");
    setCancelReason("");
    setCancelError(null);
  };

  const closeCancel = () => {
    if (cancelSubmitting) return;
    setCancelOpen(false);
    setCancelConfirmRunId("");
    setCancelReason("");
    setCancelError(null);
  };

  const submitCancel = async () => {
    if (!detail || !canConfirmCancel) return;
    setCancelSubmitting(true);
    setCancelError(null);
    try {
      const result = await cancelVisualPipelineRun(detail.pipeline_id, detail.visual_run_id, {
        reason: cancelReason.trim(),
        confirm_visual_run_id: cancelConfirmRunId.trim(),
      });
      setCancelOpen(false);
      setCancelSuccess(
        result.message ||
          "중단 요청이 접수되었습니다. 현재 단계가 끝난 뒤 중단됩니다.",
      );
      onCancelSuccess?.();
    } catch (err) {
      const raw = extractApiErrorMessage(err, "중단 요청에 실패했습니다.");
      setCancelError(cancelErrorMessage(raw));
    } finally {
      setCancelSubmitting(false);
    }
  };

  return (
    <div
      className="rounded-md border border-slate-200 bg-white shadow-sm overflow-hidden"
      data-testid={`${testIdPrefix}-panel`}
    >
      <div className="flex items-center justify-between px-3 py-2 border-b border-slate-100 bg-slate-50">
        <span className="text-xs font-bold text-slate-700">Run 상세</span>
        <button
          type="button"
          className="text-[11px] text-slate-500 hover:text-slate-800"
          onClick={onClose}
          data-testid={`${testIdPrefix}-close`}
        >
          닫기
        </button>
      </div>
      <div className="px-3 py-3 space-y-3">
        {loading && <p className="text-xs text-slate-500">Run 상세를 불러오는 중입니다.</p>}
        {error && (
          <p className="text-xs text-red-600 bg-red-50 border border-red-100 rounded-md px-2.5 py-2">{error}</p>
        )}
        {!loading && !error && !detail && (
          <p className="text-xs text-slate-500">Run 상세 정보를 찾을 수 없습니다. 목록을 새로고침해 주세요.</p>
        )}
        {detail && (
          <>
            <section className="grid grid-cols-1 sm:grid-cols-2 gap-2">
              <Field label="Run ID" value={detail.visual_run_id} />
              <Field label="상태" value={detail.run_status} />
              <Field label="실행 방식" value={modeLabel(detail.mode)} />
              <Field label="execution_mode" value={detail.execution_mode} />
            </section>

            <section
              className="rounded-md border border-slate-100 bg-slate-50 px-2.5 py-2 space-y-2"
              data-testid={`${testIdPrefix}-progress-section`}
            >
              <div className="flex items-center justify-between gap-2">
                <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wide">진행 상태</span>
                {progressPercent != null && (
                  <span className="text-[10px] font-mono text-slate-600">{progressPercent}%</span>
                )}
              </div>
              {progressLoading && <p className="text-[11px] text-slate-500">진행 상태를 불러오는 중입니다.</p>}
              {progressError && (
                <p className="text-[11px] text-amber-700 bg-amber-50 border border-amber-100 rounded px-2 py-1">
                  {progressError}
                </p>
              )}
              {!progressLoading && !progressError && progress && (
                <>
                  {progressPercent != null && (
                    <div className="h-1.5 rounded-full bg-slate-200 overflow-hidden">
                      <div
                        className="h-full bg-violet-500 transition-all"
                        style={{ width: `${progressPercent}%` }}
                        data-testid={`${testIdPrefix}-progress-bar`}
                      />
                    </div>
                  )}
                  <div className="text-[11px] text-slate-600">
                    현재 단계: {progress.current_step_name ?? progress.current_step_key ?? "-"}
                  </div>
                  <div className="flex flex-wrap gap-1.5">
                    {(progress.steps ?? []).map((step) => (
                      <span
                        key={step.step_key}
                        className={`inline-flex text-[10px] border rounded px-1.5 py-0.5 ${stepStatusTone(step.status)}`}
                        data-testid={`${testIdPrefix}-step-${step.step_key}`}
                      >
                        {step.step_name ?? step.step_key}: {step.status}
                      </span>
                    ))}
                  </div>
                </>
              )}
            </section>

            <section
              className="rounded-md border border-slate-100 bg-white px-2.5 py-2 space-y-1.5"
              data-testid={`${testIdPrefix}-timeline-section`}
            >
              <div className="text-[10px] font-bold text-slate-500 uppercase tracking-wide">단계별 진행 이력</div>
              {progressLoading && <p className="text-[11px] text-slate-500">이력을 불러오는 중입니다.</p>}
              {!progressLoading && events.length === 0 && (
                <p className="text-[11px] text-slate-500">기록된 진행 이벤트가 없습니다.</p>
              )}
              {events.length > 0 && (
                <ul className="space-y-1 max-h-40 overflow-y-auto">
                  {events.map((ev) => (
                    <li
                      key={ev.event_id}
                      className="text-[10px] font-mono text-slate-600 border-b border-slate-50 pb-1"
                      data-testid={`${testIdPrefix}-event-row`}
                    >
                      <span className="text-slate-400">{ev.created_at ?? "-"}</span>
                      {" · "}
                      <span className="font-semibold">{eventTypeLabel(ev.event_type)}</span>
                      {ev.step_name ? ` · ${ev.step_name}` : ev.step_key ? ` · ${ev.step_key}` : ""}
                      {ev.progress_percent != null ? ` · ${ev.progress_percent}%` : ""}
                    </li>
                  ))}
                </ul>
              )}
            </section>

            <section
              className="rounded-md border border-violet-100 bg-violet-50/40 px-2.5 py-2 space-y-2"
              data-testid={`${testIdPrefix}-retry-section`}
            >
              <div className="text-[10px] font-bold text-violet-700 uppercase tracking-wide">재시도</div>
              {(detail.retry_of_run_id || (detail.retry_attempt ?? 0) > 0) && (
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                  <Field label="원본 Run ID" value={detail.retry_of_run_id} />
                  <Field label="Retry attempt" value={detail.retry_attempt} />
                  <Field label="Retry mode" value={detail.retry_mode} />
                  <Field label="Retry reason" value={detail.retry_reason} />
                </div>
              )}
              {retrySuccess && (
                <p
                  className="text-[11px] text-emerald-800 bg-emerald-50 border border-emerald-100 rounded px-2 py-1"
                  data-testid={`${testIdPrefix}-retry-success`}
                >
                  {retrySuccess}
                </p>
              )}
              {retryable ? (
                <button
                  type="button"
                  className="text-[11px] font-medium text-violet-800 border border-violet-200 bg-white rounded px-2.5 py-1 hover:bg-violet-50"
                  onClick={openRetry}
                  data-testid={`${testIdPrefix}-retry-button`}
                >
                  재시도
                </button>
              ) : (
                <p className="text-[11px] text-slate-500" data-testid={`${testIdPrefix}-retry-unavailable`}>
                  현재 상태({detail.run_status})에서는 재시도할 수 없습니다. FAILED / PARTIAL만 가능합니다.
                </p>
              )}
            </section>

            {retryOpen && (
              <div
                className="rounded-md border border-violet-200 bg-white px-2.5 py-2 space-y-2"
                data-testid={`${testIdPrefix}-retry-dialog`}
              >
                <div className="text-xs font-bold text-slate-700">Run 재시도</div>
                <p className="text-[11px] text-slate-600 whitespace-pre-line">
                  {`선택한 Run을 새 Run으로 재시도합니다.
원본 Run은 변경하지 않고, 동일한 실행 설정 스냅샷으로 새 대기 Run을 생성합니다.
실제 실행은 실행기가 처리합니다.
계속하려면 Run ID를 정확히 입력하세요.`}
                </p>
                {String(detail.run_status).toUpperCase() === "PARTIAL" && (
                  <p className="text-[11px] text-amber-800 bg-amber-50 border border-amber-100 rounded px-2 py-1">
                    이 Run은 부분 성공 상태입니다. 재시도 시 동일한 대상에 다시 적재될 수 있습니다.
                  </p>
                )}
                {String(detail.run_status).toUpperCase() === "FAILED" && (
                  <p className="text-[11px] text-slate-600 bg-slate-50 border border-slate-100 rounded px-2 py-1">
                    실패 원인을 확인한 뒤 재시도하는 것을 권장합니다.
                  </p>
                )}
                <p className="font-mono text-[10px] text-slate-500">target: {detail.visual_run_id}</p>
                <label className="block text-[11px] text-slate-600">
                  confirm_visual_run_id
                  <input
                    className="mt-1 w-full border border-slate-200 rounded px-2 py-1.5 text-[11px] font-mono"
                    value={confirmRunId}
                    onChange={(e) => setConfirmRunId(e.target.value)}
                    placeholder={detail.visual_run_id}
                    data-testid={`${testIdPrefix}-retry-confirm-input`}
                    autoComplete="off"
                  />
                </label>
                <label className="block text-[11px] text-slate-600">
                  reason (5자 이상)
                  <textarea
                    className="mt-1 w-full border border-slate-200 rounded px-2 py-1.5 text-[11px] min-h-[64px]"
                    value={retryReason}
                    onChange={(e) => setRetryReason(e.target.value)}
                    data-testid={`${testIdPrefix}-retry-reason-input`}
                  />
                </label>
                {retryError && (
                  <p className="text-[11px] text-red-600" data-testid={`${testIdPrefix}-retry-dialog-error`}>
                    {retryError}
                  </p>
                )}
                <div className="flex justify-end gap-2">
                  <button
                    type="button"
                    className="text-[11px] text-slate-600 border border-slate-200 rounded px-2.5 py-1"
                    onClick={closeRetry}
                    disabled={retrySubmitting}
                    data-testid={`${testIdPrefix}-retry-cancel-button`}
                  >
                    취소
                  </button>
                  <button
                    type="button"
                    className="text-[11px] font-medium text-white bg-violet-700 rounded px-2.5 py-1 disabled:opacity-40"
                    onClick={() => void submitRetry()}
                    disabled={!canConfirmRetry}
                    data-testid={`${testIdPrefix}-retry-confirm-button`}
                  >
                    {retrySubmitting ? "처리 중…" : "새 Run으로 재시도"}
                  </button>
                </div>
              </div>
            )}

            <section
              className="rounded-md border border-amber-100 bg-amber-50/40 px-2.5 py-2 space-y-2"
              data-testid={`${testIdPrefix}-cancel-section`}
            >
              <div className="text-[10px] font-bold text-amber-800 uppercase tracking-wide">중단 요청</div>
              {(detail.cancel_requested_at || detail.cancel_reason || cancelAlreadyRequested) && (
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                  <Field label="요청 시각" value={detail.cancel_requested_at ?? progress?.cancel_requested_at} />
                  <Field label="요청자" value={detail.cancel_requested_by ?? progress?.cancel_requested_by} />
                  <Field label="사유" value={detail.cancel_reason ?? progress?.cancel_reason} />
                  <Field
                    label="반영 시각"
                    value={detail.cancel_acknowledged_at ?? progress?.cancel_acknowledged_at}
                  />
                </div>
              )}
              {cancelSuccess && (
                <p
                  className="text-[11px] text-emerald-800 bg-emerald-50 border border-emerald-100 rounded px-2 py-1"
                  data-testid={`${testIdPrefix}-cancel-success`}
                >
                  {cancelSuccess}
                </p>
              )}
              {softCancelable && cancelAlreadyRequested ? (
                <p
                  className="text-[11px] text-amber-900 bg-amber-100/60 border border-amber-200 rounded px-2 py-1"
                  data-testid={`${testIdPrefix}-cancel-requested-badge`}
                >
                  중단 요청됨 — 현재 단계가 끝난 뒤 반영됩니다. (즉시 강제 종료되지 않습니다)
                </p>
              ) : softCancelable ? (
                <button
                  type="button"
                  className="text-[11px] font-medium text-amber-900 border border-amber-300 bg-white rounded px-2.5 py-1 hover:bg-amber-50"
                  onClick={openCancel}
                  data-testid={`${testIdPrefix}-cancel-button`}
                >
                  중단 요청
                </button>
              ) : (
                <p className="text-[11px] text-slate-500" data-testid={`${testIdPrefix}-cancel-unavailable`}>
                  현재 상태({detail.run_status})에서는 중단 요청을 할 수 없습니다. RUNNING만 가능합니다.
                  대기(PENDING) Run은 실행 패널의 「대기 Run 취소」를 사용하세요.
                </p>
              )}
            </section>

            {cancelOpen && (
              <div
                className="rounded-md border border-amber-200 bg-white px-2.5 py-2 space-y-2"
                data-testid={`${testIdPrefix}-cancel-dialog`}
              >
                <div className="text-xs font-bold text-slate-700">Run 중단 요청</div>
                <p className="text-[11px] text-slate-600 whitespace-pre-line">
                  {`실행 중인 Run에 중단을 요청합니다.
현재 진행 중인 단계가 끝난 뒤 실행이 취소됩니다.
이미 완료된 단계의 데이터는 되돌리지 않습니다.
외부 API 호출/적재가 진행 중이면 즉시 중단되지 않을 수 있습니다.
계속하려면 Run ID를 정확히 입력하세요.`}
                </p>
                <p className="font-mono text-[10px] text-slate-500">target: {detail.visual_run_id}</p>
                <label className="block text-[11px] text-slate-600">
                  confirm_visual_run_id
                  <input
                    className="mt-1 w-full border border-slate-200 rounded px-2 py-1.5 text-[11px] font-mono"
                    value={cancelConfirmRunId}
                    onChange={(e) => setCancelConfirmRunId(e.target.value)}
                    placeholder={detail.visual_run_id}
                    data-testid={`${testIdPrefix}-cancel-confirm-input`}
                    autoComplete="off"
                  />
                </label>
                <label className="block text-[11px] text-slate-600">
                  reason (5자 이상)
                  <textarea
                    className="mt-1 w-full border border-slate-200 rounded px-2 py-1.5 text-[11px] min-h-[64px]"
                    value={cancelReason}
                    onChange={(e) => setCancelReason(e.target.value)}
                    data-testid={`${testIdPrefix}-cancel-reason-input`}
                  />
                </label>
                {cancelError && (
                  <p className="text-[11px] text-red-600" data-testid={`${testIdPrefix}-cancel-dialog-error`}>
                    {cancelError}
                  </p>
                )}
                <div className="flex justify-end gap-2">
                  <button
                    type="button"
                    className="text-[11px] text-slate-600 border border-slate-200 rounded px-2.5 py-1"
                    onClick={closeCancel}
                    disabled={cancelSubmitting}
                    data-testid={`${testIdPrefix}-cancel-dialog-close`}
                  >
                    닫기
                  </button>
                  <button
                    type="button"
                    className="text-[11px] font-medium text-white bg-amber-700 rounded px-2.5 py-1 disabled:opacity-40"
                    onClick={() => void submitCancel()}
                    disabled={!canConfirmCancel}
                    data-testid={`${testIdPrefix}-cancel-confirm-button`}
                  >
                    {cancelSubmitting ? "처리 중…" : "중단 요청 접수"}
                  </button>
                </div>
              </div>
            )}

            <section className="grid grid-cols-1 sm:grid-cols-2 gap-2">
              <Field label="생성" value={detail.created_at} />
              <Field label="시작" value={detail.started_at} />
              <Field label="종료" value={detail.finished_at} />
              <Field label="스케줄 시각" value={detail.scheduled_for} />
            </section>
            <section className="grid grid-cols-1 sm:grid-cols-2 gap-2">
              <Field label="Compile ID" value={detail.compile_result_id} />
              <Field label="실행 설정 ID" value={detail.materialization_result_id} />
              <Field label="graph hash" value={detail.graph_version_hash} />
            </section>
            <section className="grid grid-cols-1 sm:grid-cols-2 gap-2">
              <Field label="실행기" value={detail.claimed_by} />
              <Field label="claim" value={detail.claimed_at} />
              <Field label="heartbeat" value={detail.heartbeat_at} />
              <Field label="attempt" value={detail.attempt_count} />
              <Field label="locked_until" value={detail.locked_until} />
            </section>
            <section className="grid grid-cols-1 sm:grid-cols-2 gap-2">
              <Field label="activation_id" value={detail.activation_id} />
              <Field label="스케줄 연결 ID" value={detail.r10_schedule_id} />
              <Field label="dedup_key" value={detail.dedup_key} />
              <Field label="적재 실행 ID" value={detail.load_run_id} />
            </section>
            {(detail.error_message || (detail.issues && detail.issues.length > 0) || detail.result) && (
              <section className="space-y-1.5">
                {detail.error_message && (
                  <p className="text-xs text-red-700 bg-red-50 border border-red-100 rounded-md px-2.5 py-2">
                    {detail.error_message}
                  </p>
                )}
                {detail.issues && detail.issues.length > 0 && (
                  <div className="text-[11px] text-slate-600 bg-slate-50 border border-slate-100 rounded-md px-2.5 py-2">
                    이슈 {detail.issues_count ?? detail.issues.length}건
                    <ul className="mt-1 space-y-0.5 font-mono text-[10px]">
                      {detail.issues.slice(0, 5).map((issue, idx) => (
                        <li key={`${String(issue.code)}-${idx}`}>
                          {String(issue.code ?? "")}: {String(issue.message ?? "")}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
                {detail.result && (
                  <div className="text-[11px] text-slate-600 bg-slate-50 border border-slate-100 rounded-md px-2.5 py-2">
                    <div className="text-[9px] font-bold text-slate-400 uppercase tracking-wide mb-1">결과 요약</div>
                    <div className="font-mono text-[10px] grid grid-cols-2 gap-1">
                      {Object.entries(detail.result)
                        .filter(([k]) => !/secret|token|password|credential|api[_-]?key|authorization/i.test(k))
                        .slice(0, 12)
                        .map(([k, v]) => (
                          <div key={k}>
                            {k}: {v == null ? "-" : String(v)}
                          </div>
                        ))}
                    </div>
                  </div>
                )}
              </section>
            )}
            <p className="text-[10px] text-slate-400">
              읽기 전용 상세 · RUNNING 중단은 soft-cancel(단계 경계 반영)입니다.
            </p>
          </>
        )}
      </div>
    </div>
  );
}
