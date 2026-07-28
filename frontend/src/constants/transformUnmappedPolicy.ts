/**
 * R11-S8-9-5 / B14 — Transform unmapped_policy aligned with backend WIDE_HOUR_TO_LONG.
 * Shared by Studio Transform Inspector and API Connector Wizard.
 */

export const UNMAPPED_POLICY_VALUES = ["FAIL_LOAD", "SKIP_UNMAPPED", "LOG_ONLY"] as const;

export type UnmappedPolicyValue = (typeof UNMAPPED_POLICY_VALUES)[number];

export const DEFAULT_UNMAPPED_POLICY: UnmappedPolicyValue = "FAIL_LOAD";

/** Select options (value = backend enum, label = Wizard wording). */
export const UNMAPPED_POLICY_SELECT_OPTIONS: ReadonlyArray<{ value: UnmappedPolicyValue; label: string }> = [
  { value: "FAIL_LOAD", label: "FAIL_LOAD (적재 중단)" },
  { value: "SKIP_UNMAPPED", label: "SKIP_UNMAPPED (해당 item skip)" },
  { value: "LOG_ONLY", label: "LOG_ONLY (entity 없이 변환)" },
];

/** Legacy Studio values that safely map to backend enums (C안). KEEP is not mapped. */
export const LEGACY_UNMAPPED_POLICY_AUTO_MAP: Readonly<Record<string, UnmappedPolicyValue>> = {
  ERROR: "FAIL_LOAD",
  DROP: "SKIP_UNMAPPED",
};

export const UNSUPPORTED_LEGACY_UNMAPPED_POLICIES = new Set(["KEEP"]);

export function isAllowedUnmappedPolicy(value: string): value is UnmappedPolicyValue {
  return (UNMAPPED_POLICY_VALUES as readonly string[]).includes(value);
}

export function isUnsupportedLegacyUnmappedPolicy(value: string): boolean {
  return UNSUPPORTED_LEGACY_UNMAPPED_POLICIES.has(value);
}

/**
 * Remap ERROR/DROP; leave KEEP and unknown as-is for Inspector reselect.
 * Empty/null left unchanged (schema default FAIL_LOAD fills later).
 */
export function remapLegacyUnmappedPolicy(raw: unknown): unknown {
  if (raw === undefined || raw === null || raw === "") return raw;
  const s = String(raw);
  if (isAllowedUnmappedPolicy(s)) return s;
  const mapped = LEGACY_UNMAPPED_POLICY_AUTO_MAP[s];
  if (mapped) return mapped;
  return s;
}

export const UNSUPPORTED_UNMAPPED_POLICY_MESSAGE =
  "현재 값 KEEP은 더 이상 지원되지 않는 미매핑 정책입니다. FAIL_LOAD / SKIP_UNMAPPED / LOG_ONLY 중 하나를 선택해 주세요.";
