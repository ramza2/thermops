import type { ChangeEvent } from "react";
import type {
  VisualPipelineComponentConfigSchema,
  VisualPipelineNodeConfigValues,
} from "@/types/visualPipeline";
import { VpColumnListField } from "@/components/visualPipeline/config/VpColumnListField";
import { VpConfigFieldShell } from "@/components/visualPipeline/config/VpConfigFieldShell";

const INPUT_CLASS =
  "h-8 px-2.5 text-xs border border-slate-300 rounded-md w-full focus:outline-none focus:ring-1 focus:ring-blue-500 bg-white disabled:bg-slate-50 disabled:text-slate-400";

const WRITE_MODE_OPTIONS = ["INSERT_ONLY", "DEDUPLICATE", "UPSERT"] as const;
const DUPLICATE_POLICY_OPTIONS = ["KEEP_FIRST", "KEEP_LAST", "ERROR"] as const;
const NULL_UPDATE_OPTIONS = ["KEEP_EXISTING", "OVERWRITE_WITH_NULL"] as const;

export type VpUpsertLoadConfigFormProps = {
  values: VisualPipelineNodeConfigValues;
  schema?: VisualPipelineComponentConfigSchema | null;
  fieldWarnings?: Record<string, string>;
  onChange: (patch: Record<string, unknown>) => void;
  disabled?: boolean;
};

function strVal(values: VisualPipelineNodeConfigValues, key: string): string {
  const v = values[key];
  return v == null ? "" : String(v);
}

function boolVal(values: VisualPipelineNodeConfigValues, key: string, fallback = false): boolean {
  const v = values[key];
  if (typeof v === "boolean") return v;
  return fallback;
}

export function VpUpsertLoadConfigForm({ values, fieldWarnings, onChange, disabled }: VpUpsertLoadConfigFormProps) {
  const writeMode = strVal(values, "write_mode") || "INSERT_ONLY";
  const conflictRequired = writeMode === "DEDUPLICATE" || writeMode === "UPSERT";
  const warn = (key: string) => fieldWarnings?.[key];

  const patchText = (key: string) => (e: ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    const raw = e.target.value;
    onChange({ [key]: raw === "" ? undefined : raw });
  };

  return (
    <div className="space-y-3" data-testid="visual-pipeline-inspector-config-form">
      <section className="rounded-lg border border-slate-100 p-2.5 space-y-2.5">
        <div className="text-[9px] font-bold text-slate-400 uppercase tracking-wide">Target</div>
        <VpConfigFieldShell
          fieldKey="standard_dataset_id"
          label="Standard Dataset ID"
          help="표준 데이터셋 참조 ID. 실제 selector/API 연동은 후속."
          warning={warn("standard_dataset_id")}
        >
          <input
            type="text"
            value={strVal(values, "standard_dataset_id")}
            onChange={patchText("standard_dataset_id")}
            placeholder="SD-001"
            disabled={disabled}
            className={INPUT_CLASS}
          />
        </VpConfigFieldShell>
        <VpConfigFieldShell
          fieldKey="target_table"
          label="Target Table"
          required
          help="적재 대상 물리 테이블명 또는 compiled target hint"
          warning={warn("target_table")}
        >
          <input
            type="text"
            value={strVal(values, "target_table")}
            onChange={patchText("target_table")}
            placeholder="tb_sample_fact"
            disabled={disabled}
            className={INPUT_CLASS}
          />
        </VpConfigFieldShell>
      </section>

      <section className="rounded-lg border border-slate-100 p-2.5 space-y-2.5">
        <div className="text-[9px] font-bold text-slate-400 uppercase tracking-wide">Write Policy</div>
        <VpConfigFieldShell fieldKey="write_mode" label="Write Mode" required warning={warn("write_mode")}>
          <select
            value={writeMode}
            onChange={patchText("write_mode")}
            disabled={disabled}
            className={INPUT_CLASS}
          >
            {WRITE_MODE_OPTIONS.map((opt) => (
              <option key={opt} value={opt}>
                {opt}
              </option>
            ))}
          </select>
        </VpConfigFieldShell>
        <VpColumnListField
          fieldKey="conflict_key_columns_json"
          label="Conflict Key Columns"
          value={values.conflict_key_columns_json}
          placeholder="entity_id, measured_at"
          required={conflictRequired}
          help={
            conflictRequired
              ? "DEDUPLICATE/UPSERT 시 conflict key가 필요합니다 (저장은 차단하지 않음)."
              : "쉼표로 구분된 컬럼 목록 → string[]로 저장"
          }
          warning={warn("conflict_key_columns_json")}
          disabled={disabled}
          onChange={onChange}
        />
      </section>

      <section className="rounded-lg border border-slate-100 p-2.5 space-y-2.5">
        <div className="text-[9px] font-bold text-slate-400 uppercase tracking-wide">Dedup</div>
        <VpConfigFieldShell
          fieldKey="duplicate_within_batch_policy"
          label="Duplicate Within Batch"
          warning={warn("duplicate_within_batch_policy")}
        >
          <select
            value={strVal(values, "duplicate_within_batch_policy") || "KEEP_LAST"}
            onChange={patchText("duplicate_within_batch_policy")}
            disabled={disabled}
            className={INPUT_CLASS}
          >
            {DUPLICATE_POLICY_OPTIONS.map((opt) => (
              <option key={opt} value={opt}>
                {opt}
              </option>
            ))}
          </select>
        </VpConfigFieldShell>
        <VpConfigFieldShell
          fieldKey="null_update_policy"
          label="Null Update Policy"
          warning={warn("null_update_policy")}
        >
          <select
            value={strVal(values, "null_update_policy") || "KEEP_EXISTING"}
            onChange={patchText("null_update_policy")}
            disabled={disabled}
            className={INPUT_CLASS}
          >
            {NULL_UPDATE_OPTIONS.map((opt) => (
              <option key={opt} value={opt}>
                {opt}
              </option>
            ))}
          </select>
        </VpConfigFieldShell>
        <VpConfigFieldShell
          fieldKey="save_dedup_summary_yn"
          label="Save Dedup Summary"
          warning={warn("save_dedup_summary_yn")}
        >
          <label className="inline-flex items-center gap-2 text-[11px] text-slate-600">
            <input
              type="checkbox"
              checked={boolVal(values, "save_dedup_summary_yn", true)}
              onChange={(e) => onChange({ save_dedup_summary_yn: e.target.checked })}
              disabled={disabled}
              className="rounded border-slate-300"
            />
            중복 제거 요약 저장
          </label>
        </VpConfigFieldShell>
      </section>

      <div className="space-y-1 text-[9px] text-slate-500 leading-relaxed px-0.5">
        <p>설정 변경사항은 Graph 저장 시 함께 저장됩니다.</p>
        <p className="text-amber-700">
          실제 적재 정책 적용과 compile 연계는 R11-S6 이후 단계에서 적용됩니다.
        </p>
      </div>
    </div>
  );
}
