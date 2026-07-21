import { Plus } from "lucide-react";
import { useState } from "react";
import { Button } from "@/components/Button";
import { Modal } from "@/components/Modal";
import { TextInput } from "@/components/SearchPanel";
import type { GraphTemplateId } from "@/types/visualPipeline";

const TEMPLATES: { id: GraphTemplateId; label: string; desc: string; hint: string }[] = [
  { id: "blank", label: "Blank", desc: "빈 Canvas에서 시작합니다.", hint: "0 nodes" },
  { id: "rest-upsert", label: "REST → Transform → Upsert", desc: "기본 API 적재 흐름", hint: "3 nodes" },
  { id: "cron-full", label: "CRON → REST → Transform → Upsert", desc: "스케줄 기반 전체 흐름", hint: "4 nodes" },
];

interface VpNewPipelineModalProps {
  open: boolean;
  saving: boolean;
  onClose: () => void;
  onSubmit: (name: string, description: string | undefined, templateId: GraphTemplateId) => void;
}

export function VpNewPipelineModal({ open, saving, onClose, onSubmit }: VpNewPipelineModalProps) {
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [templateId, setTemplateId] = useState<GraphTemplateId>("cron-full");
  const [touched, setTouched] = useState(false);

  const handleSubmit = () => {
    setTouched(true);
    if (!name.trim()) return;
    onSubmit(name.trim(), description.trim() || undefined, templateId);
  };

  return (
    <Modal
      open={open}
      title="새 Visual Pipeline 만들기"
      onClose={onClose}
      footer={
        <>
          <Button variant="secondary" onClick={onClose} disabled={saving}>취소</Button>
          <Button icon={<Plus className="w-4 h-4" />} onClick={handleSubmit} disabled={saving || !name.trim()}>
            {saving ? "생성 중…" : "생성"}
          </Button>
        </>
      }
    >
      <div className="space-y-4">
        <div>
          <label className="block text-xs font-medium text-slate-600 mb-1">pipeline_name *</label>
          <TextInput value={name} onChange={setName} placeholder="예: ASOS 관측 기상 적재 파이프라인" />
          {touched && !name.trim() && (
            <p className="text-[11px] text-red-600 mt-1">pipeline_name은 필수입니다.</p>
          )}
        </div>
        <div>
          <label className="block text-xs font-medium text-slate-600 mb-1">description</label>
          <TextInput value={description} onChange={setDescription} placeholder="파이프라인 설명 (선택)" />
        </div>
        <div>
          <label className="block text-xs font-medium text-slate-600 mb-2">기본 Graph Template</label>
          <div className="grid gap-2">
            {TEMPLATES.map((t) => (
              <label
                key={t.id}
                className={`flex items-start gap-3 p-3 border-2 rounded-lg cursor-pointer transition-all ${
                  templateId === t.id
                    ? "border-blue-400 bg-blue-50 shadow-sm"
                    : "border-slate-200 hover:border-blue-300 hover:bg-slate-50"
                }`}
              >
                <input
                  type="radio"
                  name="vp-template"
                  checked={templateId === t.id}
                  onChange={() => setTemplateId(t.id)}
                  className="mt-1 accent-blue-600"
                />
                <div className="min-w-0 flex-1">
                  <div className="flex items-center justify-between gap-2">
                    <div className="text-sm font-semibold text-slate-800">{t.label}</div>
                    <span className="text-[9px] font-mono text-slate-400 bg-white border border-slate-200 rounded px-1.5 py-0.5 shrink-0">
                      {t.hint}
                    </span>
                  </div>
                  <div className="text-xs text-slate-500 mt-0.5">{t.desc}</div>
                </div>
              </label>
            ))}
          </div>
        </div>
      </div>
    </Modal>
  );
}
