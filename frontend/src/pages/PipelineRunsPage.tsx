import { useEffect, useState } from "react";
import { RefreshCw, Eye, Play } from "lucide-react";
import { fetchApi, postApi, PagedData } from "@/api/client";
import { Button } from "@/components/Button";
import { DataTable } from "@/components/DataTable";
import { Modal } from "@/components/Modal";
import { StatusBadge } from "@/components/StatusBadge";
import { Pagination, LoadingState, ErrorState } from "@/components/Pagination";
import { DateRangePicker, defaultDateRange } from "@/components/DateRangePicker";
import { SearchPanel } from "@/components/SearchPanel";
import { useToast } from "@/hooks/useToast";
import { useRole } from "@/hooks/useRole";
import { PermissionDeniedModal } from "@/components/PermissionDeniedModal";
import { PageHeader } from "@/layouts/MainLayout";

interface PipelineRun {
  pipeline_run_id: string;
  pipeline_id: string;
  pipeline_name: string;
  pipeline_type: string;
  run_status: string;
  started_at: string;
  finished_at: string | null;
  duration_minutes: number | null;
  message: string | null;
}

interface Pipeline {
  pipeline_id: string;
  name: string;
  type: string;
}

export default function PipelineRunsPage() {
  const { showToast } = useToast();
  const { canRunPipeline } = useRole();
  const [items, setItems] = useState<PipelineRun[]>([]);
  const [allItems, setAllItems] = useState<PipelineRun[]>([]);
  const [pipelines, setPipelines] = useState<Pipeline[]>([]);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [detail, setDetail] = useState<PipelineRun | null>(null);
  const [retrying, setRetrying] = useState<string | null>(null);
  const [triggerTarget, setTriggerTarget] = useState<Pipeline | null>(null);
  const [triggering, setTriggering] = useState(false);
  const [permissionDenied, setPermissionDenied] = useState(false);
  const [dateRange, setDateRange] = useState(defaultDateRange(14));

  const filterByDate = (rows: PipelineRun[]) => {
    if (!dateRange.from && !dateRange.to) return rows;
    const from = dateRange.from ? new Date(`${dateRange.from}T00:00:00`) : null;
    const to = dateRange.to ? new Date(`${dateRange.to}T23:59:59`) : null;
    return rows.filter((r) => {
      const started = new Date(r.started_at);
      if (from && started < from) return false;
      if (to && started > to) return false;
      return true;
    });
  };

  const paginate = (rows: PipelineRun[], p: number) => {
    const size = 20;
    const filtered = filterByDate(rows);
    const start = (p - 1) * size;
    return {
      pageItems: filtered.slice(start, start + size),
      totalPages: Math.max(1, Math.ceil(filtered.length / size)),
    };
  };

  const load = async (p = page) => {
    setLoading(true);
    setError("");
    try {
      const [runsRes, pipesRes] = await Promise.all([
        fetchApi<PagedData<PipelineRun>>("/pipeline-runs", { page: 1, size: 200 }),
        fetchApi<Pipeline[]>("/pipelines"),
      ]);
      setAllItems(runsRes.items);
      setPipelines(pipesRes);
      const { pageItems, totalPages: tp } = paginate(runsRes.items, p);
      setItems(pageItems);
      setTotalPages(tp);
    } catch {
      setError("파이프라인 실행 이력을 불러오지 못했습니다.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(page); }, []);

  const applyFilter = (p = 1) => {
    const { pageItems, totalPages: tp } = paginate(allItems, p);
    setItems(pageItems);
    setTotalPages(tp);
    setPage(p);
  };

  const handleRetry = async (row: PipelineRun) => {
    setRetrying(row.pipeline_run_id);
    try {
      const res = await postApi<{ pipeline_run_id: string }>(`/pipeline-runs/${row.pipeline_run_id}/retry`);
      showToast("success", `재시도가 요청되었습니다. (${res.pipeline_run_id})`);
      load(page);
    } catch {
      showToast("error", "재시도에 실패했습니다. 실패 상태인 작업만 재시도할 수 있습니다.");
    } finally {
      setRetrying(null);
    }
  };

  const handleDetail = async (row: PipelineRun) => {
    try {
      const res = await fetchApi<PipelineRun>(`/pipeline-runs/${row.pipeline_run_id}`);
      setDetail(res);
    } catch {
      setDetail(row);
    }
  };

  const handleTrigger = async () => {
    if (!triggerTarget) return;
    setTriggering(true);
    try {
      await postApi(`/pipelines/${encodeURIComponent(triggerTarget.pipeline_id)}/trigger`, {
        business_date: dateRange.to || new Date().toISOString().slice(0, 10),
      });
      showToast("success", "파이프라인 실행이 요청되었습니다.");
      setTriggerTarget(null);
      load(1);
      setPage(1);
    } catch {
      showToast("error", "파이프라인 실행에 실패했습니다.");
    } finally {
      setTriggering(false);
    }
  };

  const openTrigger = (pipe: Pipeline) => {
    if (!canRunPipeline) {
      setPermissionDenied(true);
      return;
    }
    setTriggerTarget(pipe);
  };

  if (loading && !items.length) return <LoadingState />;
  if (error && !items.length) return <ErrorState message={error} onRetry={() => load()} />;

  return (
    <div>
      <PageHeader
        title="파이프라인 실행 이력"
        description="Airflow 파이프라인 실행 상태와 이력을 관리합니다."
        breadcrumbs={[
          { label: "운영 관리", path: "/ops/pipeline-runs" },
          { label: "파이프라인 실행 이력" },
        ]}
      />

      <div className="bg-white rounded-lg border border-slate-200 p-4 mb-4 shadow-sm">
        <h3 className="text-sm font-semibold text-slate-800 mb-3">파이프라인 목록</h3>
        <div className="flex flex-wrap gap-2">
          {pipelines.map((p) => (
            <Button key={p.pipeline_id} variant="secondary" icon={<Play className="w-3 h-3" />}
              onClick={() => openTrigger(p)}>
              {p.name} 수동 실행
            </Button>
          ))}
        </div>
      </div>

      <SearchPanel
        fields={[
          {
            label: "실행 기간",
            element: <DateRangePicker from={dateRange.from} to={dateRange.to} onChange={(from, to) => setDateRange({ from, to })} />,
          },
        ]}
        onSearch={() => applyFilter(1)}
        onReset={() => { setDateRange(defaultDateRange(14)); applyFilter(1); }}
      />

      <DataTable
        loading={loading}
        columns={[
          { key: "pipeline_run_id", header: "Run ID" },
          { key: "pipeline_name", header: "파이프라인" },
          { key: "pipeline_type", header: "유형" },
          { key: "run_status", header: "상태", render: (r) => <StatusBadge status={r.run_status as string} /> },
          { key: "started_at", header: "시작", render: (r) => new Date(r.started_at as string).toLocaleString("ko-KR") },
          { key: "duration_minutes", header: "소요(분)", render: (r) => r.duration_minutes != null ? String(r.duration_minutes) : "-" },
          {
            key: "actions", header: "작업", render: (r) => {
              const row = r as unknown as PipelineRun;
              return (
                <div className="flex gap-2" onClick={(e) => e.stopPropagation()}>
                  <Button variant="ghost" icon={<Eye className="w-3 h-3" />} onClick={() => handleDetail(row)}>상세</Button>
                  {row.run_status === "FAILED" && (
                    <Button variant="secondary" icon={<RefreshCw className="w-3 h-3" />}
                      disabled={retrying === row.pipeline_run_id}
                      onClick={() => handleRetry(row)}>
                      {retrying === row.pipeline_run_id ? "처리 중..." : "재시도"}
                    </Button>
                  )}
                </div>
              );
            },
          },
        ]}
        data={items as unknown as Record<string, unknown>[]}
      />
      <Pagination page={page} totalPages={totalPages} onChange={(p) => { setPage(p); applyFilter(p); }} />

      <Modal open={!!detail} title="파이프라인 실행 상세" onClose={() => setDetail(null)} size="lg"
        footer={<Button variant="secondary" onClick={() => setDetail(null)}>닫기</Button>}>
        {detail && (
          <dl className="grid grid-cols-2 gap-3 text-sm">
            <div><dt className="text-slate-500">Run ID</dt><dd className="font-medium">{detail.pipeline_run_id}</dd></div>
            <div><dt className="text-slate-500">파이프라인</dt><dd className="font-medium">{detail.pipeline_name}</dd></div>
            <div><dt className="text-slate-500">유형</dt><dd>{detail.pipeline_type}</dd></div>
            <div><dt className="text-slate-500">상태</dt><dd><StatusBadge status={detail.run_status} /></dd></div>
            <div><dt className="text-slate-500">시작</dt><dd>{new Date(detail.started_at).toLocaleString("ko-KR")}</dd></div>
            <div><dt className="text-slate-500">종료</dt><dd>{detail.finished_at ? new Date(detail.finished_at).toLocaleString("ko-KR") : "-"}</dd></div>
            <div className="col-span-2"><dt className="text-slate-500">메시지</dt><dd className="mt-1 text-slate-700">{detail.message || "-"}</dd></div>
          </dl>
        )}
      </Modal>

      <Modal open={!!triggerTarget} title="파이프라인 수동 실행" onClose={() => setTriggerTarget(null)}
        footer={<>
          <Button variant="secondary" onClick={() => setTriggerTarget(null)}>취소</Button>
          <Button icon={<Play className="w-4 h-4" />} onClick={handleTrigger} disabled={triggering}>
            {triggering ? "실행 중..." : "실행"}
          </Button>
        </>}>
        <p className="text-sm text-slate-600">
          <strong>{triggerTarget?.name}</strong> 파이프라인을 수동 실행하시겠습니까?
        </p>
        <p className="text-xs text-slate-400 mt-2">기준일: {dateRange.to || "오늘"}</p>
      </Modal>

      <PermissionDeniedModal open={permissionDenied} onClose={() => setPermissionDenied(false)} />
    </div>
  );
}
