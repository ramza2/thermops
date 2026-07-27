import type { VisualPipelineRunResponse } from "@/types/visualPipeline";

interface VpRunDetailPanelProps {
  detail: VisualPipelineRunResponse | null;
  loading?: boolean;
  error?: string | null;
  onClose: () => void;
  testIdPrefix?: string;
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

export function VpRunDetailPanel({
  detail,
  loading,
  error,
  onClose,
  testIdPrefix = "visual-pipeline-run-detail",
}: VpRunDetailPanelProps) {
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
            <p className="text-[10px] text-slate-400">읽기 전용 · Retry / Progress / 중단 요청은 후속 단계입니다.</p>
          </>
        )}
      </div>
    </div>
  );
}
