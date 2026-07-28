import type { ChangeEvent } from "react";
import type {
  VisualPipelineComponentConfigSchema,
  VisualPipelineNodeConfigValues,
} from "@/types/visualPipeline";
import { VpConfigFieldShell } from "@/components/visualPipeline/config/VpConfigFieldShell";
import { VpJsonTextareaField } from "@/components/visualPipeline/config/VpJsonTextareaField";
import {
  DEFAULT_UNMAPPED_POLICY,
  UNMAPPED_POLICY_SELECT_OPTIONS,
  UNSUPPORTED_UNMAPPED_POLICY_MESSAGE,
  isAllowedUnmappedPolicy,
  isUnsupportedLegacyUnmappedPolicy,
} from "@/constants/transformUnmappedPolicy";

const INPUT_CLASS =
  "h-8 px-2.5 text-xs border border-slate-300 rounded-md w-full focus:outline-none focus:ring-1 focus:ring-blue-500 bg-white disabled:bg-slate-50 disabled:text-slate-400";

const TRANSFORM_TYPE_OPTIONS = [
  "NONE",
  "WIDE_HOUR_TO_LONG",
  "ASOS_HOURLY_TO_CANONICAL",
  "CALENDAR_SPECIAL_DAY_TO_DATE",
  "CALENDAR_DATE_TO_HOUR",
] as const;

const MAPPING_PLACEHOLDER = `{
  "mappings": [
    { "source": "value", "target": "demand_value", "type": "number" }
  ]
}`;

const HOUR_POLICY_PLACEHOLDER = `{
  "hour_columns": ["h01", "h02", "h03"],
  "target_hour_column": "hour"
}`;

export type VpTransformConfigFormProps = {
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

function previewJson(value: unknown): string {
  if (value === undefined || value === null) return "";
  if (typeof value === "object") {
    try {
      return JSON.stringify(value, null, 2);
    } catch {
      return "";
    }
  }
  return String(value);
}

export function VpTransformConfigForm({ values, fieldWarnings, onChange, disabled }: VpTransformConfigFormProps) {
  const patchSelect = (key: string) => (e: ChangeEvent<HTMLSelectElement>) => {
    const raw = e.target.value;
    onChange({ [key]: raw === "" ? undefined : raw });
  };

  const schemaPreview = previewJson(values.target_schema_preview);
  const warn = (key: string) => fieldWarnings?.[key];
  const unmappedPolicy = strVal(values, "unmapped_policy");
  const unsupportedLegacy = Boolean(unmappedPolicy) && isUnsupportedLegacyUnmappedPolicy(unmappedPolicy);
  const unmappedSelectValue =
    !unmappedPolicy || isAllowedUnmappedPolicy(unmappedPolicy) || unsupportedLegacy
      ? unmappedPolicy || DEFAULT_UNMAPPED_POLICY
      : DEFAULT_UNMAPPED_POLICY;
  const unmappedWarning =
    warn("unmapped_policy") || (unsupportedLegacy ? UNSUPPORTED_UNMAPPED_POLICY_MESSAGE : undefined);

  return (
    <div className="space-y-3" data-testid="visual-pipeline-inspector-config-form">
      <section className="rounded-lg border border-slate-100 p-2.5 space-y-2.5">
        <div className="text-[9px] font-bold text-slate-400 uppercase tracking-wide">Transform</div>
        <VpConfigFieldShell
          fieldKey="transform_type"
          label="Transform Type"
          required
          warning={warn("transform_type")}
        >
          <select
            value={strVal(values, "transform_type")}
            onChange={patchSelect("transform_type")}
            disabled={disabled}
            className={INPUT_CLASS}
          >
            {!strVal(values, "transform_type") && <option value="">선택하세요</option>}
            {TRANSFORM_TYPE_OPTIONS.map((opt) => (
              <option key={opt} value={opt}>
                {opt}
              </option>
            ))}
          </select>
        </VpConfigFieldShell>
        <VpJsonTextareaField
          fieldKey="mapping_config"
          label="Mapping Config"
          value={values.mapping_config}
          placeholder={MAPPING_PLACEHOLDER}
          disabled={disabled}
          warning={warn("mapping_config")}
          onChange={onChange}
        />
      </section>

      <section className="rounded-lg border border-slate-100 p-2.5 space-y-2.5">
        <div className="text-[9px] font-bold text-slate-400 uppercase tracking-wide">Policy</div>
        <VpConfigFieldShell
          fieldKey="unmapped_policy"
          label="Unmapped Policy"
          help="backend WIDE_HOUR_TO_LONG 허용 정책 (FAIL_LOAD / SKIP_UNMAPPED / LOG_ONLY)"
          warning={unmappedWarning}
        >
          <select
            value={unsupportedLegacy ? unmappedPolicy : unmappedSelectValue}
            onChange={patchSelect("unmapped_policy")}
            disabled={disabled}
            className={INPUT_CLASS}
            data-testid="visual-pipeline-unmapped-policy-select"
          >
            {unsupportedLegacy && (
              <option value={unmappedPolicy} disabled>
                {`지원되지 않는 기존 값: ${unmappedPolicy}`}
              </option>
            )}
            {UNMAPPED_POLICY_SELECT_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        </VpConfigFieldShell>
        <VpJsonTextareaField
          fieldKey="hour_policy"
          label="Hour Policy"
          value={values.hour_policy}
          placeholder={HOUR_POLICY_PLACEHOLDER}
          advanced
          disabled={disabled}
          warning={warn("hour_policy")}
          onChange={onChange}
        />
      </section>

      <section className="rounded-lg border border-slate-100 p-2.5 space-y-2.5">
        <div className="text-[9px] font-bold text-slate-400 uppercase tracking-wide">Preview</div>
        <VpConfigFieldShell
          fieldKey="target_schema_preview"
          label="Target Schema Preview"
          help="미리보기 전용 필드이며 graph 저장 대상이 아닙니다."
        >
          <pre className="bg-slate-900 text-slate-100 border border-slate-700 rounded-md p-2.5 text-[10px] font-mono whitespace-pre-wrap leading-relaxed overflow-x-auto min-h-[48px]">
            {schemaPreview || "(미리보기 없음)"}
          </pre>
        </VpConfigFieldShell>
      </section>

      <div className="space-y-1 text-[9px] text-slate-500 leading-relaxed px-0.5">
        <p>설정 변경사항은 Graph 저장 시 함께 저장됩니다.</p>
        <p className="text-amber-700">
          Transform 실행 엔진과 compile 연계는 R11-S6 이후 단계에서 적용됩니다.
        </p>
      </div>
    </div>
  );
}
