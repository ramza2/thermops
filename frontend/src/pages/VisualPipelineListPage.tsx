import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Archive, ArrowRight, Plus, RefreshCw, Workflow } from "lucide-react";
import {
  archiveVisualPipeline,
  createVisualPipelineFromTemplate,
  listVisualPipelines,
} from "@/api/visualPipelines";
import { extractApiErrorMessage } from "@/api/client";
import { Button } from "@/components/Button";
import { DataTable, type Column } from "@/components/DataTable";
import { StatusBadge } from "@/components/StatusBadge";
import { ErrorState, LoadingState } from "@/components/Pagination";
import { SearchPanel, SelectInput, TextInput } from "@/components/SearchPanel";
import { VpNewPipelineModal } from "@/components/visualPipeline/VpNewPipelineModal";
import { useToast } from "@/hooks/useToast";
import { PageHeader } from "@/layouts/MainLayout";
import { PAGE_DESCRIPTIONS, PAGE_TITLES } from "@/constants/displayLabels";
import type { GraphTemplateId, VisualPipelineSummary } from "@/types/visualPipeline";

const STATUS_OPTIONS = [
  { value: "", label: "전체 상태 (활성 목록)" },
  { value: "DRAFT", label: "DRAFT" },
  { value: "VALIDATED", label: "VALIDATED" },
  { value: "ACTIVE", label: "ACTIVE" },
  { value: "ARCHIVED", label: "ARCHIVED (보관됨)" },
];

export default function VisualPipelineListPage() {
  const navigate = useNavigate();
  const { showToast } = useToast();
  const [items, setItems] = useState<VisualPipelineSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("");
  const [createOpen, setCreateOpen] = useState(false);
  const [creating, setCreating] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const res = await listVisualPipelines({
        q: search.trim() || undefined,
        status: status || undefined,
      });
      setItems(res.items);
    } catch (err) {
      setError(extractApiErrorMessage(err, "Visual Pipeline 목록을 불러오지 못했습니다."));
    } finally {
      setLoading(false);
    }
  }, [search, status]);

  useEffect(() => {
    void load();
  }, [load]);

  const handleCreate = async (name: string, description: string | undefined, templateId: GraphTemplateId) => {
    setCreating(true);
    try {
      const created = await createVisualPipelineFromTemplate(name, description, templateId);
      showToast("success", "Visual Pipeline이 생성되었습니다.");
      setCreateOpen(false);
      navigate(`/visual-pipelines/${created.pipeline_id}`);
    } catch (err) {
      showToast("error", extractApiErrorMessage(err, "Visual Pipeline 생성에 실패했습니다."));
    } finally {
      setCreating(false);
    }
  };

  const handleArchive = async (row: VisualPipelineSummary) => {
    if (!window.confirm(`"${row.pipeline_name}"을(를) 보관(Archive) 하시겠습니까?\n삭제되지 않으며 기본 목록에서 숨겨집니다.`)) return;
    try {
      await archiveVisualPipeline(row.pipeline_id);
      showToast("success", "Visual Pipeline이 보관 처리되었습니다.");
      void load();
    } catch (err) {
      showToast("error", extractApiErrorMessage(err, "보관 처리에 실패했습니다."));
    }
  };

  const columns: Column<VisualPipelineSummary>[] = [
    {
      key: "pipeline_name",
      header: "pipeline_name",
      render: (row) => (
        <div>
          <div className="font-medium text-slate-800">{row.pipeline_name}</div>
          <div className="font-mono text-[10px] text-slate-400 mt-0.5">{row.pipeline_id}</div>
        </div>
      ),
    },
    {
      key: "description",
      header: "description",
      render: (r) => <span className="text-xs text-slate-500 line-clamp-2">{r.description ?? "-"}</span>,
    },
    { key: "status", header: "status", render: (r) => <StatusBadge status={r.status} /> },
    { key: "sync", header: "sync", render: (r) => <StatusBadge status={r.current_sync_status} /> },
    {
      key: "nodes",
      header: "graph",
      render: (r) => (
        <div className="flex flex-wrap gap-1">
          <span className="inline-flex items-center text-[10px] font-mono bg-slate-50 border border-slate-200 text-slate-600 rounded-full px-2 py-0.5">
            nodes {r.node_count}
          </span>
          <span className="inline-flex items-center text-[10px] font-mono bg-slate-50 border border-slate-200 text-slate-600 rounded-full px-2 py-0.5">
            edges {r.edge_count}
          </span>
        </div>
      ),
    },
    {
      key: "updated",
      header: "updated_at",
      render: (r) => <span className="font-mono text-[11px] text-slate-500">{r.updated_at ?? "-"}</span>,
    },
    {
      key: "open",
      header: "열기",
      render: (r) => (
        <Link
          to={`/visual-pipelines/${r.pipeline_id}`}
          className="inline-flex items-center gap-1 text-xs font-medium text-blue-700 hover:underline"
        >
          <ArrowRight className="w-3 h-3" /> Studio
        </Link>
      ),
    },
    {
      key: "archive",
      header: "보관",
      render: (r) =>
        r.status === "ARCHIVED" ? (
          <span className="text-[10px] text-slate-400">보관됨</span>
        ) : (
          <button
            type="button"
            onClick={() => void handleArchive(r)}
            className="inline-flex items-center gap-1 text-xs text-slate-500 hover:text-amber-700"
            title="삭제되지 않습니다. 기본 목록에서 숨깁니다."
          >
            <Archive className="w-3 h-3" /> 보관
          </button>
        ),
    },
  ];

  return (
    <div>
      <PageHeader
        title={PAGE_TITLES.visualPipelineStudio}
        description={PAGE_DESCRIPTIONS.visualPipelineStudio}
        actions={
          <>
            <Button icon={<Plus className="w-4 h-4" />} onClick={() => setCreateOpen(true)}>새 Visual Pipeline</Button>
            <Button variant="secondary" icon={<RefreshCw className="w-4 h-4" />} onClick={() => void load()}>새로고침</Button>
          </>
        }
      />

      <div className="mb-4 flex flex-wrap items-center gap-2">
        <span className="inline-flex items-center text-[10px] font-bold uppercase tracking-wide bg-violet-50 text-violet-700 border border-violet-200 rounded px-2 py-0.5">
          R11 PoC
        </span>
        <span className="text-xs text-slate-500">
          보관(Archive)은 삭제와 다릅니다. 기본 목록에서는 보관된 파이프라인이 숨겨질 수 있습니다.
        </span>
      </div>

      <SearchPanel
        fields={[
          { label: "검색", element: <TextInput value={search} onChange={setSearch} placeholder="pipeline_name / description" /> },
          { label: "status", element: <SelectInput value={status} onChange={setStatus} options={STATUS_OPTIONS} /> },
        ]}
        onSearch={() => void load()}
        onReset={() => { setSearch(""); setStatus(""); }}
      />

      {loading ? (
        <LoadingState />
      ) : error ? (
        <ErrorState message={error} onRetry={() => void load()} />
      ) : items.length === 0 ? (
        <div className="bg-white border border-slate-200 rounded-lg shadow-sm flex flex-col items-center justify-center py-16 px-6 text-slate-400">
          <div className="w-14 h-14 rounded-full bg-slate-50 border border-slate-100 flex items-center justify-center mb-4">
            <Workflow className="w-7 h-7 text-slate-300" />
          </div>
          <p className="text-sm font-semibold text-slate-600">아직 생성된 Visual Pipeline이 없습니다.</p>
          <p className="text-xs mt-1.5 mb-5 text-center max-w-sm leading-relaxed">
            새 Visual Pipeline을 만들어 REST API 적재 흐름을 노드와 연결선으로 구성해 보세요.
          </p>
          <Button icon={<Plus className="w-4 h-4" />} onClick={() => setCreateOpen(true)}>새 Visual Pipeline</Button>
        </div>
      ) : (
        <div className="bg-white border border-slate-200 rounded-lg shadow-sm overflow-hidden">
          <DataTable columns={columns} data={items as (VisualPipelineSummary & Record<string, unknown>)[]} />
        </div>
      )}

      <VpNewPipelineModal open={createOpen} saving={creating} onClose={() => setCreateOpen(false)} onSubmit={handleCreate} />
    </div>
  );
}
