import { useState } from "react";
import { Button } from "@/components/Button";
import { Modal } from "@/components/Modal";
import {
  STARTER_TEMPLATE_CATALOG,
  STARTER_TEMPLATE_HINT,
  type StarterTemplateId,
} from "@/utils/starterTemplateCatalog";

export type VpStarterTemplateModalProps = {
  open: boolean;
  onClose: () => void;
  onApply: (templateId: StarterTemplateId) => void;
};

export function VpStarterTemplateModal({ open, onClose, onApply }: VpStarterTemplateModalProps) {
  const [selectedId, setSelectedId] = useState<StarterTemplateId>("cron-full");

  return (
    <Modal
      open={open}
      title="Starter Template"
      onClose={onClose}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            취소
          </Button>
          <Button
            data-testid="visual-pipeline-starter-template-apply"
            onClick={() => onApply(selectedId)}
          >
            적용
          </Button>
        </>
      }
    >
      <div className="space-y-3" data-testid="visual-pipeline-starter-template-modal">
        <p className="text-xs text-slate-500 leading-relaxed">{STARTER_TEMPLATE_HINT}</p>
        <div className="grid gap-2">
          {STARTER_TEMPLATE_CATALOG.map((t) => (
            <label
              key={t.id}
              className={`flex items-start gap-3 p-3 border-2 rounded-lg cursor-pointer transition-all ${
                selectedId === t.id
                  ? "border-blue-400 bg-blue-50 shadow-sm"
                  : "border-slate-200 hover:border-blue-300 hover:bg-slate-50"
              }`}
              data-testid={`visual-pipeline-starter-template-option-${t.id}`}
            >
              <input
                type="radio"
                name="vp-starter-template"
                checked={selectedId === t.id}
                onChange={() => setSelectedId(t.id)}
                className="mt-1 accent-blue-600"
              />
              <div className="min-w-0 flex-1">
                <div className="flex items-center justify-between gap-2">
                  <div className="text-sm font-semibold text-slate-800">{t.title}</div>
                  <span className="text-[10px] text-slate-400 shrink-0">
                    {t.expectedNodeCount} nodes · {t.expectedEdgeCount} edges
                  </span>
                </div>
                <p className="text-xs text-slate-600 mt-0.5 leading-relaxed">{t.description}</p>
                <p className="text-[10px] text-slate-500 mt-1">
                  필요 설정: {t.requiredSetup.join(", ")}
                </p>
              </div>
            </label>
          ))}
        </div>
      </div>
    </Modal>
  );
}
