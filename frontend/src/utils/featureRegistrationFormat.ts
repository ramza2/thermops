import type { FeatureNameValidation, FeatureRegistrationStatus } from "@/types/featureRegistration";
import type { FeatureRegistryItem } from "@/types/featureRegistry";
import { FEATURE_USAGE_STEPS } from "@/constants/displayLabels";

export { FEATURE_USAGE_STEPS };

export function registrationStatusLabel(status: FeatureRegistrationStatus): string {
  switch (status) {
    case "COMPUTABLE":
      return "계산 가능";
    case "CATALOG_ONLY":
      return "카탈로그 전용";
    case "LEGACY_ALIAS":
      return "레거시";
    case "DUPLICATE":
      return "중복";
    case "REGISTERED_IN_REGISTRY":
      return "등록 정보 있음";
    case "TEMPLATE_PUBLISHED":
      return "규칙 발행됨";
    case "TEMPLATE_BUILD_SUPPORTED":
      return "규칙 생성 지원";
    default:
      return "미등록";
  }
}

export function registrationStatusClass(status: FeatureRegistrationStatus): string {
  switch (status) {
    case "COMPUTABLE":
      return "bg-emerald-50 text-emerald-800 border-emerald-200";
    case "CATALOG_ONLY":
      return "bg-amber-50 text-amber-800 border-amber-200";
    case "LEGACY_ALIAS":
      return "bg-orange-50 text-orange-800 border-orange-200";
    case "DUPLICATE":
      return "bg-red-50 text-red-800 border-red-200";
    case "REGISTERED_IN_REGISTRY":
      return "bg-sky-50 text-sky-800 border-sky-200";
    case "TEMPLATE_PUBLISHED":
      return "bg-violet-50 text-violet-800 border-violet-200";
    case "TEMPLATE_BUILD_SUPPORTED":
      return "bg-emerald-50 text-emerald-800 border-emerald-200";
    default:
      return "bg-slate-50 text-slate-600 border-slate-200";
  }
}

export function inferRegistrationStatus(
  featureName: string,
  registry?: FeatureRegistryItem,
): FeatureRegistrationStatus {
  if (!registry) return "CATALOG_ONLY";
  return "COMPUTABLE";
}

export function validationBlocksRegistration(v: FeatureNameValidation | null): boolean {
  if (!v) return false;
  return v.status === "DUPLICATE" || v.status === "LEGACY_ALIAS";
}

export function validationWarnsRegistration(v: FeatureNameValidation | null): boolean {
  if (!v) return false;
  return v.status === "CATALOG_ONLY" && !v.catalog_registered;
}

export const TPL_FEATURE_BLOCK_MSG =
  "공식 템플릿 변수 구성에는 계산 가능한 등록 변수만 추가할 수 있습니다. 카탈로그 전용·레거시 변수는 사용자 정의 변수 구성에서만 실험적으로 사용할 수 있습니다.";

export const CATALOG_ONLY_WARNING_MSG =
  "이 변수는 카탈로그에만 등록되어 있으며 현재 계산 로직이 없습니다. 변수 생성 시 값이 생성되지 않아 경고 또는 변수 품질 검증 실패가 발생할 수 있습니다.";

export const LEGACY_ALIAS_WARNING_MSG = (name: string, recommended: string) =>
  `이 변수명(${name})은 레거시 별칭입니다. 신규 변수 구성에는 공식명 ${recommended}을 사용하세요.`;

export const FEATURE_QUALITY_REGISTRATION_HINT =
  "카탈로그 전용·레거시 변수가 변수 구성에 포함되면 변수 생성에서 값이 생성되지 않거나 변수 품질에서 누락으로 표시될 수 있습니다.";

export const LEGACY_REPLACE_HINT =
  "이 변수 구성에는 레거시 변수명이 포함되어 있습니다. 신규 변수 구성과 학습·예측에는 공식 변수명을 사용하는 것이 권장됩니다.";

export const LEGACY_REPLACE_AFTER_HINT =
  "공식명으로 대체한 뒤에는 변수 생성과 변수 품질 검증을 다시 실행하는 것이 좋습니다.";

export type FeatureListFilter = "all" | "computable" | "catalog_only" | "legacy";

export function matchesFeatureListFilter(
  reg: FeatureNameValidation | undefined,
  filter: FeatureListFilter,
): boolean {
  if (filter === "all") return true;
  if (!reg) return filter === "catalog_only";
  if (filter === "computable") return reg.computable;
  if (filter === "catalog_only") return reg.status === "CATALOG_ONLY" || reg.status === "DUPLICATE";
  if (filter === "legacy") return reg.status === "LEGACY_ALIAS";
  return true;
}

export function registrationStatusLabelExtended(meta: {
  registration_status?: string;
  status?: string;
  recommended_name?: string | null;
}): string {
  const status = (meta.registration_status ?? meta.status) as FeatureRegistrationStatus | undefined;
  if (!status) return "미등록";
  if (status === "LEGACY_ALIAS" && meta.recommended_name) {
    return `레거시: ${meta.recommended_name} 권장`;
  }
  return registrationStatusLabel(status);
}

export function isNonComputableRegistration(reg?: FeatureNameValidation | null): boolean {
  if (!reg) return true;
  return !reg.computable || reg.status === "LEGACY_ALIAS" || reg.status === "CATALOG_ONLY";
}
