/**
 * Mock 역할(Role) 기반 UI 권한 훅
 *
 * 실제 인증 기능이 아닙니다. 로그인, JWT, 세션, SSO, 사용자 관리는 구현하지 않으며,
 * `VITE_USER_ROLE` 환경 변수로 버튼 활성/비활성·권한 없음 Modal 등 UI 권한 표현만
 * 개발·시연·화면 검증용으로 확인합니다.
 *
 * 추후 Auth Provider 또는 발주기관 SSO/IAM 연계 시 이 훅(또는 Role Context)을
 * 실제 인증·권한 체계로 교체합니다. 백엔드 API 권한 검증은 1차 범위에 포함되지 않습니다.
 */
export type MockUserRole = "ADMIN" | "OPERATOR" | "VIEWER";

/** @deprecated MockUserRole과 동일. 기존 import 호환용 */
export type UserRole = MockUserRole;

/** 빌드/실행 시점에 주입되는 Mock 권한값 (미설정 시 VIEWER) */
const MOCK_ROLE: MockUserRole =
  (import.meta.env.VITE_USER_ROLE as MockUserRole) || "VIEWER";

export function useRole() {
  const canEdit = MOCK_ROLE !== "VIEWER";
  const canDelete = MOCK_ROLE === "ADMIN";
  const canRunPipeline = MOCK_ROLE !== "VIEWER";
  /** Admin Ops UI (R11-S7-12) — mock menu/page gate only, not real auth */
  const canViewVpOps = MOCK_ROLE === "ADMIN";

  return {
    /** Mock 권한값 (실제 사용자 역할 아님) */
    role: MOCK_ROLE,
    canEdit,
    canDelete,
    canRunPipeline,
    canViewVpOps,
  };
}
