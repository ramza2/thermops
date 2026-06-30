import type { FeatureNameValidation, FeatureRegistrationStatus } from "@/types/featureRegistration";
import type { FeatureRegistryItem } from "@/types/featureRegistry";

export const FEATURE_USAGE_STEPS = `신규 Feature를 학습/예측에 사용하려면 다음 단계를 완료해야 합니다.

1. Feature 메타데이터 등록
2. 코드 기반 계산 로직 구현
3. Feature Registry 등록
4. Feature Set에 포함
5. Feature 생성 실행
6. Feature 품질 검증
7. 학습 설정에서 해당 Feature Set 사용

현재 화면에서 등록하는 것은 1번 단계입니다.
2~3번이 완료되지 않은 Feature는 자동 계산되지 않습니다.`;

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
      return "Registry 등록";
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
  "공식 템플릿 Feature Set에는 계산 가능한 Registry Feature만 추가할 수 있습니다. Catalog-only 또는 Legacy Feature는 사용자 정의 Feature Set에서만 실험적으로 사용할 수 있습니다.";

export const CATALOG_ONLY_WARNING_MSG =
  "이 Feature는 카탈로그에만 등록되어 있으며 현재 계산 로직이 없습니다. Feature 생성 시 값이 생성되지 않아 Build WARNING 또는 Feature Quality 실패가 발생할 수 있습니다.";

export const LEGACY_ALIAS_WARNING_MSG = (name: string, recommended: string) =>
  `이 Feature명(${name})은 레거시 별칭입니다. 신규 Feature Set에는 공식명 ${recommended}을 사용하세요.`;

export const FEATURE_QUALITY_REGISTRATION_HINT =
  "Catalog-only 또는 Legacy Feature가 Feature Set에 포함되면 Feature Build에서 값이 생성되지 않거나 Feature Quality에서 missing key로 표시될 수 있습니다.";

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
