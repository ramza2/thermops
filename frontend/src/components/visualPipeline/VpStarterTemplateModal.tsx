import { useMemo, useState } from "react";
import { Button } from "@/components/Button";
import { Modal } from "@/components/Modal";
import {
  DOMAIN_PRESET_CATALOG,
  DOMAIN_PRESET_NONE_LABEL,
  DOMAIN_PRESET_SECTION_HINT,
  formatDomainPresetKeys,
  getDomainPreset,
  type DomainPresetId,
} from "@/utils/domainPresetCatalog";
import {
  STARTER_TEMPLATE_CATALOG,
  STARTER_TEMPLATE_HINT,
  type StarterTemplateId,
} from "@/utils/starterTemplateCatalog";

export type VpStarterTemplateApplyPayload = {
  templateId: StarterTemplateId;
  domainPresetId: DomainPresetId | null;
};

export type VpStarterTemplateModalProps = {
  open: boolean;
  onClose: () => void;
  onApply: (payload: VpStarterTemplateApplyPayload) => void;
};

export function VpStarterTemplateModal({ open, onClose, onApply }: VpStarterTemplateModalProps) {
  const [selectedId, setSelectedId] = useState<StarterTemplateId>("cron-full");
  const [presetId, setPresetId] = useState<DomainPresetId | null>(null);

  const selectedPreset = useMemo(() => getDomainPreset(presetId), [presetId]);

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
            onClick={() => onApply({ templateId: selectedId, domainPresetId: presetId })}
          >
            적용
          </Button>
        </>
      }
    >
      <div className="space-y-4" data-testid="visual-pipeline-starter-template-modal">
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

        <div
          className="space-y-2 border-t border-slate-100 pt-3"
          data-testid="visual-pipeline-domain-preset-section"
        >
          <div className="text-sm font-semibold text-slate-800">Domain Preset (선택)</div>
          <p className="text-[10px] text-slate-500 leading-relaxed">{DOMAIN_PRESET_SECTION_HINT}</p>

          <label
            className={`flex items-start gap-3 p-2.5 border rounded-lg cursor-pointer ${
              presetId === null ? "border-blue-400 bg-blue-50" : "border-slate-200 hover:bg-slate-50"
            }`}
            data-testid="visual-pipeline-domain-preset-option-none"
          >
            <input
              type="radio"
              name="vp-domain-preset"
              checked={presetId === null}
              onChange={() => setPresetId(null)}
              className="mt-0.5 accent-blue-600"
            />
            <span className="text-xs font-medium text-slate-800">{DOMAIN_PRESET_NONE_LABEL}</span>
          </label>

          {DOMAIN_PRESET_CATALOG.map((p) => (
            <label
              key={p.id}
              className={`flex items-start gap-3 p-2.5 border rounded-lg cursor-pointer ${
                presetId === p.id ? "border-blue-400 bg-blue-50" : "border-slate-200 hover:bg-slate-50"
              }`}
              data-testid={`visual-pipeline-domain-preset-option-${p.id}`}
            >
              <input
                type="radio"
                name="vp-domain-preset"
                checked={presetId === p.id}
                onChange={() => setPresetId(p.id)}
                className="mt-0.5 accent-blue-600"
              />
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="text-xs font-semibold text-slate-800">{p.title}</span>
                  <span className="text-[9px] uppercase tracking-wide text-slate-400">{p.category}</span>
                </div>
                <p className="text-[10px] text-slate-600 mt-0.5 leading-relaxed">{p.description}</p>
              </div>
            </label>
          ))}

          {selectedPreset ? (
            <div
              className="rounded-md border border-slate-200 bg-slate-50 px-2.5 py-2 space-y-1"
              data-testid="visual-pipeline-domain-preset-guide"
            >
              <p className="text-[10px] text-slate-700">
                추천 transform: {selectedPreset.recommendedTransformType ?? "강제 없음"}
              </p>
              <p className="text-[10px] text-slate-700">
                추천 key: {formatDomainPresetKeys(selectedPreset.recommendedConflictKeys)}
              </p>
              <p className="text-[10px] text-slate-600">
                직접 설정 필요: {selectedPreset.requiredSetup.join(", ")}
              </p>
              {selectedPreset.limitations[0] ? (
                <p className="text-[10px] text-slate-500">{selectedPreset.limitations[0]}</p>
              ) : null}
            </div>
          ) : null}
        </div>
      </div>
    </Modal>
  );
}
