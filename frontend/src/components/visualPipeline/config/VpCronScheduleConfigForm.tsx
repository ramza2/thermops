import type { ChangeEvent } from "react";
import type {
  VisualPipelineComponentConfigSchema,
  VisualPipelineNodeConfigValues,
} from "@/types/visualPipeline";
import { VpConfigFieldShell } from "@/components/visualPipeline/config/VpConfigFieldShell";

const INPUT_CLASS =
  "h-8 px-2.5 text-xs border border-slate-300 rounded-md w-full focus:outline-none focus:ring-1 focus:ring-blue-500 bg-white disabled:bg-slate-50 disabled:text-slate-400";

const TIMEZONE_OPTIONS = ["Asia/Seoul", "UTC", "Asia/Tokyo", "America/Los_Angeles"] as const;

const CRON_SOFT_WARNING =
  "일반적인 CRON은 5개 필드(분 시 일 월 요일)로 구성됩니다. 저장은 가능하며 S5-5 검증에서 확인될 수 있습니다.";

export type VpCronScheduleConfigFormProps = {
  values: VisualPipelineNodeConfigValues;
  schema?: VisualPipelineComponentConfigSchema | null;
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

function numVal(values: VisualPipelineNodeConfigValues, key: string, fallback: number): number {
  const v = values[key];
  if (typeof v === "number" && Number.isFinite(v)) return v;
  if (typeof v === "string" && v.trim() !== "" && Number.isFinite(Number(v))) return Number(v);
  return fallback;
}

/** Convert ISO-like / stored string to datetime-local value (YYYY-MM-DDTHH:mm). */
function toDatetimeLocal(value: unknown): string {
  if (value == null || value === "") return "";
  const s = String(value);
  if (/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}/.test(s)) return s.slice(0, 16);
  return s;
}

function cronFivePartWarning(expr: string): string | undefined {
  const trimmed = expr.trim();
  if (!trimmed) return undefined;
  const parts = trimmed.split(/\s+/);
  if (parts.length !== 5) return CRON_SOFT_WARNING;
  return undefined;
}

export function VpCronScheduleConfigForm({ values, onChange, disabled }: VpCronScheduleConfigFormProps) {
  const cronExpression = strVal(values, "cron_expression");
  const retryEnabled = boolVal(values, "retry_enabled_yn", false);
  const cronWarning = cronFivePartWarning(cronExpression);

  const patchText = (key: string) => (e: ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    const raw = e.target.value;
    onChange({ [key]: raw === "" ? undefined : raw });
  };

  const patchNumber = (key: string, min: number) => (e: ChangeEvent<HTMLInputElement>) => {
    const raw = e.target.value;
    if (raw === "") {
      onChange({ [key]: undefined });
      return;
    }
    const n = Number(raw);
    if (!Number.isFinite(n)) return;
    onChange({ [key]: Math.max(min, Math.trunc(n)) });
  };

  return (
    <div className="space-y-3" data-testid="visual-pipeline-inspector-config-form">
      <section className="rounded-lg border border-slate-100 p-2.5 space-y-2.5">
        <div className="text-[9px] font-bold text-slate-400 uppercase tracking-wide">Schedule</div>
        <VpConfigFieldShell fieldKey="schedule_type" label="Schedule Type" required>
          <select
            value="CRON"
            disabled
            className={INPUT_CLASS}
            onChange={() => onChange({ schedule_type: "CRON" })}
          >
            <option value="CRON">CRON</option>
          </select>
        </VpConfigFieldShell>
        <VpConfigFieldShell
          fieldKey="cron_expression"
          label="Cron Expression"
          required
          help="예: 0 6 * * * — 매일 06:00"
          warning={cronWarning}
        >
          <input
            type="text"
            value={cronExpression}
            onChange={patchText("cron_expression")}
            placeholder="0 6 * * *"
            disabled={disabled}
            className={INPUT_CLASS}
          />
        </VpConfigFieldShell>
        <VpConfigFieldShell fieldKey="timezone" label="Timezone" required>
          <select
            value={strVal(values, "timezone") || "Asia/Seoul"}
            onChange={patchText("timezone")}
            disabled={disabled}
            className={INPUT_CLASS}
          >
            {TIMEZONE_OPTIONS.map((opt) => (
              <option key={opt} value={opt}>
                {opt}
              </option>
            ))}
          </select>
        </VpConfigFieldShell>
      </section>

      <section className="rounded-lg border border-slate-100 p-2.5 space-y-2.5">
        <div className="text-[9px] font-bold text-slate-400 uppercase tracking-wide">Window</div>
        <VpConfigFieldShell fieldKey="start_at" label="Start At">
          <input
            type="datetime-local"
            value={toDatetimeLocal(values.start_at)}
            onChange={patchText("start_at")}
            disabled={disabled}
            className={INPUT_CLASS}
          />
        </VpConfigFieldShell>
        <VpConfigFieldShell fieldKey="end_at" label="End At">
          <input
            type="datetime-local"
            value={toDatetimeLocal(values.end_at)}
            onChange={patchText("end_at")}
            disabled={disabled}
            className={INPUT_CLASS}
          />
        </VpConfigFieldShell>
        <VpConfigFieldShell
          fieldKey="active_yn"
          label="Active"
          help="S5 단계에서는 저장값만 반영하며 실제 스케줄 활성화는 S6 이후입니다."
        >
          <label className="inline-flex items-center gap-2 text-[11px] text-slate-600">
            <input
              type="checkbox"
              checked={boolVal(values, "active_yn", false)}
              onChange={(e) => onChange({ active_yn: e.target.checked })}
              disabled={disabled}
              className="rounded border-slate-300"
            />
            활성 (저장만)
          </label>
        </VpConfigFieldShell>
      </section>

      <section className="rounded-lg border border-slate-100 p-2.5 space-y-2.5">
        <div className="text-[9px] font-bold text-slate-400 uppercase tracking-wide">Retry</div>
        <VpConfigFieldShell fieldKey="retry_enabled_yn" label="Retry Enabled">
          <label className="inline-flex items-center gap-2 text-[11px] text-slate-600">
            <input
              type="checkbox"
              checked={retryEnabled}
              onChange={(e) => onChange({ retry_enabled_yn: e.target.checked })}
              disabled={disabled}
              className="rounded border-slate-300"
            />
            재시도 사용
          </label>
        </VpConfigFieldShell>
        <VpConfigFieldShell fieldKey="max_retry_count" label="Max Retry Count">
          <input
            type="number"
            min={0}
            value={numVal(values, "max_retry_count", 0)}
            onChange={patchNumber("max_retry_count", 0)}
            disabled={disabled || !retryEnabled}
            className={INPUT_CLASS}
          />
        </VpConfigFieldShell>
        <VpConfigFieldShell fieldKey="retry_interval_minutes" label="Retry Interval (minutes)">
          <input
            type="number"
            min={1}
            value={numVal(values, "retry_interval_minutes", 10)}
            onChange={patchNumber("retry_interval_minutes", 1)}
            disabled={disabled || !retryEnabled}
            className={INPUT_CLASS}
          />
        </VpConfigFieldShell>
      </section>

      <div className="space-y-1 text-[9px] text-slate-500 leading-relaxed px-0.5">
        <p>설정 변경사항은 Graph 저장 시 함께 저장됩니다.</p>
        <p className="text-amber-700">
          S5 단계에서는 스케줄 설정만 저장하며 실제 활성화는 R11-S6 이후 단계에서 적용됩니다.
        </p>
      </div>
    </div>
  );
}
