import { useEffect, useState } from "react";
import { Clock } from "lucide-react";
import { extractApiErrorMessage } from "@/api/client";
import {
  enqueueScheduleCatchupRun,
  getScheduleCatchupCandidate,
} from "@/api/visualPipelines";
import type {
  VisualPipelineScheduleActivationResponse,
  VisualPipelineScheduleCatchupCandidate,
} from "@/types/visualPipeline";

interface VpScheduleActivationPanelProps {
  pipelineId?: string | null;
  result: VisualPipelineScheduleActivationResponse | null;
  loading?: boolean;
  activating?: boolean;
  deactivating?: boolean;
  pausing?: boolean;
  resuming?: boolean;
  error?: string | null;
  canActivateHint?: string | null;
  staleActiveWarning?: boolean;
  expanded: boolean;
  onToggle: () => void;
  onDeactivate?: () => void;
  onPause?: () => void;
  onResume?: () => void;
  onCatchupSuccess?: (catchupVisualRunId: string) => void;
}

function statusTone(status: string | undefined): string {
  if (status === "ACTIVE") return "bg-emerald-50 border-emerald-200 text-emerald-700";
  if (status === "INACTIVE") return "bg-slate-50 border-slate-200 text-slate-600";
  if (status === "PAUSED") return "bg-amber-50 border-amber-200 text-amber-800";
  if (status === "ERROR") return "bg-red-50 border-red-200 text-red-700";
  return "bg-slate-50 border-slate-200 text-slate-600";
}

function catchupErrorMessage(codeOrMsg: string): string {
  const code = codeOrMsg.trim();
  if (code.includes("SCHEDULE_CATCHUP_ACTIVE_RUN_EXISTS")) {
    return "이 파이프라인에 실행 중이거나 대기 중인 Run이 있어 누락 실행 보정을 생성할 수 없습니다.";
  }
  if (code.includes("SCHEDULE_CATCHUP_DUPLICATE_RUN_EXISTS")) {
    return "해당 스케줄 시각에 대한 Run이 이미 존재합니다.";
  }
  if (code.includes("SCHEDULE_CATCHUP_NOT_ELIGIBLE")) {
    return "현재 Catch-up 가능한 누락 실행 후보가 없습니다.";
  }
  if (code.includes("SCHEDULE_CATCHUP_CONFIRM_MISMATCH")) {
    return "confirm_activation_id가 일치하지 않습니다.";
  }
  if (code.includes("SCHEDULE_CATCHUP_REASON_REQUIRED")) {
    return "사유는 5자 이상 입력해야 합니다.";
  }
  if (code.includes("SCHEDULE_CATCHUP_WINDOW_EXCEEDED")) {
    return "Catch-up 허용 시간 창을 초과했습니다.";
  }
  if (code.includes("SCHEDULE_CATCHUP_AUDIT_REQUIRED_FAILED")) {
    return "Audit 기록 실패로 Catch-up Run을 생성하지 못했습니다.";
  }
  return codeOrMsg || "누락 실행 보정 요청에 실패했습니다.";
}

export function VpScheduleActivationPanel({
  pipelineId,
  result,
  loading,
  activating,
  deactivating,
  pausing,
  resuming,
  error,
  canActivateHint,
  staleActiveWarning,
  expanded,
  onToggle,
  onDeactivate,
  onPause,
  onResume,
  onCatchupSuccess,
}: VpScheduleActivationPanelProps) {
  const isActive = result?.activation_status === "ACTIVE";
  const isPaused = result?.activation_status === "PAUSED";
  const busy = Boolean(activating || deactivating || pausing || resuming);

  const [candidate, setCandidate] = useState<VisualPipelineScheduleCatchupCandidate | null>(null);
  const [candidateLoading, setCandidateLoading] = useState(false);
  const [candidateError, setCandidateError] = useState<string | null>(null);
  const [catchupOpen, setCatchupOpen] = useState(false);
  const [confirmActivationId, setConfirmActivationId] = useState("");
  const [catchupReason, setCatchupReason] = useState("");
  const [catchupSubmitting, setCatchupSubmitting] = useState(false);
  const [catchupError, setCatchupError] = useState<string | null>(null);
  const [catchupSuccess, setCatchupSuccess] = useState<string | null>(null);

  const loadCandidate = async () => {
    if (!pipelineId || !result?.activation_id) {
      setCandidate(null);
      return;
    }
    setCandidateLoading(true);
    setCandidateError(null);
    try {
      const data = await getScheduleCatchupCandidate(pipelineId, result.activation_id);
      setCandidate(data);
    } catch (err) {
      setCandidate(null);
      setCandidateError(extractApiErrorMessage(err, "누락 실행 후보를 불러오지 못했습니다."));
    } finally {
      setCandidateLoading(false);
    }
  };

  useEffect(() => {
    setCatchupOpen(false);
    setConfirmActivationId("");
    setCatchupReason("");
    setCatchupError(null);
    setCatchupSuccess(null);
    if (!expanded || !pipelineId || !result?.activation_id) {
      setCandidate(null);
      return;
    }
    void loadCandidate();
    // eslint-disable-next-line react-hooks/exhaustive-deps -- reload when activation identity changes
  }, [expanded, pipelineId, result?.activation_id, result?.last_skip_at, result?.missed_count]);

  const canConfirmCatchup =
    !!result &&
    !!candidate?.eligible &&
    !!candidate.candidate_scheduled_at &&
    confirmActivationId.trim() === result.activation_id &&
    catchupReason.trim().length >= 5 &&
    !catchupSubmitting;

  const submitCatchup = async () => {
    if (!pipelineId || !result || !candidate?.candidate_scheduled_at || !canConfirmCatchup) return;
    setCatchupSubmitting(true);
    setCatchupError(null);
    try {
      const out = await enqueueScheduleCatchupRun(pipelineId, result.activation_id, {
        candidate_scheduled_at: candidate.candidate_scheduled_at,
        reason: catchupReason.trim(),
        confirm_activation_id: confirmActivationId.trim(),
      });
      setCatchupOpen(false);
      setCatchupSuccess(
        `누락 실행 보정 Run이 생성되었습니다. (${out.catchup_visual_run_id}) 실행 이력에서 진행 상태를 확인할 수 있습니다.`,
      );
      onCatchupSuccess?.(out.catchup_visual_run_id);
      await loadCandidate();
    } catch (err) {
      const raw = extractApiErrorMessage(err, "누락 실행 보정 요청에 실패했습니다.");
      setCatchupError(catchupErrorMessage(raw));
    } finally {
      setCatchupSubmitting(false);
    }
  };

  return (
    <div
      className="mt-3 bg-white border border-slate-200 rounded-lg shadow-sm overflow-hidden"
      data-testid="visual-pipeline-schedule-activation-panel"
    >
      <button
        type="button"
        className="w-full flex items-center justify-between px-3 py-2.5 text-left hover:bg-slate-50"
        onClick={onToggle}
      >
        <div className="flex items-center gap-2 min-w-0">
          <Clock className="w-3.5 h-3.5 text-slate-500 shrink-0" />
          <span className="text-xs font-bold text-slate-700">스케줄 활성화</span>
          {result?.activation_status && (
            <span
              className={`text-[10px] font-bold px-1.5 py-0.5 rounded border ${statusTone(result.activation_status)}`}
              data-testid="visual-pipeline-schedule-activation-status"
            >
              {result.activation_status}
            </span>
          )}
          {(loading || busy) && <span className="text-[10px] text-slate-400">처리 중…</span>}
        </div>
        <span className="text-[10px] text-slate-400">{expanded ? "접기" : "펼치기"}</span>
      </button>

      {expanded && (
        <div className="px-3 pb-3 border-t border-slate-100 space-y-2.5">
          {error && (
            <p className="text-xs text-red-600 bg-red-50 border border-red-100 rounded-md px-2.5 py-2">
              {error}
            </p>
          )}
          {!result && !loading && !error && (
            <p className="text-xs text-slate-500">
              아직 스케줄 활성화 이력이 없습니다. 조건 충족 후 스케줄 활성화 버튼으로 시작할 수 있습니다.
            </p>
          )}
          {canActivateHint && !isActive && !isPaused && (
            <p className="text-[11px] text-slate-500 bg-slate-50 border border-slate-100 rounded-md px-2.5 py-2">
              {canActivateHint}
            </p>
          )}
          {staleActiveWarning && (isActive || isPaused) && (
            <p className="text-[11px] text-amber-800 bg-amber-50 border border-amber-100 rounded-md px-2.5 py-2">
              그래프가 최신 Compile과 일치하지 않습니다. 활성/일시중지 스케줄은 유지되지만 다시 Compile 후 실행 설정
              반영을 권장합니다.
            </p>
          )}
          {result && (
            <>
              <p className="text-[11px] text-slate-600 leading-relaxed bg-slate-50 border border-slate-100 rounded-md px-2.5 py-2">
                스케줄을 활성화하면 지정된 주기에 따라 실행 대기 Run이 생성됩니다. 실제 데이터 적재는 실행기가 Run을
                처리할 때 수행됩니다.
              </p>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-[11px]">
                <div>
                  <span className="text-slate-400">activation_id</span>
                  <p className="font-mono text-slate-700" data-testid="visual-pipeline-schedule-activation-id">
                    {result.activation_id}
                  </p>
                </div>
                <div>
                  <span className="text-slate-400">schedule_id</span>
                  <p className="font-mono text-slate-700">{result.r10_schedule_id}</p>
                </div>
                <div>
                  <span className="text-slate-400">cron</span>
                  <p className="font-mono text-slate-700">
                    {result.cron_expression ?? "-"} · {result.timezone ?? "-"}
                  </p>
                </div>
                <div>
                  <span className="text-slate-400">next_due_at</span>
                  <p className="font-mono text-slate-700" data-testid="visual-pipeline-schedule-next-due">
                    {result.next_due_at ?? "-"}
                  </p>
                </div>
                <div>
                  <span className="text-slate-400">last_triggered_at</span>
                  <p className="font-mono text-slate-700">{result.last_triggered_at ?? "-"}</p>
                </div>
                <div>
                  <span className="text-slate-400">trigger_count</span>
                  <p
                    className="font-mono text-slate-700"
                    data-testid="visual-pipeline-schedule-trigger-count"
                  >
                    {result.trigger_count ?? 0}
                  </p>
                </div>
                <div>
                  <span className="text-slate-400">paused_at / resumed_at</span>
                  <p className="font-mono text-slate-700">
                    {result.paused_at ?? "-"} / {result.resumed_at ?? "-"}
                  </p>
                </div>
                <div>
                  <span className="text-slate-400">last_due_at</span>
                  <p className="font-mono text-slate-700">{result.last_due_at ?? "-"}</p>
                </div>
                <div>
                  <span className="text-slate-400">last_skip_reason</span>
                  <p
                    className="font-mono text-slate-700"
                    data-testid="visual-pipeline-schedule-last-skip-reason"
                  >
                    {result.last_skip_reason ?? "-"}
                    {result.last_skip_at ? ` · ${result.last_skip_at}` : ""}
                  </p>
                </div>
                <div>
                  <span className="text-slate-400">missed_count</span>
                  <p
                    className="font-mono text-slate-700"
                    data-testid="visual-pipeline-schedule-missed-count"
                  >
                    {result.missed_count ?? 0}
                  </p>
                </div>
              </div>
              <div className="text-[11px] bg-slate-50 border border-slate-100 rounded-md px-2.5 py-2 text-slate-600 space-y-0.5">
                <p>스케줄 활성화만으로는 데이터 적재를 바로 실행하지 않습니다.</p>
                <p>일시중지하면 새 대기 Run 생성이 멈춥니다. 재개 시 다음 실행 시각을 현재 기준으로 다시 계산합니다.</p>
                <p>자동 Catch-up은 수행하지 않습니다. 아래 「누락 실행 보정」에서 최근 후보 1건만 수동 생성할 수 있습니다.</p>
              </div>
              <div className="flex flex-wrap gap-2">
                {isActive && onPause && (
                  <button
                    type="button"
                    className="inline-flex items-center px-2.5 py-1.5 text-xs font-medium rounded-md border border-slate-300 text-slate-700 hover:bg-slate-50 disabled:opacity-50"
                    onClick={onPause}
                    disabled={busy}
                    data-testid="visual-pipeline-schedule-pause-button"
                  >
                    {pausing ? "일시중지 중…" : "일시중지"}
                  </button>
                )}
                {isPaused && onResume && (
                  <button
                    type="button"
                    className="inline-flex items-center px-2.5 py-1.5 text-xs font-medium rounded-md border border-slate-300 text-slate-700 hover:bg-slate-50 disabled:opacity-50"
                    onClick={onResume}
                    disabled={busy}
                    data-testid="visual-pipeline-schedule-resume-button"
                  >
                    {resuming ? "재개 중…" : "재개"}
                  </button>
                )}
                {(isActive || isPaused) && onDeactivate && (
                  <button
                    type="button"
                    className="inline-flex items-center px-2.5 py-1.5 text-xs font-medium rounded-md border border-slate-300 text-slate-700 hover:bg-slate-50 disabled:opacity-50"
                    onClick={onDeactivate}
                    disabled={busy}
                    data-testid="visual-pipeline-schedule-deactivate-button"
                  >
                    {deactivating ? "비활성화 중…" : "비활성화"}
                  </button>
                )}
              </div>

              <section
                className="rounded-md border border-teal-100 bg-teal-50/40 px-2.5 py-2 space-y-2"
                data-testid="visual-pipeline-schedule-catchup-section"
              >
                <div className="flex items-center justify-between gap-2">
                  <div className="text-[10px] font-bold text-teal-800 uppercase tracking-wide">
                    누락 실행 보정
                  </div>
                  <button
                    type="button"
                    className="text-[10px] text-teal-800 border border-teal-200 bg-white rounded px-2 py-0.5 hover:bg-teal-50 disabled:opacity-40"
                    onClick={() => void loadCandidate()}
                    disabled={candidateLoading || !pipelineId}
                    data-testid="visual-pipeline-schedule-catchup-refresh"
                  >
                    {candidateLoading ? "확인 중…" : "후보 새로고침"}
                  </button>
                </div>
                <p className="text-[11px] text-slate-600">
                  스케줄이 실행되지 못한 최근 후보를 확인하고, 운영자가 명시적으로 1건만 다시 대기 Run으로
                  생성합니다. 자동 보정은 수행하지 않습니다.
                </p>
                <p className="text-[11px] text-amber-900 bg-amber-50 border border-amber-100 rounded px-2 py-1">
                  과거 스케줄 기준으로 다시 실행되므로, 입력 데이터의 기준시점과 중복 적재 가능성을 확인하세요.
                </p>
                {candidateLoading && (
                  <p className="text-[11px] text-slate-500" data-testid="visual-pipeline-schedule-catchup-loading">
                    누락 실행 후보를 확인하는 중입니다.
                  </p>
                )}
                {candidateError && (
                  <p
                    className="text-[11px] text-red-600"
                    data-testid="visual-pipeline-schedule-catchup-error"
                  >
                    {candidateError}
                  </p>
                )}
                {catchupSuccess && (
                  <p
                    className="text-[11px] text-emerald-800 bg-emerald-50 border border-emerald-100 rounded px-2 py-1"
                    data-testid="visual-pipeline-schedule-catchup-success"
                  >
                    {catchupSuccess}
                  </p>
                )}
                {!candidateLoading && !candidateError && candidate && (
                  <>
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-[11px]">
                      <div>
                        <span className="text-slate-400">eligible</span>
                        <p
                          className="font-mono text-slate-700"
                          data-testid="visual-pipeline-schedule-catchup-eligible"
                        >
                          {candidate.eligible ? "true" : "false"}
                        </p>
                      </div>
                      <div>
                        <span className="text-slate-400">candidate_scheduled_at</span>
                        <p className="font-mono text-slate-700">
                          {candidate.candidate_scheduled_at ?? "-"}
                        </p>
                      </div>
                      <div>
                        <span className="text-slate-400">last_skip_reason</span>
                        <p className="font-mono text-slate-700">{candidate.last_skip_reason ?? "-"}</p>
                      </div>
                      <div>
                        <span className="text-slate-400">missed_count</span>
                        <p className="font-mono text-slate-700">{candidate.missed_count ?? 0}</p>
                      </div>
                    </div>
                    {candidate.reason && (
                      <p className="text-[11px] text-slate-600" data-testid="visual-pipeline-schedule-catchup-reason">
                        {candidate.reason}
                      </p>
                    )}
                    {(candidate.warnings || []).map((w) => (
                      <p key={w} className="text-[11px] text-amber-800">
                        {w}
                      </p>
                    ))}
                    {candidate.eligible ? (
                      <button
                        type="button"
                        className="text-[11px] font-medium text-teal-900 border border-teal-300 bg-white rounded px-2.5 py-1 hover:bg-teal-50"
                        onClick={() => {
                          setCatchupOpen(true);
                          setConfirmActivationId("");
                          setCatchupReason("");
                          setCatchupError(null);
                        }}
                        data-testid="visual-pipeline-schedule-catchup-button"
                      >
                        누락 실행 보정 Run 생성
                      </button>
                    ) : (
                      <p
                        className="text-[11px] text-slate-500"
                        data-testid="visual-pipeline-schedule-catchup-unavailable"
                      >
                        Catch-up 가능한 누락 실행 후보가 없습니다.
                      </p>
                    )}
                  </>
                )}
                {catchupOpen && candidate?.eligible && candidate.candidate_scheduled_at && (
                  <div
                    className="rounded-md border border-teal-200 bg-white px-2.5 py-2 space-y-2"
                    data-testid="visual-pipeline-schedule-catchup-dialog"
                  >
                    <div className="text-xs font-bold text-slate-700">누락 실행 보정 Run 생성</div>
                    <p className="text-[11px] text-slate-600 whitespace-pre-line">
                      {`선택한 누락 스케줄 후보를 새 대기 Run으로 생성합니다.
이 작업은 즉시 실행하지 않으며, 기존 실행기가 Run을 처리합니다.
과거 기준시점의 데이터를 다시 적재할 수 있으므로 대상 테이블과 입력 데이터 기준을 확인하세요.
계속하려면 Activation ID를 정확히 입력하세요.`}
                    </p>
                    <p className="font-mono text-[10px] text-slate-500">
                      target: {result.activation_id} · {candidate.candidate_scheduled_at}
                    </p>
                    <label className="block text-[11px] text-slate-600">
                      confirm_activation_id
                      <input
                        className="mt-1 w-full border border-slate-200 rounded px-2 py-1.5 text-[11px] font-mono"
                        value={confirmActivationId}
                        onChange={(e) => setConfirmActivationId(e.target.value)}
                        placeholder={result.activation_id}
                        data-testid="visual-pipeline-schedule-catchup-confirm-input"
                        autoComplete="off"
                      />
                    </label>
                    <label className="block text-[11px] text-slate-600">
                      reason (5자 이상)
                      <textarea
                        className="mt-1 w-full border border-slate-200 rounded px-2 py-1.5 text-[11px] min-h-[64px]"
                        value={catchupReason}
                        onChange={(e) => setCatchupReason(e.target.value)}
                        data-testid="visual-pipeline-schedule-catchup-reason-input"
                      />
                    </label>
                    {catchupError && (
                      <p
                        className="text-[11px] text-red-600"
                        data-testid="visual-pipeline-schedule-catchup-dialog-error"
                      >
                        {catchupError}
                      </p>
                    )}
                    <div className="flex justify-end gap-2">
                      <button
                        type="button"
                        className="text-[11px] text-slate-600 border border-slate-200 rounded px-2.5 py-1"
                        onClick={() => setCatchupOpen(false)}
                        disabled={catchupSubmitting}
                        data-testid="visual-pipeline-schedule-catchup-dialog-close"
                      >
                        닫기
                      </button>
                      <button
                        type="button"
                        className="text-[11px] font-medium text-white bg-teal-700 rounded px-2.5 py-1 disabled:opacity-40"
                        onClick={() => void submitCatchup()}
                        disabled={!canConfirmCatchup}
                        data-testid="visual-pipeline-schedule-catchup-confirm-button"
                      >
                        {catchupSubmitting ? "처리 중…" : "보정 Run 생성"}
                      </button>
                    </div>
                  </div>
                )}
              </section>
            </>
          )}
        </div>
      )}
    </div>
  );
}
