import { Button } from "@/components/Button";
import { Modal } from "@/components/Modal";
import { LoadingState } from "@/components/Pagination";
import type { VisualPipelineVersion } from "@/types/visualPipeline";

interface VpVersionHistoryModalProps {
  open: boolean;
  loading: boolean;
  versions: VisualPipelineVersion[];
  onClose: () => void;
}

export function VpVersionHistoryModal({ open, loading, versions, onClose }: VpVersionHistoryModalProps) {
  return (
    <Modal
      open={open}
      title="버전 이력"
      onClose={onClose}
      size="lg"
      footer={<Button variant="secondary" onClick={onClose}>닫기</Button>}
    >
      {loading ? (
        <LoadingState />
      ) : versions.length === 0 ? (
        <div className="py-10 text-center border border-dashed border-slate-200 rounded-lg bg-slate-50">
          <p className="text-sm text-slate-500">저장된 version snapshot이 없습니다.</p>
          <p className="text-xs text-slate-400 mt-1">Studio에서 「버전 저장」으로 snapshot을 남길 수 있습니다.</p>
        </div>
      ) : (
        <div className="space-y-2 max-h-[420px] overflow-y-auto pr-0.5">
          {versions.map((v) => (
            <div
              key={v.version_id}
              className="flex items-start justify-between gap-3 p-3 border border-slate-200 rounded-lg bg-white hover:border-slate-300 hover:shadow-sm transition-all"
            >
              <div className="min-w-0">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="font-mono text-xs font-bold text-blue-700 bg-blue-50 border border-blue-100 rounded px-1.5 py-0.5">
                    v{v.version_no}
                  </span>
                  <span className="text-[11px] text-slate-500 font-mono">{v.created_at ?? "-"}</span>
                </div>
                <div className="text-xs text-slate-700 mt-1.5">{v.change_summary ?? "(요약 없음)"}</div>
                <div className="text-[10px] font-mono text-slate-400 mt-1 truncate">{v.version_id}</div>
              </div>
              <div className="flex flex-col items-end gap-1 shrink-0">
                <span className="text-[10px] font-mono bg-slate-50 border border-slate-200 rounded-full px-2 py-0.5 text-slate-600">
                  nodes {v.node_count}
                </span>
                <span className="text-[10px] font-mono bg-slate-50 border border-slate-200 rounded-full px-2 py-0.5 text-slate-600">
                  edges {v.edge_count}
                </span>
              </div>
            </div>
          ))}
        </div>
      )}
    </Modal>
  );
}
