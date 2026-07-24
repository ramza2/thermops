import { useCallback, useEffect, useState } from "react";
import { RefreshCw } from "lucide-react";
import {
  getVisualPipelineOpsAuditLogs,
  getVisualPipelineOpsStuckRuns,
  getVisualPipelineOpsSummary,
  markFailedErrorMessage,
  markVisualPipelineStuckRunFailed,
} from "@/api/visualPipelineOps";
import { extractApiErrorMessage } from "@/api/client";
import { Button } from "@/components/Button";
import { Modal } from "@/components/Modal";
import { LoadingState, ErrorState } from "@/components/Pagination";
import { PageHeader } from "@/layouts/MainLayout";
import { useRole } from "@/hooks/useRole";
import { PAGE_DESCRIPTIONS, PAGE_TITLES } from "@/constants/displayLabels";
import type {
  VisualPipelineAuditLogListItem,
  VisualPipelineOpsStuckRun,
  VisualPipelineOpsSummary,
} from "@/types/visualPipelineOps";

const RUN_STATUSES = ["PENDING", "RUNNING", "SUCCESS", "FAILED", "PARTIAL", "CANCELLED"] as const;
const ACT_STATUSES = ["ACTIVE", "PAUSED", "INACTIVE", "ERROR"] as const;

const AUDIT_EVENT_FILTERS = [
  "",
  "SCHEDULE_ACTIVATE",
  "SCHEDULE_DEACTIVATE",
  "SCHEDULE_PAUSE",
  "SCHEDULE_RESUME",
  "RUN_CANCELLED",
  "OPS_MARK_FAILED_DRY_RUN",
  "OPS_MARK_FAILED_APPLY",
  "RUN_MARK_FAILED_BY_OPS",
  "SCHEDULE_WORKER_SKIPPED_ACTIVE_RUN",
] as const;

function fmt(value: string | number | null | undefined): string {
  if (value === null || value === undefined || value === "") return "-";
  return String(value);
}

function CountGrid({
  testId,
  title,
  keys,
  counts,
}: {
  testId: string;
  title: string;
  keys: readonly string[];
  counts: Partial<Record<string, number>> | undefined;
}) {
  return (
    <section
      className="bg-white border border-slate-200 rounded-lg p-4 shadow-sm"
      data-testid={testId}
    >
      <h2 className="text-sm font-semibold text-slate-800 mb-3">{title}</h2>
      <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
        {keys.map((key) => (
          <div key={key} className="rounded-md bg-slate-50 border border-slate-100 px-2.5 py-2">
            <div className="text-[10px] uppercase tracking-wide text-slate-400">{key}</div>
            <div className="text-lg font-semibold text-slate-800 tabular-nums">
              {Number(counts?.[key] ?? 0)}
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}

export default function VisualPipelineOpsPage() {
  const { canViewVpOps } = useRole();
  const [summary, setSummary] = useState<VisualPipelineOpsSummary | null>(null);
  const [stuckItems, setStuckItems] = useState<VisualPipelineOpsStuckRun[]>([]);
  const [stuckTotal, setStuckTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [summaryError, setSummaryError] = useState<string | null>(null);
  const [stuckError, setStuckError] = useState<string | null>(null);

  const [auditItems, setAuditItems] = useState<VisualPipelineAuditLogListItem[]>([]);
  const [auditTotal, setAuditTotal] = useState(0);
  const [auditLoading, setAuditLoading] = useState(false);
  const [auditError, setAuditError] = useState<string | null>(null);
  const [auditEventType, setAuditEventType] = useState("");

  const [markTarget, setMarkTarget] = useState<VisualPipelineOpsStuckRun | null>(null);
  const [confirmRunId, setConfirmRunId] = useState("");
  const [markReason, setMarkReason] = useState("");
  const [markSubmitting, setMarkSubmitting] = useState(false);
  const [actionMessage, setActionMessage] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  const loadAudit = useCallback(async () => {
    if (!canViewVpOps) return;
    setAuditLoading(true);
    setAuditError(null);
    try {
      const data = await getVisualPipelineOpsAuditLogs({
        event_type: auditEventType || undefined,
        limit: 50,
      });
      setAuditItems(data.items ?? []);
      setAuditTotal(data.total ?? (data.items?.length ?? 0));
    } catch (err) {
      setAuditItems([]);
      setAuditTotal(0);
      setAuditError(
        extractApiErrorMessage(err, "Audit logs를 불러오지 못했습니다."),
      );
    } finally {
      setAuditLoading(false);
    }
  }, [canViewVpOps, auditEventType]);

  const load = useCallback(async () => {
    if (!canViewVpOps) return;
    setLoading(true);
    setSummaryError(null);
    setStuckError(null);
    const [summaryResult, stuckResult] = await Promise.allSettled([
      getVisualPipelineOpsSummary(),
      getVisualPipelineOpsStuckRuns({ pending_age_seconds: 600, limit: 50 }),
    ]);
    if (summaryResult.status === "fulfilled") {
      setSummary(summaryResult.value);
    } else {
      setSummary(null);
      setSummaryError(
        extractApiErrorMessage(
          summaryResult.reason,
          "운영 현황을 불러오지 못했습니다. backend / visual-pipeline-ops API 상태를 확인하세요.",
        ),
      );
    }
    if (stuckResult.status === "fulfilled") {
      setStuckItems(stuckResult.value.items ?? []);
      setStuckTotal(stuckResult.value.total ?? (stuckResult.value.items?.length ?? 0));
    } else {
      setStuckItems([]);
      setStuckTotal(0);
      setStuckError(
        extractApiErrorMessage(
          stuckResult.reason,
          "stuck runs를 불러오지 못했습니다.",
        ),
      );
    }
    setLoading(false);
  }, [canViewVpOps]);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    void loadAudit();
  }, [loadAudit]);

  const openMarkFailed = (row: VisualPipelineOpsStuckRun) => {
    setMarkTarget(row);
    setConfirmRunId("");
    setMarkReason("");
    setActionError(null);
    setActionMessage(null);
  };

  const closeMarkFailed = () => {
    if (markSubmitting) return;
    setMarkTarget(null);
    setConfirmRunId("");
    setMarkReason("");
  };

  const canConfirmMarkFailed =
    !!markTarget &&
    confirmRunId.trim() === markTarget.visual_run_id &&
    markReason.trim().length >= 5;

  const submitMarkFailed = async () => {
    if (!markTarget || !canConfirmMarkFailed) return;
    setMarkSubmitting(true);
    setActionError(null);
    setActionMessage(null);
    try {
      await markVisualPipelineStuckRunFailed(markTarget.visual_run_id, {
        reason: markReason.trim(),
        confirm_visual_run_id: confirmRunId.trim(),
        pending_age_seconds: 600,
        running_lock_grace_seconds: 0,
      });
      setMarkTarget(null);
      setConfirmRunId("");
      setMarkReason("");
      setActionMessage("Run이 FAILED로 처리되었습니다. Audit Log에 기록되었습니다.");
      await Promise.all([load(), loadAudit()]);
    } catch (err) {
      setActionError(markFailedErrorMessage(err));
    } finally {
      setMarkSubmitting(false);
    }
  };

  if (!canViewVpOps) {
    return (
      <div data-testid="visual-pipeline-ops-page">
        <PageHeader
          title={PAGE_TITLES.visualPipelineOps}
          description={PAGE_DESCRIPTIONS.visualPipelineOps}
        />
        <div
          className="mt-4 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900"
          data-testid="visual-pipeline-ops-admin-required"
        >
          <p className="font-semibold">ADMIN mock role에서만 표시되는 운영 화면입니다.</p>
          <p className="mt-1 text-amber-800">
            `VITE_USER_ROLE=ADMIN`으로 설정하면 메뉴와 데이터가 표시됩니다. 이 값은 운영 권한 체계가
            아니라 Frontend mock 표시 제어입니다. 비ADMIN에서는 ops API를 호출하지 않습니다.
          </p>
        </div>
      </div>
    );
  }

  const cfg = summary?.worker_config;
  const stuck = summary?.stuck_summary;
  const hints = summary?.activity_hints;
  const failures = summary?.recent_failures ?? [];

  return (
    <div data-testid="visual-pipeline-ops-page" className="space-y-4">
      <PageHeader
        title={PAGE_TITLES.visualPipelineOps}
        description={PAGE_DESCRIPTIONS.visualPipelineOps}
        actions={
          <Button
            variant="secondary"
            icon={<RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />}
            onClick={() => void load()}
            disabled={loading}
            data-testid="visual-pipeline-ops-refresh-button"
          >
            {loading ? "새로고침 중…" : "새로고침"}
          </Button>
        }
      />

      <div className="flex flex-wrap items-center gap-2" data-testid="visual-pipeline-ops-read-only-notice">
        <span className="inline-flex items-center rounded border border-slate-300 bg-slate-50 px-2 py-0.5 text-[10px] font-bold tracking-wide text-slate-600">
          READ ONLY
        </span>
        <span className="inline-flex items-center rounded border border-amber-200 bg-amber-50 px-2 py-0.5 text-[10px] font-bold tracking-wide text-amber-800">
          Admin mock role
        </span>
        <span className="text-xs text-slate-500">
          stuck run에 한정해 `실패 처리`(strong confirm + audit required)를 지원합니다. pause /
          resume / deactivate / cancel / retry 버튼은 없습니다. CLI도 계속 사용할 수 있습니다.
        </span>
      </div>

      {actionMessage && (
        <div
          className="rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-900"
          data-testid="visual-pipeline-ops-mark-failed-success"
        >
          {actionMessage}
        </div>
      )}
      {actionError && !markTarget && (
        <div
          className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800"
          data-testid="visual-pipeline-ops-mark-failed-error"
        >
          {actionError}
        </div>
      )}

      {loading && !summary && !summaryError && <LoadingState />}
      {summaryError && !summary && (
        <ErrorState
          message={summaryError}
          onRetry={() => void load()}
        />
      )}

      {summary && (
        <>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
            <CountGrid
              testId="visual-pipeline-ops-run-counts"
              title="Run Status Counts"
              keys={RUN_STATUSES}
              counts={summary.run_status_counts}
            />
            <CountGrid
              testId="visual-pipeline-ops-activation-counts"
              title="Activation Status Counts"
              keys={ACT_STATUSES}
              counts={summary.activation_status_counts}
            />
            <section
              className="bg-white border border-slate-200 rounded-lg p-4 shadow-sm"
              data-testid="visual-pipeline-ops-stuck-summary"
            >
              <h2 className="text-sm font-semibold text-slate-800 mb-3">Stuck Summary</h2>
              <div className="grid grid-cols-2 gap-2">
                <div className="rounded-md bg-slate-50 border border-slate-100 px-2.5 py-2">
                  <div className="text-[10px] text-slate-400">pending_older_than_threshold</div>
                  <div className="text-lg font-semibold tabular-nums text-slate-800">
                    {Number(stuck?.pending_older_than_threshold ?? 0)}
                  </div>
                </div>
                <div className="rounded-md bg-slate-50 border border-slate-100 px-2.5 py-2">
                  <div className="text-[10px] text-slate-400">running_lock_expired</div>
                  <div className="text-lg font-semibold tabular-nums text-slate-800">
                    {Number(stuck?.running_lock_expired ?? 0)}
                  </div>
                </div>
              </div>
            </section>
            <section
              className="bg-white border border-slate-200 rounded-lg p-4 shadow-sm"
              data-testid="visual-pipeline-ops-worker-config"
            >
              <h2 className="text-sm font-semibold text-slate-800 mb-3">Worker Config</h2>
              <dl className="grid grid-cols-1 sm:grid-cols-2 gap-x-3 gap-y-1.5 text-xs">
                <div>
                  <dt className="text-slate-400">run_executor</dt>
                  <dd className="font-mono text-slate-700">{fmt(cfg?.run_executor)}</dd>
                </div>
                <div>
                  <dt className="text-slate-400">run_worker_enabled</dt>
                  <dd className="font-mono text-slate-700">{String(Boolean(cfg?.run_worker_enabled))}</dd>
                </div>
                <div>
                  <dt className="text-slate-400">schedule_activation_enabled</dt>
                  <dd className="font-mono text-slate-700">
                    {String(Boolean(cfg?.schedule_activation_enabled))}
                  </dd>
                </div>
                <div>
                  <dt className="text-slate-400">schedule_worker_enabled</dt>
                  <dd className="font-mono text-slate-700">
                    {String(Boolean(cfg?.schedule_worker_enabled))}
                  </dd>
                </div>
                <div>
                  <dt className="text-slate-400">run_worker_lock_ttl_seconds</dt>
                  <dd className="font-mono text-slate-700">{fmt(cfg?.run_worker_lock_ttl_seconds)}</dd>
                </div>
                <div>
                  <dt className="text-slate-400">run_worker_poll_interval_seconds</dt>
                  <dd className="font-mono text-slate-700">
                    {fmt(cfg?.run_worker_poll_interval_seconds)}
                  </dd>
                </div>
                <div>
                  <dt className="text-slate-400">schedule_worker_poll_interval_seconds</dt>
                  <dd className="font-mono text-slate-700">
                    {fmt(cfg?.schedule_worker_poll_interval_seconds)}
                  </dd>
                </div>
              </dl>
            </section>
          </div>

          <section
            className="bg-white border border-slate-200 rounded-lg p-4 shadow-sm"
            data-testid="visual-pipeline-ops-activity-hints"
          >
            <h2 className="text-sm font-semibold text-slate-800 mb-1">Activity Hints</h2>
            <p className="text-[11px] text-slate-500 mb-3">
              DB 상태 기반 관찰 힌트이며 Docker process liveness를 직접 확인하지 않습니다.
            </p>
            <dl className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-2 text-xs">
              <div>
                <dt className="text-slate-400">latest_claimed_at</dt>
                <dd className="font-mono text-slate-700 break-all">{fmt(hints?.latest_claimed_at)}</dd>
              </div>
              <div>
                <dt className="text-slate-400">latest_heartbeat_at</dt>
                <dd className="font-mono text-slate-700 break-all">{fmt(hints?.latest_heartbeat_at)}</dd>
              </div>
              <div>
                <dt className="text-slate-400">latest_last_triggered_at</dt>
                <dd className="font-mono text-slate-700 break-all">
                  {fmt(hints?.latest_last_triggered_at)}
                </dd>
              </div>
              <div>
                <dt className="text-slate-400">latest_last_skip_at</dt>
                <dd className="font-mono text-slate-700 break-all">{fmt(hints?.latest_last_skip_at)}</dd>
              </div>
            </dl>
          </section>

          <section className="bg-white border border-slate-200 rounded-lg p-4 shadow-sm">
            <div className="flex items-baseline justify-between gap-2 mb-2">
              <h2 className="text-sm font-semibold text-slate-800">Stuck Runs</h2>
              <span className="text-[11px] text-slate-400">total={stuckTotal}</span>
            </div>
            <p className="text-[11px] text-slate-500 mb-3">
              행별 `실패 처리`는 Audit 기록 성공 시에만 FAILED로 전환됩니다. CLI
              `manage_visual_pipeline_ops.py mark-failed`도 동일 fail-close 정책입니다.
            </p>
            {stuckError && !stuckItems.length ? (
              <p className="text-xs text-red-600">{stuckError}</p>
            ) : stuckItems.length === 0 ? (
              <p className="text-sm text-slate-500">현재 stuck run이 없습니다.</p>
            ) : (
              <div className="overflow-x-auto" data-testid="visual-pipeline-ops-stuck-runs-table">
                <table className="min-w-full text-xs text-left">
                  <thead className="bg-slate-50 text-slate-500">
                    <tr>
                      {[
                        "reason",
                        "visual_run_id",
                        "pipeline_id",
                        "mode",
                        "run_status",
                        "age_seconds",
                        "scheduled_for",
                        "locked_until",
                        "heartbeat_at",
                        "claimed_by",
                        "attempt_count",
                        "action",
                      ].map((h) => (
                        <th key={h} className="px-2 py-1.5 font-medium whitespace-nowrap">
                          {h}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {stuckItems.map((row) => (
                      <tr key={row.visual_run_id} className="border-t border-slate-100">
                        <td className="px-2 py-1.5 font-mono whitespace-nowrap">{fmt(row.reason)}</td>
                        <td className="px-2 py-1.5 font-mono whitespace-nowrap">{row.visual_run_id}</td>
                        <td className="px-2 py-1.5 font-mono whitespace-nowrap">{row.pipeline_id}</td>
                        <td className="px-2 py-1.5">{fmt(row.mode)}</td>
                        <td className="px-2 py-1.5">{fmt(row.run_status)}</td>
                        <td className="px-2 py-1.5 tabular-nums">{fmt(row.age_seconds)}</td>
                        <td className="px-2 py-1.5 font-mono whitespace-nowrap">
                          {fmt(row.scheduled_for)}
                        </td>
                        <td className="px-2 py-1.5 font-mono whitespace-nowrap">
                          {fmt(row.locked_until)}
                        </td>
                        <td className="px-2 py-1.5 font-mono whitespace-nowrap">
                          {fmt(row.heartbeat_at)}
                        </td>
                        <td className="px-2 py-1.5 font-mono">{fmt(row.claimed_by)}</td>
                        <td className="px-2 py-1.5 tabular-nums">{fmt(row.attempt_count)}</td>
                        <td className="px-2 py-1.5 whitespace-nowrap">
                          <Button
                            variant="secondary"
                            onClick={() => openMarkFailed(row)}
                            data-testid="visual-pipeline-ops-mark-failed-button"
                          >
                            실패 처리
                          </Button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>

          <section className="bg-white border border-slate-200 rounded-lg p-4 shadow-sm">
            <h2 className="text-sm font-semibold text-slate-800 mb-3">Recent Failures</h2>
            {failures.length === 0 ? (
              <p className="text-sm text-slate-500">최근 실패 Run이 없습니다.</p>
            ) : (
              <div className="overflow-x-auto" data-testid="visual-pipeline-ops-recent-failures-table">
                <table className="min-w-full text-xs text-left">
                  <thead className="bg-slate-50 text-slate-500">
                    <tr>
                      {[
                        "visual_run_id",
                        "pipeline_id",
                        "mode",
                        "activation_id",
                        "error_message",
                        "finished_at",
                      ].map((h) => (
                        <th key={h} className="px-2 py-1.5 font-medium whitespace-nowrap">
                          {h}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {failures.map((row) => (
                      <tr key={row.visual_run_id} className="border-t border-slate-100">
                        <td className="px-2 py-1.5 font-mono whitespace-nowrap">{row.visual_run_id}</td>
                        <td className="px-2 py-1.5 font-mono whitespace-nowrap">{row.pipeline_id}</td>
                        <td className="px-2 py-1.5">{fmt(row.mode)}</td>
                        <td className="px-2 py-1.5 font-mono whitespace-nowrap">
                          {fmt(row.activation_id)}
                        </td>
                        <td className="px-2 py-1.5 max-w-md truncate" title={row.error_message ?? ""}>
                          {fmt(row.error_message)}
                        </td>
                        <td className="px-2 py-1.5 font-mono whitespace-nowrap">
                          {fmt(row.finished_at)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>
        </>
      )}

      <section
        className="bg-white border border-slate-200 rounded-lg p-4 shadow-sm"
        data-testid="visual-pipeline-ops-audit-section"
      >
        <div className="flex flex-wrap items-center justify-between gap-2 mb-3">
          <div>
            <h2 className="text-sm font-semibold text-slate-800">Audit Logs</h2>
            <p className="text-[11px] text-slate-500 mt-0.5">
              read-only list · detail modal / mark-failed 액션 없음 · total={auditTotal}
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <label className="text-[11px] text-slate-500 flex items-center gap-1.5">
              event_type
              <select
                className="border border-slate-200 rounded px-2 py-1 text-xs font-mono text-slate-700 bg-white"
                value={auditEventType}
                onChange={(e) => setAuditEventType(e.target.value)}
                data-testid="visual-pipeline-ops-audit-event-filter"
              >
                {AUDIT_EVENT_FILTERS.map((ev) => (
                  <option key={ev || "ALL"} value={ev}>
                    {ev || "(all)"}
                  </option>
                ))}
              </select>
            </label>
            <Button
              variant="secondary"
              icon={<RefreshCw className={`w-3.5 h-3.5 ${auditLoading ? "animate-spin" : ""}`} />}
              onClick={() => void loadAudit()}
              disabled={auditLoading}
              data-testid="visual-pipeline-ops-audit-refresh-button"
            >
              {auditLoading ? "Audit 새로고침…" : "Audit 새로고침"}
            </Button>
          </div>
        </div>
        {auditError && !auditItems.length ? (
          <p className="text-xs text-red-600">{auditError}</p>
        ) : auditLoading && !auditItems.length ? (
          <p className="text-sm text-slate-500">Audit logs 로딩 중…</p>
        ) : auditItems.length === 0 ? (
          <p className="text-sm text-slate-500">표시할 audit log가 없습니다.</p>
        ) : (
          <div className="overflow-x-auto" data-testid="visual-pipeline-ops-audit-table">
            <table className="min-w-full text-xs text-left">
              <thead className="bg-slate-50 text-slate-500">
                <tr>
                  {[
                    "created_at",
                    "event_type",
                    "action_status",
                    "pipeline_id",
                    "visual_run_id",
                    "activation_id",
                    "actor",
                    "reason",
                  ].map((h) => (
                    <th key={h} className="px-2 py-1.5 font-medium whitespace-nowrap">
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {auditItems.map((row) => (
                  <tr key={row.audit_id} className="border-t border-slate-100">
                    <td className="px-2 py-1.5 font-mono whitespace-nowrap">
                      {fmt(row.created_at)}
                    </td>
                    <td className="px-2 py-1.5 font-mono whitespace-nowrap">{row.event_type}</td>
                    <td className="px-2 py-1.5">{fmt(row.action_status)}</td>
                    <td className="px-2 py-1.5 font-mono whitespace-nowrap">
                      {fmt(row.pipeline_id)}
                    </td>
                    <td className="px-2 py-1.5 font-mono whitespace-nowrap">
                      {fmt(row.visual_run_id)}
                    </td>
                    <td className="px-2 py-1.5 font-mono whitespace-nowrap">
                      {fmt(row.activation_id)}
                    </td>
                    <td className="px-2 py-1.5 font-mono whitespace-nowrap">
                      {fmt(row.actor_type)}/{fmt(row.actor_id)}
                    </td>
                    <td className="px-2 py-1.5 max-w-xs truncate" title={row.reason ?? ""}>
                      {fmt(row.reason)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <Modal
        open={!!markTarget}
        title="Stuck Run 실패 처리"
        onClose={closeMarkFailed}
        size="md"
        footer={
          <>
            <Button
              variant="secondary"
              onClick={closeMarkFailed}
              disabled={markSubmitting}
              data-testid="visual-pipeline-ops-mark-failed-cancel-button"
            >
              취소
            </Button>
            <Button
              onClick={() => void submitMarkFailed()}
              disabled={!canConfirmMarkFailed || markSubmitting}
              data-testid="visual-pipeline-ops-mark-failed-confirm-button"
            >
              {markSubmitting ? "처리 중…" : "Audit 기록 후 실패 처리"}
            </Button>
          </>
        }
      >
        <div data-testid="visual-pipeline-ops-mark-failed-dialog" className="space-y-3 text-sm">
          <p className="text-slate-700 whitespace-pre-line">
            {`이 작업은 선택한 Run을 FAILED 상태로 변경합니다.
Audit Log 기록에 성공한 경우에만 상태가 변경됩니다.
실행 중인 정상 Run이나 조건을 만족하지 않는 Run은 처리되지 않습니다.
계속하려면 Run ID를 정확히 입력하세요.`}
          </p>
          <p className="font-mono text-xs text-slate-500">
            target: {markTarget?.visual_run_id}
          </p>
          <label className="block text-xs text-slate-600">
            confirm_visual_run_id
            <input
              className="mt-1 w-full border border-slate-200 rounded px-2 py-1.5 text-sm font-mono"
              value={confirmRunId}
              onChange={(e) => setConfirmRunId(e.target.value)}
              placeholder={markTarget?.visual_run_id}
              data-testid="visual-pipeline-ops-mark-failed-confirm-input"
              autoComplete="off"
            />
          </label>
          <label className="block text-xs text-slate-600">
            reason (5자 이상)
            <textarea
              className="mt-1 w-full border border-slate-200 rounded px-2 py-1.5 text-sm min-h-[72px]"
              value={markReason}
              onChange={(e) => setMarkReason(e.target.value)}
              data-testid="visual-pipeline-ops-mark-failed-reason-input"
            />
          </label>
          {actionError && markTarget && (
            <p className="text-xs text-red-600" data-testid="visual-pipeline-ops-mark-failed-dialog-error">
              {actionError}
            </p>
          )}
        </div>
      </Modal>
    </div>
  );
}
