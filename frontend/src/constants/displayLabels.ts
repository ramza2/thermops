/**
 * R9-S2-3 사용자 화면 표시용 용어·안내 문구.
 * 내부 API/DB 식별자는 유지하고, label·메뉴·빈 화면·도움말만 여기서 관리한다.
 */

export const APP_TAGLINE = "MLOps 운영 플랫폼";

/** 공통 lifecycle / run 상태 (화면 표시) */
export const LIFECYCLE_STATUS_LABELS: Record<string, string> = {
  DRAFT: "작성 중",
  VALIDATED: "검증 완료",
  ACTIVE: "사용 중",
  ARCHIVED: "보관됨",
  PUBLISHED: "사용 가능",
  PLANNED: "계획",
  SUCCESS: "성공",
  FAILED: "실패",
  WARNING: "경고",
  RUNNING: "실행 중",
  QUEUED: "대기",
  PENDING: "대기",
  NOT_CREATED: "미생성",
  PREVIEWED: "미리보기 완료",
  CANCELLED: "취소됨",
};

export function lifecycleStatusLabel(code?: string | null, fallback?: string): string {
  if (!code) return fallback ?? "-";
  return LIFECYCLE_STATUS_LABELS[code] ?? fallback ?? code;
}

export const MENU_GROUPS = {
  dataPrep: "데이터 준비",
  features: "학습 변수 관리",
  modelPredict: "모델 학습·예측",
  operations: "운영 모니터링",
  system: "시스템 관리",
} as const;

export const PAGE_TITLES = {
  dashboard: "대시보드",
  dataSources: "데이터 소스",
  standardDatasets: "표준 데이터셋",
  dataMappings: "데이터 매핑",
  dataQuality: "데이터 품질",
  features: "학습 변수",
  featureSets: "변수 구성",
  featureSetDetail: "변수 구성 상세",
  featureRecipes: "변수 생성 규칙",
  featureRecipeBuilder: "변수 생성 규칙 작성",
  trainingConfigs: "학습 설정",
  trainingJobs: "모델 학습",
  modelPerformance: "모델 성능 비교",
  modelRegistry: "모델 등록 목록",
  predictionJobs: "예측 작업",
  predictionResults: "예측 결과",
  predictionErrors: "예측 오차 분석",
  pipelineBuilder: "작업 흐름 구성",
  pipelineRuns: "작업 실행 이력",
  modelMonitoring: "성능 모니터링",
  driftReports: "데이터 변화 리포트",
  retrainingCandidates: "재학습 후보",
  systemConfig: "시스템 설정",
} as const;

export const PAGE_DESCRIPTIONS = {
  dashboard: "전체 운영 현황과 최근 예측·모델 상태를 한눈에 확인합니다.",
  dataSources: "학습과 예측에 사용할 원천 데이터의 위치를 등록합니다. REST API, CSV, 데이터베이스 등을 연결할 수 있습니다.",
  standardDatasets: "THERMOps 안에서 사용할 데이터 구조를 정의하고 내부 테이블을 생성합니다.",
  dataMappings: "원천 데이터의 컬럼을 내부 표준 데이터셋의 컬럼에 연결합니다.",
  dataQuality: "적재된 데이터의 결측·이상·정합성을 점검합니다.",
  features: "모델 학습에 사용할 입력 변수와 계산 정보를 확인합니다.",
  featureSets: "모델 학습에 사용할 변수 묶음을 구성합니다.",
  featureSetDetail: "변수 구성에 포함할 학습 변수와 생성 규칙을 관리합니다.",
  featureRecipes: "원천 컬럼을 이용해 새로운 학습 변수를 만드는 규칙을 관리합니다.",
  featureRecipeBuilder: "변수 생성 규칙을 작성·검증·미리보기합니다. 미리보기 결과는 저장되지 않습니다.",
  trainingConfigs: "학습에 사용할 알고리즘·기간·변수 구성 등 학습 설정을 관리합니다.",
  trainingJobs: "선택한 데이터와 변수 구성으로 예측 모델을 학습합니다.",
  modelPerformance: "학습·운영 기준으로 모델 성능 지표를 비교합니다.",
  modelRegistry: "등록된 모델 버전과 운영(대표) 모델을 관리합니다.",
  predictionJobs: "예측 실행 요청과 처리 상태를 확인합니다.",
  predictionResults: "모델이 생성한 예측값과 실제값 비교 결과를 확인합니다.",
  predictionErrors: "예측값과 실제값을 비교하여 오차를 분석합니다.",
  pipelineBuilder: "데이터 적재, 변수 생성, 모델 학습, 예측 등의 작업 순서를 구성합니다.",
  pipelineRuns: "작업 흐름이나 개별 작업이 언제 실행되었고 성공했는지 확인합니다.",
  modelMonitoring: "운영 중인 모델의 성능 지표 추이를 모니터링합니다.",
  driftReports: "학습 당시 데이터와 최근 데이터의 분포 차이를 확인합니다.",
  retrainingCandidates: "데이터 변화·성능 저하 등으로 재학습이 필요한 후보를 관리합니다.",
  systemConfig: "공통 코드와 시스템 운영 설정을 관리합니다.",
} as const;

export const EMPTY_MESSAGES = {
  dataSources:
    "등록된 데이터 소스가 없습니다. 먼저 REST API, CSV 파일 또는 데이터베이스 연결 정보를 등록하세요.",
  standardDatasets:
    "등록된 표준 데이터셋이 없습니다. 데이터 적재 대상이 될 내부 데이터 구조를 먼저 정의하세요.",
  dataMappings:
    "등록된 데이터 매핑이 없습니다. 데이터 소스와 표준 데이터셋을 만든 뒤 컬럼을 연결하세요.",
  features:
    "등록된 학습 변수가 없습니다. 변수 정보를 등록하거나 변수 생성 규칙으로 새 변수를 만드세요.",
  featureSets:
    "등록된 변수 구성이 없습니다. 모델 학습에 사용할 변수 묶음을 만들어보세요.",
  featureRecipes:
    "등록된 변수 생성 규칙이 없습니다. 원천 컬럼을 이용해 학습 변수를 만드는 규칙을 추가하세요.",
  trainingJobs:
    "등록된 학습 작업이 없습니다. 데이터셋과 변수 구성을 준비한 뒤 모델 학습을 시작하세요.",
  predictionJobs:
    "등록된 예측 작업이 없습니다. 학습된 모델을 선택해 예측을 실행하세요.",
  pipelineBuilder:
    "등록된 작업 흐름이 없습니다. 데이터 적재부터 예측까지의 실행 순서를 구성하세요.",
  pipelineRuns: "실행 이력이 없습니다. 작업 흐름 구성에서 실행하거나 개별 작업을 실행하세요.",
  generic: "데이터가 없습니다.",
} as const;

export const HELP_TEXTS = {
  columnRole:
    "각 컬럼이 모델 학습에서 어떤 역할을 하는지 지정합니다. 예: 시간 컬럼, 기준 키, 예측 대상값, 입력 변수.",
  featureRecipe:
    "원천 데이터의 컬럼을 이용해 학습에 필요한 새 변수를 만드는 규칙입니다. 예: 24시간 전 값, 7일 이동평균.",
  drift:
    "최근 데이터가 학습 당시 데이터와 얼마나 달라졌는지 확인해 재학습 필요성을 판단합니다.",
  pipeline:
    "반복되는 데이터 적재, 변수 생성, 학습, 예측 작업을 순서대로 묶어 실행하는 기능입니다.",
  datasetVersion:
    "변수 생성 작업으로 만들어진 모델 학습용 데이터 묶음입니다.",
  standardDataset:
    "데이터 적재·매핑의 기준이 되는 논리 데이터 구조와 내부 테이블 정의입니다.",
} as const;

export const FEATURE_USAGE_STEPS = `신규 학습 변수를 모델 학습·예측에 사용하려면 다음 단계를 완료해야 합니다.

1. 변수 정보 등록 (현재 화면)
2. 계산 로직 구현 또는 변수 생성 규칙 작성
3. 변수 구성에 포함
4. 변수 생성 작업 실행
5. 변수 품질 검증
6. 모델 학습에서 해당 변수 구성 사용

2~3단계가 완료되지 않은 변수는 자동으로 값이 생성되지 않을 수 있습니다.`;

export const R9_S2_3_NOTE =
  "R9-S2-3부터 화면 표시명은 일반 운영자가 이해하기 쉬운 업무 용어를 사용합니다. 내부 코드명은 상세·툴팁에 병기될 수 있습니다.";

/** 폼·테이블 필드 라벨 (내부 키는 유지) */
export const FIELD_LABELS = {
  featureSet: "변수 구성",
  featureSetId: "변수 구성 ID",
  featureSetName: "변수 구성명",
  featureName: "변수명",
  datasetVersion: "학습 데이터 버전",
  columnRole: "컬럼 역할",
  targetTable: "적재 대상 테이블",
  pipeline: "작업 흐름",
  pipelineName: "작업 흐름명",
  registry: "등록 정보",
} as const;

export const ACTION_LABELS = {
  create: "등록",
  save: "저장",
  delete: "삭제",
  validate: "검증",
  preview: "미리보기",
  run: "실행",
  retry: "다시 실행",
  refresh: "새로고침",
  open: "열기",
  newPipeline: "새 작업 흐름",
  newFeatureSet: "신규 변수 구성",
  newMapping: "새 매핑",
} as const;
