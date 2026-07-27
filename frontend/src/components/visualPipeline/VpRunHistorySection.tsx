import { useCallback, useEffect, useState } from "react";
import { RefreshCw } from "lucide-react";
import { extractApiErrorMessage } from "@/api/client";
import { getVisualPipelineRun, listVisualPipelineRuns } from "@/api/visualPipelines";
import { VpRunDetailPanel } from "@/components/visualPipeline/VpRunDetailPanel";
import type {
  VisualPipelineRunResponse,
  VisualPipelineRunSummary,
} from "@/types/visualPipeline";

interface VpRunHistorySectionProps {
  pipelineId: string;
  /** Bump to refresh list (e.g. after Run Now / terminal). */
  refreshToken?: number;
}

function statusTone(status: string | undefined): string {
  if (status === "SUCCESS") return "bg-emerald-50 border-emerald-200 text-emerald-700";
  if (status === "PARTIAL") return "bg-amber-50 border-amber-200 text-amber-800";
  if (status === "FAILED" || status === "CANCELLED") return "bg-red-50 border-red-200 text-red-700";
  if (status === "PENDING" || status === "RUNNING") return "bg-sky-50 border-sky-200 text-sky-700";
  return "bg-slate-50 border-slate-200 text-slate-600";
}

function modeLabel(mode?: string | null): string {
  if (mode === "SCHEDULED") return "스케줄";
  if (mode === "MANUAL") return "즉시";
  return mode ?? "-";
}

function shortId(id: string): string {
  if (id.length <= 14) return id;
  return `${id.slice(0, 10)}…`;
}

export function VpRunHistorySection({ pipelineId, refreshToken = 0 }: VpRunHistorySectionProps) {
  const [items, setItems] = useState<VisualPipelineRunSummary[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState("");
  const [modeFilter, setModeFilter] = useState("");
  const [detail, setDetail] = useState<VisualPipelineRunResponse | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState<string | null>(null);
  const [detailOpen, setDetailOpen] = useState(false);

  const loadHistory = useCallback(async () => {
    if (!pipelineId) return;
    setLoading(true);
    setError(null);
    try {
      const listed = await listVisualPipelineRuns(pipelineId, {
        limit: 20,
        offset: 0,
        run_status: statusFilter || undefined,
        mode: modeFilter || undefined,
      });
      setItems(listed.items ?? []);
      setTotal(listed.total ?? listed.items?.length ?? 0);
    } catch (err) {
      setError(extractApiErrorMessage(err, "실행 이력을 불러오지 못했습니다."));
      setItems([]);
      setTotal(0);
    } finally {
      setLoading(false);
    }
  }, [pipelineId, statusFilter, modeFilter]);

  useEffect(() => {
    void loadHistory();
  }, [loadHistory, refreshToken]);

  const openDetail = async (visualRunId: string) => {
    setDetailOpen(true);
    setDetail(null);
    setDetailError(null);
    setDetailLoading(true);
    try {
      const row = await getVisualPipelineRun(pipelineId, visualRunId);
      setDetail(row);
    } catch (err) {
      setDetailError(extractApiErrorMessage(err, "Run 상세 정보를 찾을 수 없습니다. 목록을 새로고침해 주세요."));
    } finally {
      setDetailLoading(false);
    }
  };

  return (
    <div
      className="border-t border-slate-100 pt-3 space-y-2.5"
      data-testid="visual-pipeline-run-history-section"
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <div className="text-[10px] font-bold text-slate-500 uppercase tracking-wide">최근 실행 이력</div>
          <div className="text-[10px] text-slate-400">total={total}</div>
        </div>
        <button
          type="button"
          className="inline-flex items-center gap-1 px-2 py-1 text-[11px] font-medium rounded-md border border-slate-200 text-slate-600 hover:bg-slate-50 disabled:opacity-50"
          onClick={() => void loadHistory()}
          disabled={loading}
          data-testid="visual-pipeline-run-history-refresh"
        >
          <RefreshCw className={`w-3 h-3 ${loading ? "animate-spin" : ""}`} />
          새로고침
        </button>
      </div>

      <div className="flex flex-wrap gap-2">
        <select
          className="text-[11px] border border-slate-200 rounded-md px-2 py-1 bg-white"
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          data-testid="visual-pipeline-run-history-status-filter"
        >
          <option value="">상태 전체</option>
          {["PENDING", "RUNNING", "SUCCESS", "PARTIAL", "FAILED", "CANCELLED"].map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>
        <select
          className="text-[11px] border border-slate-200 rounded-md px-2 py-1 bg-white"
          value={modeFilter}
          onChange={(e) => setModeFilter(e.target.value)}
          data-testid="visual-pipeline-run-history-mode-filter"
        >
          <option value="">실행 방식 전체</option>
          <option value="MANUAL">즉시 실행</option>
          <option value="SCHEDULED">스케줄 실행</option>
        </select>
      </div>

      {error && (
        <p className="text-xs text-red-600 bg-red-50 border border-red-100 rounded-md px-2.5 py-2">{error}</p>
      )}
      {loading && !items.length && (
        <p className="text-xs text-slate-500">실행 이력을 불러오는 중입니다.</p>
      )}
      {!loading && !error && items.length === 0 && (
        <p className="text-xs text-slate-500">
          아직 실행 이력이 없습니다. 즉시 실행 또는 스케줄 활성화 후 실행 이력이 표시됩니다.
        </p>
      )}

      {items.length > 0 && (
        <div className="overflow-x-auto border border-slate-100 rounded-md">
          <table className="min-w-full text-[11px]">
            <thead className="bg-slate-50 text-slate-500">
              <tr>
                <th className="text-left font-medium px-2 py-1.5">Run</th>
                <th className="text-left font-medium px-2 py-1.5">상태</th>
                <th className="text-left font-medium px-2 py-1.5">방식</th>
                <th className="text-left font-medium px-2 py-1.5">생성</th>
                <th className="text-left font-medium px-2 py-1.5">이슈</th>
                <th className="text-left font-medium px-2 py-1.5" />
              </tr>
            </thead>
            <tbody>
              {items.map((row) => (
                <tr
                  key={row.visual_run_id}
                  className="border-t border-slate-100"
                  data-testid="visual-pipeline-run-history-row"
                >
                  <td className="px-2 py-1.5 font-mono whitespace-nowrap" title={row.visual_run_id}>
                    {shortId(row.visual_run_id)}
                  </td>
                  <td className="px-2 py-1.5">
                    <span
                      className={`inline-flex text-[10px] font-bold uppercase tracking-wide border rounded px-1.5 py-0.5 ${statusTone(row.run_status)}`}
                    >
                      {row.run_status}
                    </span>
                  </td>
                  <td className="px-2 py-1.5 whitespace-nowrap">{modeLabel(row.mode)}</td>
                  <td className="px-2 py-1.5 font-mono whitespace-nowrap text-[10px]">
                    {row.created_at ?? "-"}
                  </td>
                  <td className="px-2 py-1.5">{row.issues_count ?? 0}</td>
                  <td className="px-2 py-1.5 text-right">
                    <button
                      type="button"
                      className="text-[11px] font-medium text-violet-700 hover:underline"
                      onClick={() => void openDetail(row.visual_run_id)}
                      data-testid="visual-pipeline-run-history-detail-button"
                    >
                      상세
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {detailOpen && (
        <VpRunDetailPanel
          detail={detail}
          loading={detailLoading}
          error={detailError}
          onClose={() => {
            setDetailOpen(false);
            setDetail(null);
            setDetailError(null);
          }}
        />
      )}
    </div>
  );
}
