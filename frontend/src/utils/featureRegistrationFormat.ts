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
