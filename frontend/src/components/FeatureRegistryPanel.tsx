import type { ReactNode } from "react";
import type { FeatureRegistryItem } from "@/types/featureRegistry";
import {
  formatCalcMethod,
  formatLeakageSafe,
  formatList,
  formatLookbackHours,
  formatSourceDataSummary,
} from "@/utils/featureRegistryFormat";

export function CalcMemoBadge() {
  return (
    <span className="inline-flex px-1.5 py-0.5 rounded text-[10px] font-medium bg-slate-100 text-slate-500 shrink-0">
      설명용
    </span>
  );
}

export function CalcMemoText({ expression }: { expression: string | null | undefined }) {
  if (!expression) return <span className="text-slate-400">-</span>;
  return (
    <span className="inline-flex flex-wrap items-center gap-1.5">
      <span className="font-mono text-xs break-all">{expression}</span>
      <CalcMemoBadge />
    </span>
  );
}

interface FeatureRegistryPanelProps {
  registry?: FeatureRegistryItem | null;
  catalogCalcExpression?: string | null;
  showUnregistered?: boolean;
}

export function FeatureRegistryPanel({
  registry,
  catalogCalcExpression,
  showUnregistered = true,
}: FeatureRegistryPanelProps) {
  if (!registry) {
    if (!showUnregistered) return null;
    return (
      <div className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900 space-y-1">
        <p className="font-medium">Registry 미등록</p>
        <p className="text-xs text-amber-800">
          메타데이터만 등록된 Feature입니다. 실제 생성 로직이 없을 수 있습니다.
        </p>
        {catalogCalcExpression && (
          <p className="text-xs pt-1">
            카탈로그 계산식 메모: <CalcMemoText expression={catalogCalcExpression} />
          </p>
        )}
      </div>
    );
  }

  const rows: { label: string; value: ReactNode }[] = [
    { label: "표시명", value: registry.display_name || registry.feature_name },
    { label: "그룹", value: registry.feature_group || "-" },
    { label: "유형", value: registry.feature_type },
    { label: "계산 방식", value: formatCalcMethod(registry.calc_method) },
    {
      label: "계산식 메모",
      value: <CalcMemoText expression={registry.calc_expression || catalogCalcExpression} />,
    },
    { label: "입력 데이터", value: formatSourceDataSummary(registry) },
    { label: "시간 기준", value: registry.time_key || "-" },
    { label: "파티션", value: formatList(registry.partition_keys) },
    { label: "Lookback", value: formatLookbackHours(registry.lookback_hours) },
    { label: "누수 방지", value: formatLeakageSafe(registry.leakage_safe) },
  ];

  if (registry.description) {
    rows.push({ label: "설명", value: registry.description });
  }

  return (
    <dl className="grid grid-cols-1 sm:grid-cols-2 gap-x-4 gap-y-2 text-sm">
      {rows.map(({ label, value }) => (
        <div key={label} className="contents">
          <dt className="text-slate-500 text-xs">{label}</dt>
          <dd className="text-slate-800 mb-2 sm:mb-0">{value}</dd>
        </div>
      ))}
    </dl>
  );
}
