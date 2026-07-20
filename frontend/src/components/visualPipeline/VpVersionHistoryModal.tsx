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
        <p className="text-sm text-slate-500 py-4 text-center">저장된 version snapshot이 없습니다.</p>
      ) : (
        <div className="space-y-2">
          {versions.map((v) => (
            <div
              key={v.version_id}
              className="flex items-start justify-between p-3 border border-slate-200 rounded-lg hover:bg-slate-50"
            >
              <div>
                <div className="flex items-center gap-2">
                  <span className="font-mono text-xs font-bold text-blue-700">v{v.version_no}</span>
                  <span className="text-xs text-slate-500 font-mono">{v.created_at ?? "-"}</span>
                </div>
                <div className="text-xs text-slate-600 mt-1">{v.change_summary ?? "(요약 없음)"}</div>
              </div>
              <div className="text-right text-xs font-mono text-slate-400 shrink-0 ml-4">
                <div>노드 {v.node_count}</div>
                <div>엣지 {v.edge_count}</div>
              </div>
            </div>
          ))}
        </div>
      )}
    </Modal>
  );
}
