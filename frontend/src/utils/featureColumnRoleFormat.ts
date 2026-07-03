import type { ColumnRoleCode } from "@/types/featureColumnRoles";

const FALLBACK_LABELS: Record<string, string> = {
  ENTITY_KEY: "개체 키",
  TIME_KEY: "시간 키",
  TARGET: "예측 대상",
  NUMERIC_INPUT: "수치 입력",
  CATEGORICAL_INPUT: "범주 입력",
  BOOLEAN_INPUT: "불리언 입력",
  JOIN_KEY: "조인 키",
  EXCLUDE: "제외",
  ID: "식별자",
  TEXT: "텍스트",
  LOCATION: "위치",
  DATETIME: "날짜/시간",
  MEASURE: "측정값",
};

export function roleLabel(code: string | null | undefined, codes?: ColumnRoleCode[]): string {
  if (!code) return "미지정";
  const found = codes?.find((c) => c.code === code);
  return found?.label ?? FALLBACK_LABELS[code] ?? code;
}

export function roleBadgeClass(code: string | null | undefined): string {
  if (!code) return "text-slate-500 bg-slate-50 border-slate-200";
  switch (code) {
    case "ENTITY_KEY":
      return "text-violet-800 bg-violet-50 border-violet-200";
    case "TIME_KEY":
      return "text-blue-800 bg-blue-50 border-blue-200";
    case "TARGET":
      return "text-rose-800 bg-rose-50 border-rose-200";
    case "NUMERIC_INPUT":
    case "MEASURE":
      return "text-emerald-800 bg-emerald-50 border-emerald-200";
    case "CATEGORICAL_INPUT":
      return "text-amber-800 bg-amber-50 border-amber-200";
    case "BOOLEAN_INPUT":
      return "text-cyan-800 bg-cyan-50 border-cyan-200";
    case "EXCLUDE":
    case "ID":
      return "text-slate-600 bg-slate-100 border-slate-300";
    default:
      return "text-slate-700 bg-slate-50 border-slate-200";
  }
}

export function isFeatureCandidateRole(code: string | null | undefined, codes?: ColumnRoleCode[]): boolean {
  if (!code) return false;
  const found = codes?.find((c) => c.code === code);
  return found?.feature_candidate ?? ["NUMERIC_INPUT", "CATEGORICAL_INPUT", "BOOLEAN_INPUT", "MEASURE", "DATETIME"].includes(code);
}

export const COLUMN_ROLE_HELP =
  "컬럼 역할은 변수 생성 규칙 작성 시 각 컬럼의 의미(시간, 기준 키, 예측 대상 등)를 지정하는 선택 정보입니다. 매핑 수정 화면에서 드롭다운으로 지정합니다.";

export const COLUMN_ROLE_INFERENCE_NOTE =
  "자동 추론은 제안일 뿐입니다. 역할을 확인한 뒤 「컬럼 역할 저장」으로 확정하세요.";
