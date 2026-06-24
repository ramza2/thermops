import { useEffect, useState } from "react";
import { Download } from "lucide-react";
import { fetchApi, PagedData } from "@/api/client";
import { Button } from "@/components/Button";
import { DataTable } from "@/components/DataTable";
import { SearchPanel, SelectInput, TextInput } from "@/components/SearchPanel";
import { DateRangePicker, defaultDateRange } from "@/components/DateRangePicker";
import { Pagination, LoadingState, ErrorState } from "@/components/Pagination";
import { useToast } from "@/hooks/useToast";
import { PageHeader } from "@/layouts/MainLayout";

interface Prediction {
  site_id: string;
  target_at: string;
  predicted_demand: number;
  actual_demand: number | null;
  absolute_error: number | null;
  model_name: string | null;
  model_version: string | null;
}

interface Site {
  site_id: string;
  site_name: string;
}

export default function PredictionResultsPage() {
  const { showToast } = useToast();
  const [items, setItems] = useState<Prediction[]>([]);
  const [sites, setSites] = useState<Site[]>([]);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [filters, setFilters] = useState({ site_id: "", model_name: "" });
  const [dateRange, setDateRange] = useState(defaultDateRange(7));

  useEffect(() => {
    fetchApi<Site[]>("/sites").then(setSites).catch(() => {});
  }, []);

  const load = async (p = page) => {
    setLoading(true);
    setError("");
    try {
      const params: Record<string, unknown> = { page: p, size: 20 };
      if (filters.site_id) params.site_id = filters.site_id;
      if (filters.model_name) params.model_name = filters.model_name;
      if (dateRange.from) params.from = `${dateRange.from}T00:00:00`;
      if (dateRange.to) params.to = `${dateRange.to}T23:59:59`;
      const res = await fetchApi<PagedData<Prediction>>("/predictions", params);
      setItems(res.items);
      setTotalPages(res.total_pages);
    } catch {
      setError("예측 결과를 불러오지 못했습니다.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(page); }, [page]);

  const handleSearch = () => { setPage(1); load(1); };

  const handleDownload = () => {
    const site = filters.site_id || "SITE-001";
    const url = `${import.meta.env.VITE_API_BASE_URL || "/api/v1"}/predictions/export?site_id=${site}`;
    window.open(url, "_blank");
    showToast("success", "예측 결과 다운로드가 시작되었습니다.");
  };

  if (loading && !items.length && !error) return <LoadingState />;

  return (
    <div>
      <PageHeader
        title="예측 결과 조회"
        description="배치 예측 결과를 검색하고 다운로드합니다."
        breadcrumbs={[
          { label: "예측 관리", path: "/predictions/jobs" },
          { label: "예측 결과" },
        ]}
        actions={<Button variant="secondary" icon={<Download className="w-4 h-4" />} onClick={handleDownload}>엑셀 다운로드</Button>}
      />

      <SearchPanel
        fields={[
          {
            label: "조회 기간",
            element: <DateRangePicker from={dateRange.from} to={dateRange.to} onChange={(from, to) => setDateRange({ from, to })} />,
          },
          {
            label: "지사",
            element: (
              <SelectInput value={filters.site_id} onChange={(v) => setFilters({ ...filters, site_id: v })}
                options={[{ value: "", label: "전체" }, ...sites.map((s) => ({ value: s.site_id, label: s.site_name }))]} />
            ),
          },
          {
            label: "모델명",
            element: <TextInput value={filters.model_name} onChange={(v) => setFilters({ ...filters, model_name: v })} placeholder="heat_demand_lgbm" />,
          },
        ]}
        onSearch={handleSearch}
        onReset={() => { setFilters({ site_id: "", model_name: "" }); setDateRange(defaultDateRange(7)); setPage(1); }}
      />

      {error ? <ErrorState message={error} onRetry={() => load()} /> : (
        <>
          <DataTable
            loading={loading}
            columns={[
              { key: "site_id", header: "지사 ID" },
              { key: "target_at", header: "대상 시각", render: (r) => new Date(r.target_at as string).toLocaleString("ko-KR") },
              { key: "predicted_demand", header: "예측값", render: (r) => Number(r.predicted_demand).toFixed(2) },
              { key: "actual_demand", header: "실제값", render: (r) => r.actual_demand != null ? Number(r.actual_demand).toFixed(2) : "-" },
              { key: "absolute_error", header: "절대오차", render: (r) => r.absolute_error != null ? Number(r.absolute_error).toFixed(2) : "-" },
              { key: "model_name", header: "모델", render: (r) => r.model_name ? `${r.model_name} v${r.model_version}` : "-" },
            ]}
            data={items as unknown as Record<string, unknown>[]}
          />
          <Pagination page={page} totalPages={totalPages} onChange={setPage} />
        </>
      )}
    </div>
  );
}
