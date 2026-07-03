import { useEffect, useState } from "react";
import { Eye, Play } from "lucide-react";
import { fetchApi, postApi, PagedData } from "@/api/client";
import { Button } from "@/components/Button";
import { DataTable } from "@/components/DataTable";
import { MetricCard } from "@/components/MetricCard";
import { Modal } from "@/components/Modal";
import { StatusBadge } from "@/components/StatusBadge";
import { Pagination, LoadingState, ErrorState } from "@/components/Pagination";
import { useToast } from "@/hooks/useToast";
import { PageHeader } from "@/layouts/MainLayout";
import { PAGE_DESCRIPTIONS, PAGE_TITLES } from "@/constants/displayLabels";
import {
  extractQualityCheckError,
  formatQualityTableSummary,
  qualityMetricsRows,
  QualityRun,
  QualitySummary,
} from "@/utils/qualitySummary";

function SummarySection({ title, items, tone }: { title: string; items: string[]; tone: "error" | "warning" }) {
  if (!items.length) return null;
  const boxClass = tone === "error"
    ? "bg-red-50 border-red-200 text-red-900"
    : "bg-amber-50 border-amber-200 text-amber-900";
  return (
    <div className={`rounded border p-3 text-sm ${boxClass}`}>
      <p className="font-medium mb-2">{title}</p>
      <ul className="list-disc list-inside space-y-1 text-xs">
        {items.map((item) => <li key={item}>{item}</li>)}
      </ul>
    </div>
  );
}

function DomainSummaryBlock({ summary, title }: { summary: QualitySummary; title?: string }) {
  return (
    <div className="border border-slate-200 rounded-lg p-3 space-y-3">
      {title && <p className="text-sm font-medium text-slate-800">{title}</p>}
      <dl className="grid grid-cols-2 gap-2 text-xs">
        <div><dt className="text-slate-500">도메인</dt><dd>{summary.data_domain || "-"}</dd></div>
        <div><dt className="text-slate-500">대상 테이블</dt><dd className="break-all">{summary.target_table || "-"}</dd></div>
        {qualityMetricsRows(summary).map((row) => (
          <div key={row.label}>
            <dt className="text-slate-500">{row.label}</dt>
            <dd>{row.value}</dd>
          </div>
        ))}
      </dl>
      <SummarySection title="오류" items={summary.errors || []} tone="error" />
      <SummarySection title="경고" items={summary.warnings || []} tone="warning" />
    </div>
  );
}

export default function DataQualityPage() {
  const { showToast } = useToast();
  const [items, setItems] = useState<QualityRun[]>([]);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [running, setRunning] = useState(false);
  const [detail, setDetail] = useState<QualityRun | null>(null);

  const load = async (p = page) => {
    setLoading(true);
    setError("");
    try {
      const res = await fetchApi<PagedData<QualityRun>>("/data-quality/runs", { page: p, size: 20 });
      setItems(res.items);
      setTotalPages(res.total_pages);
    } catch {
      setError("품질 점검 이력을 불러오지 못했습니다.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(page); }, [page]);

  const handleRunCheck = async () => {
    setRunning(true);
    try {
      const res = await postApi<{
        run_id: string;
        status: string;
        result_summary?: QualitySummary;
        error_message?: string | null;
      }>("/data-quality/checks");

      const summary = res.result_summary;
      const runId = res.run_id;

      if (res.status === "FAILED") {
        const msg = summary?.errors?.[0] || res.error_message || "품질 점검에 실패했습니다.";
        showToast("error", `${msg} (${runId})`);
      } else if (res.status === "WARNING") {
        const msg = summary?.warnings?.[0] || "경고가 발견되었습니다.";
        const score = summary?.quality_score;
        showToast(
          "warning",
          score != null ? `품질 점검 완료(주의) — ${msg} · 점수 ${score.toFixed(1)} (${runId})` : `${msg} (${runId})`,
        );
      } else {
        const score = summary?.quality_score;
        showToast(
          "success",
          score != null
            ? `품질 점검 완료 — 점수 ${score.toFixed(1)} (${runId})`
            : `품질 점검이 완료되었습니다. (${runId})`,
        );
      }

      await load(1);
      setPage(1);
    } catch (err: unknown) {
      showToast("error", extractQualityCheckError(err));
    } finally {
      setRunning(false);
    }
  };

  const successCount = items.filter((i) => i.run_status === "SUCCESS").length;
  const latest = items[0]?.result_summary;
  const detailSummary = detail?.result_summary;

  if (loading && !items.length) return <LoadingState />;
  if (error && !items.length) return <ErrorState message={error} onRetry={() => load()} />;

  return (
    <div>
      <PageHeader
        title={PAGE_TITLES.dataQuality}
        description={PAGE_DESCRIPTIONS.dataQuality}
        actions={<Button icon={<Play className="w-4 h-4" />} onClick={handleRunCheck} disabled={running}>{running ? "실행 중..." : "품질 점검 실행"}</Button>}
      />

      <div className="grid grid-cols-4 gap-4 mb-6">
        <MetricCard title="총 점검 횟수" value={items.length} />
        <MetricCard title="성공" value={successCount} subtitle="현재 페이지 기준" />
        <MetricCard
          title="최근 품질 점수"
          value={latest?.quality_score != null ? latest.quality_score.toFixed(1) : "-"}
          subtitle={latest?.target_table || "이력 없음"}
        />
        <div className="bg-white rounded-lg border border-slate-200 p-4 shadow-sm">
          <p className="text-xs text-slate-500 font-medium uppercase tracking-wide">최근 상태</p>
          <div className="mt-2">{items[0] ? <StatusBadge status={items[0].run_status} /> : <span className="text-2xl font-bold text-slate-900">-</span>}</div>
          <p className="text-xs text-slate-400 mt-1">{items[0] ? new Date(items[0].started_at).toLocaleString("ko-KR") : "이력 없음"}</p>
        </div>
      </div>

      <DataTable
        loading={loading}
        columns={[
          { key: "run_id", header: "실행 ID" },
          { key: "source_id", header: "소스 ID", render: (r) => String(r.source_id || "전체") },
          { key: "check_type", header: "점검 유형" },
          { key: "run_status", header: "상태", render: (r) => <StatusBadge status={r.run_status as string} /> },
          {
            key: "result_summary",
            header: "결과 요약",
            render: (r) => formatQualityTableSummary(
              r.result_summary as QualitySummary | null,
              r.run_status as string,
            ),
          },
          { key: "started_at", header: "시작", render: (r) => new Date(r.started_at as string).toLocaleString("ko-KR") },
          {
            key: "actions",
            header: "작업",
            render: (r) => {
              const row = r as unknown as QualityRun;
              return (
                <div onClick={(e) => e.stopPropagation()}>
                  <Button variant="ghost" icon={<Eye className="w-3 h-3" />} onClick={() => setDetail(row)}>상세</Button>
                </div>
              );
            },
          },
        ]}
        data={items as unknown as Record<string, unknown>[]}
      />
      <Pagination page={page} totalPages={totalPages} onChange={setPage} />

      <Modal open={!!detail} title="품질 점검 상세" onClose={() => setDetail(null)} size="lg"
        footer={<Button variant="secondary" onClick={() => setDetail(null)}>닫기</Button>}>
        {detail && (
          <div className="space-y-4 text-sm">
            <dl className="grid grid-cols-2 gap-3">
              <div><dt className="text-slate-500">실행 ID</dt><dd className="font-medium">{detail.run_id}</dd></div>
              <div><dt className="text-slate-500">소스 ID</dt><dd>{detail.source_id || "전체"}</dd></div>
              <div><dt className="text-slate-500">점검 유형</dt><dd>{detail.check_type}</dd></div>
              <div><dt className="text-slate-500">상태</dt><dd><StatusBadge status={detail.run_status} /></dd></div>
              <div><dt className="text-slate-500">시작</dt><dd>{new Date(detail.started_at).toLocaleString("ko-KR")}</dd></div>
              <div><dt className="text-slate-500">종료</dt><dd>{detail.finished_at ? new Date(detail.finished_at).toLocaleString("ko-KR") : "-"}</dd></div>
            </dl>

            {detailSummary ? (
              <>
                {detailSummary.errors?.length ? (
                  <SummarySection title="오류 (실패 원인)" items={detailSummary.errors} tone="error" />
                ) : null}
                {detailSummary.warnings?.length ? (
                  <SummarySection title="경고" items={detailSummary.warnings} tone="warning" />
                ) : null}

                {detailSummary.checks?.length ? (
                  <div className="space-y-3">
                    <p className="font-medium text-slate-800">도메인별 점검 결과</p>
                    {detailSummary.checks.map((check) => (
                      <DomainSummaryBlock
                        key={check.data_domain || check.target_table}
                        summary={check}
                        title={check.data_domain || check.target_table}
                      />
                    ))}
                  </div>
                ) : (
                  <DomainSummaryBlock summary={detailSummary} />
                )}

                <div>
                  <p className="text-slate-500 text-xs mb-1">원본 결과 (JSON)</p>
                  <pre className="text-xs bg-slate-50 border rounded p-3 overflow-auto max-h-48">
                    {JSON.stringify(detailSummary, null, 2)}
                  </pre>
                </div>
              </>
            ) : (
              <p className="text-slate-500 text-sm">저장된 결과 요약이 없습니다.</p>
            )}
          </div>
        )}
      </Modal>
    </div>
  );
}
