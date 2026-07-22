import type { ChangeEvent } from "react";
import type {
  VisualPipelineComponentConfigSchema,
  VisualPipelineNodeConfigValues,
} from "@/types/visualPipeline";
import { VpConfigFieldShell } from "@/components/visualPipeline/config/VpConfigFieldShell";
import { VpJsonTextareaField } from "@/components/visualPipeline/config/VpJsonTextareaField";

const INPUT_CLASS =
  "h-8 px-2.5 text-xs border border-slate-300 rounded-md w-full focus:outline-none focus:ring-1 focus:ring-blue-500 bg-white disabled:bg-slate-50 disabled:text-slate-400";

export type VpRestApiSourceConfigFormProps = {
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

export function VpRestApiSourceConfigForm({
  values,
  fieldWarnings,
  onChange,
  disabled,
}: VpRestApiSourceConfigFormProps) {
  const patchText = (key: string) => (e: ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    const raw = e.target.value;
    onChange({ [key]: raw === "" ? undefined : raw });
  };
  const warn = (key: string) => fieldWarnings?.[key];

  return (
    <div className="space-y-3" data-testid="visual-pipeline-inspector-config-form">
      <section className="rounded-lg border border-slate-100 p-2.5 space-y-2.5">
        <div className="text-[9px] font-bold text-slate-400 uppercase tracking-wide">연결</div>
        <VpConfigFieldShell
          fieldKey="data_source_id"
          label="Data Source ID"
          required
          help="REST Connector / Data Source 참조 ID"
          warning={warn("data_source_id")}
        >
          <input
            type="text"
            value={strVal(values, "data_source_id")}
            onChange={patchText("data_source_id")}
            placeholder="DS-SAMPLE"
            disabled={disabled}
            className={INPUT_CLASS}
          />
        </VpConfigFieldShell>
        <VpConfigFieldShell
          fieldKey="operation_name"
          label="Operation Name"
          required
          warning={warn("operation_name")}
        >
          <input
            type="text"
            value={strVal(values, "operation_name")}
            onChange={patchText("operation_name")}
            placeholder="sample_fetch"
            disabled={disabled}
            className={INPUT_CLASS}
          />
        </VpConfigFieldShell>
        <VpConfigFieldShell
          fieldKey="credential_ref"
          label="Credential Ref"
          help="API key/token/password 원문이 아닌 credential 참조 ID만 입력하세요."
          warning={warn("credential_ref")}
        >
          <input
            type="text"
            value={strVal(values, "credential_ref")}
            onChange={patchText("credential_ref")}
            placeholder="CRED-SAMPLE"
            disabled={disabled}
            className={INPUT_CLASS}
            autoComplete="off"
          />
        </VpConfigFieldShell>
      </section>

      <section className="rounded-lg border border-slate-100 p-2.5 space-y-2.5">
        <div className="text-[9px] font-bold text-slate-400 uppercase tracking-wide">Request</div>
        <VpConfigFieldShell
          fieldKey="endpoint_path"
          label="Endpoint Path"
          required
          warning={warn("endpoint_path")}
        >
          <input
            type="text"
            value={strVal(values, "endpoint_path")}
            onChange={patchText("endpoint_path")}
            placeholder="/api/v1/sample"
            disabled={disabled}
            className={INPUT_CLASS}
          />
        </VpConfigFieldShell>
        <VpConfigFieldShell
          fieldKey="http_method"
          label="HTTP Method"
          required
          warning={warn("http_method")}
        >
          <select
            value={strVal(values, "http_method") || "GET"}
            onChange={patchText("http_method")}
            disabled={disabled}
            className={INPUT_CLASS}
          >
            <option value="GET">GET</option>
            <option value="POST">POST</option>
          </select>
        </VpConfigFieldShell>
        <VpJsonTextareaField
          fieldKey="request_params"
          label="Request Params"
          value={values.request_params}
          placeholder={'{ "branch": "P001" }'}
          advanced
          disabled={disabled}
          warning={warn("request_params")}
          onChange={onChange}
        />
        <VpJsonTextareaField
          fieldKey="pagination"
          label="Pagination"
          value={values.pagination}
          placeholder={'{\n  "type": "NONE"\n}'}
          advanced
          disabled={disabled}
          warning={warn("pagination")}
          onChange={onChange}
        />
      </section>

      <section className="rounded-lg border border-slate-100 p-2.5 space-y-2.5">
        <div className="text-[9px] font-bold text-slate-400 uppercase tracking-wide">Response</div>
        <VpConfigFieldShell
          fieldKey="response_item_path"
          label="Response Item Path"
          help="JSON 응답에서 row array 위치 (JSONPath)"
          warning={warn("response_item_path")}
        >
          <input
            type="text"
            value={strVal(values, "response_item_path")}
            onChange={patchText("response_item_path")}
            placeholder="$.items"
            disabled={disabled}
            className={INPUT_CLASS}
          />
        </VpConfigFieldShell>
      </section>

      <div className="space-y-1 text-[9px] text-slate-500 leading-relaxed px-0.5">
        <p>설정 변경사항은 Graph 저장 시 함께 저장됩니다.</p>
        <p className="text-amber-700">비밀값은 저장하지 않고 Credential 참조만 저장하세요.</p>
      </div>
    </div>
  );
}
