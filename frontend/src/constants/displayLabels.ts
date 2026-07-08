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
  predictionEntities: "예측 대상",
  externalCodeMappings: "외부 코드 매핑",
  standardDatasets: "표준 데이터셋",
  dataMappings: "데이터 매핑",
  dataQuality: "데이터 품질",
  features: "학습 변수",
  featureSets: "변수 구성",
  featureSetDetail: "변수 구성 상세",
  featureRecipes: "변수 생성 규칙",
  featureRecipeBuilder: "변수 생성 규칙 작성",
  datasetVersions: "학습 데이터 버전",
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
  dataLoadSchedules: "데이터 적재 일정",
  systemConfig: "시스템 설정",
} as const;

export const PAGE_DESCRIPTIONS = {
  dashboard: "전체 운영 현황과 최근 예측·모델 상태를 한눈에 확인합니다.",
  dataSources: "학습과 예측에 사용할 원천 데이터의 위치를 등록합니다. REST API, CSV, 데이터베이스 등을 연결할 수 있습니다.",
  predictionEntities: "예측을 수행할 지점·설비·지역 등의 기준정보와 위치, 기상 매핑을 관리합니다.",
  externalCodeMappings: "외부 API나 파일에서 들어오는 코드값을 THERMOps 내부 예측 대상, 관측소, 표준 코드와 연결합니다.",
  standardDatasets: "THERMOps 안에서 사용할 데이터 구조를 정의하고 내부 테이블을 생성합니다.",
  dataMappings: "원천 데이터의 컬럼을 내부 표준 데이터셋의 컬럼에 연결합니다.",
  dataQuality: "적재된 데이터의 결측·이상·정합성을 점검합니다.",
  features: "모델 학습에 사용할 입력 변수와 계산 정보를 확인합니다.",
  featureSets: "모델 학습에 사용할 변수 묶음을 구성합니다.",
  featureSetDetail: "변수 구성에 포함할 학습 변수와 생성 규칙을 관리합니다.",
  featureRecipes: "원천 컬럼을 이용해 새로운 학습 변수를 만드는 규칙을 관리합니다.",
  featureRecipeBuilder: "변수 생성 규칙을 작성·검증·미리보기합니다. 미리보기 결과는 저장되지 않습니다.",
  datasetVersions:
    "변수 생성 작업으로 만들어진 학습용 데이터 버전의 역할·상태를 관리하고 자동 선택 정책을 확인합니다.",
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
  dataLoadSchedules: "REST API 작업의 적재 실행을 정기 일정으로 등록하고 실행 이력과 실패 여부를 관리합니다.",
  systemConfig: "공통 코드와 시스템 운영 설정을 관리합니다.",
} as const;

export const EMPTY_MESSAGES = {
  dataSources:
    "등록된 데이터 소스가 없습니다. 표준 데이터셋을 먼저 정의한 뒤 원천 데이터 위치를 등록하면 매핑 작업을 더 쉽게 진행할 수 있습니다.",
  apiConnectorOperations:
    "등록된 REST API 작업이 없습니다. 외부 API의 endpoint와 요청 파라미터를 등록하면 표준 데이터셋으로 적재할 수 있습니다.",
  predictionEntities:
    "등록된 예측 대상이 없습니다. 열수요 지점, 설비, 지역 등 예측을 수행할 기준 대상을 먼저 등록하세요.",
  externalCodeMappings:
    "등록된 외부 코드 매핑이 없습니다. 외부 API의 지점코드·관측소코드 등을 내부 예측 대상이나 관측소와 연결하세요.",
  unmappedExternalCodes:
    "수집된 미매핑 코드가 없습니다. 코드 변환에 실패한 외부 코드가 여기에 표시됩니다.",
  standardDatasets:
    "등록된 표준 데이터셋이 없습니다. 학습과 예측에 사용할 내부 데이터 구조를 먼저 정의하세요.",
  dataMappings:
    "등록된 데이터 매핑이 없습니다. 표준 데이터셋과 데이터 소스를 만든 뒤 원천 컬럼을 적재 대상 컬럼에 연결하세요.",
  features:
    "등록된 학습 변수가 없습니다. 변수 정보를 등록하거나 변수 생성 규칙으로 새 변수를 만드세요.",
  featureSets:
    "등록된 변수 구성이 없습니다. 모델 학습에 사용할 변수 묶음을 만들어보세요.",
  featureRecipes:
    "등록된 변수 생성 규칙이 없습니다. 원천 컬럼을 이용해 학습 변수를 만드는 규칙을 추가하세요.",
  datasetVersions:
    "생성된 학습 데이터 버전이 없습니다. 변수 생성 작업을 실행하면 모델 학습에 사용할 데이터 버전이 생성됩니다.",
  trainingJobs:
    "등록된 학습 작업이 없습니다. 데이터셋과 변수 구성을 준비한 뒤 모델 학습을 시작하세요.",
  predictionJobs:
    "등록된 예측 작업이 없습니다. 학습된 모델을 선택해 예측을 실행하세요.",
  pipelineBuilder:
    "등록된 작업 흐름이 없습니다. 데이터 적재부터 예측까지의 실행 순서를 구성하세요.",
  dataLoadSchedules:
    "등록된 데이터 적재 일정이 없습니다. REST API 작업을 선택해 정기 적재 일정을 등록하세요.",
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
  datasetVersionPolicy:
    "일부 생성 버전은 자동 학습/예측 선택에서 제외됩니다. 대표 버전은 자동 선택 시 우선 사용됩니다. 보관된 버전은 자동 선택되지 않습니다.",
  standardDataset:
    "데이터 적재·매핑의 기준이 되는 논리 데이터 구조와 내부 테이블 정의입니다.",
  serviceKeyEncoding:
    "공공데이터포털 serviceKey는 Decoding 키 입력을 권장합니다. THERMOps가 호출 시 한 번만 URL 인코딩합니다. 이미 Encoding 키를 넣으면 이중 인코딩될 수 있습니다.",
  secretMasking:
    "인증 키는 저장 후 마스킹된 값만 표시됩니다. 호출 이력·미리보기 URL에도 원문이 노출되지 않습니다.",
  responseItemPath:
    "응답 JSON에서 row 목록이 위치한 dot 경로를 지정합니다. 예: response.body.items.item",
  forecastGrid:
    "단기예보 격자(nx/ny)는 기상청 단기예보 API 호출에 필요한 위치 기준입니다.",
  observationStation:
    "ASOS 관측소는 과거 학습용 기상 관측 데이터를 연결할 때 사용합니다.",
  weatherMappingSplit:
    "단기예보와 ASOS는 기준이 다르므로 각각 별도로 매핑합니다.",
  gridCalcHint:
    "계산 결과는 예보 격자 기준이며 실제 운영 전 검토가 필요합니다.",
  restApiConnectorLink:
    "기상청 단기예보 API는 예측 대상의 nx/ny가 필요합니다. REST API 연결에서 API 작업을 등록한 뒤, 예측 작업 화면의 단기예보 입력 생성기 설정에서 선택해 예측 실행 시 on-demand 호출합니다.",
  restApiConnectorExternalCodeLink:
    "외부 API 응답의 지점코드, 관측소코드 등은 외부 코드 매핑 화면에서 내부 예측 대상이나 관측소와 연결할 수 있습니다.",
  externalCodeMappingIntro:
    "외부 API나 파일에서 들어오는 코드값을 THERMOps 내부 예측 대상, 관측소, 표준 코드와 연결합니다.",
  externalCodeNoAutoCreate:
    "미매핑 코드는 자동으로 내부 기준정보를 만들지 않습니다. 검토 후 내부 대상과 연결하세요.",
  externalCodeNdIdExample:
    "예: 열수요 API의 ND_ID는 source_system=HEAT_DEMAND_API, external_code_group=NODE로 예측 대상(PREDICTION_ENTITY)과 연결합니다.",
  wideHourTransform:
    "열수요 API의 HTDND_AMNT_1HR~24HR 같은 시간대별 컬럼을 행 단위 시계열(measured_at, heat_demand)로 변환합니다.",
  wideHourTimestampPolicy:
    "1HR/24HR 시간 해석은 기관 API 정의에 따라 다를 수 있습니다. 운영 적용 전 01:00 시점인지 00:00~01:00 구간인지 확인하세요.",
  wideHourUnmapped:
    "ND_ID는 외부 코드 매핑에서 내부 예측 대상과 연결되어야 합니다. 미매핑 코드는 자동으로 예측 대상을 만들지 않습니다.",
  asosWeatherTransform:
    "ASOS 관측 기상은 과거 학습용 기상 데이터입니다. 예측 시점의 미래 기상은 단기예보 on-demand 입력으로 처리합니다.",
  forecastOnDemand:
    "과거 학습용 ASOS 관측과 달리, 예측 실행 시점에 기상청 단기예보 API를 호출해 미래 기상 입력을 생성합니다. 결과는 예측 작업 단위 기상 입력 스냅샷으로 저장되어 재현할 수 있습니다.",
  dataLoadSchedulerIntro:
    "스케줄러는 REST API 작업의 load-run을 정해진 시간에 실행하기 위한 설정입니다. serviceKey 등 인증 정보는 REST API 연결 Credential을 사용합니다.",
  dataLoadSchedulerHelp1:
    "R10-S6에서는 run-due API를 제공하며, 실제 운영에서는 cron/worker/Airflow에서 이 API를 호출할 수 있습니다.",
  dataLoadSchedulerHelp2:
    "단기예보 on-demand 입력(R10-S5)은 스케줄 대상이 아닙니다. 예측 실행 시점 Provider로 유지됩니다.",
  dataLoadSchedulerHelp3:
    "스케줄 실행 이력에는 인증 키 원문이 저장되지 않으며, 실행 파라미터 템플릿만 마스킹되어 보관됩니다.",
  dataLoadWriteModeHelp:
    "적재 방식은 신규 행 추가, 중복 제외, 있으면 갱신·없으면 추가를 지원합니다. 재실행 시 동일 키는 정책에 따라 제외되거나 갱신됩니다.",
  forecastProviderHint:
    "데이터 소스에 등록한 기상청 단기예보 API 작업을 선택하면 예측 실행 시 on-demand로 호출됩니다. serviceKey는 마스킹되어 표시됩니다.",
  forecastEntityReadiness:
    "단기예보 입력은 forecast_ready(격자 nx/ny 매핑 완료) 예측 대상만 사용할 수 있습니다. nx/ny가 없으면 예측 화면에서 단기예보 입력을 사용할 수 없습니다.",
  calendarTransform:
    "Calendar 변환은 공휴일/특일 응답을 날짜 기준정보로 정규화합니다.",
  calendarHourTransform:
    "날짜 기준정보를 시간 단위(calendar_hour) 행으로 확장합니다. hour_start~hour_end 범위를 지정하세요.",
  connectorCleanSeedHint:
    "운영 seed에는 예시 API/데이터가 포함되지 않으므로 표준 데이터셋과 REST API 작업을 먼저 등록하세요.",
  asosStationPrerequisite:
    "ASOS API 적재 전 예측 대상 > ASOS 관측소 기준정보를 등록하세요. 미등록 관측소 코드는 경고 또는 적재 중단 정책을 따릅니다.",
  calendarMultiOperationHint:
    "Calendar/특일 API는 하나의 데이터 소스 아래 공휴일·국경일·기념일·24절기·잡절 등 여러 API 작업으로 구성할 수 있습니다.",
  externalCodeStationHint:
    "관측소 코드 또는 특일 유형 코드가 필요한 경우 외부 코드 매핑을 사용할 수 있습니다.",
  externalCodeStableId:
    "외부 코드가 변경되어도 내부 예측 대상 ID를 유지할 수 있도록 매핑을 사용합니다.",
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

export const DATASET_VERSION_ROLE_LABELS: Record<string, string> = {
  PRIMARY: "대표",
  CANDIDATE: "후보",
  PARTIAL: "일부 생성",
  TEMPORARY: "임시",
  ARCHIVED: "보관됨",
};

export const DATASET_VERSION_STATUS_LABELS: Record<string, string> = {
  BUILD_SUCCESS: "생성 성공",
  BUILD_WARNING: "경고 있음",
  BUILD_FAILED: "생성 실패",
  PARTIAL: "일부 생성",
  TRAINING_READY: "학습 가능",
  SERVING_READY: "예측 사용 가능",
  ARCHIVED: "보관됨",
};

export const BUILD_SCOPE_LABELS: Record<string, string> = {
  FULL: "전체 생성",
  PARTIAL: "일부 생성",
  PREVIEW: "미리보기",
  UNKNOWN: "확인 필요",
};

export function datasetVersionRoleLabel(code?: string | null): string {
  if (!code) return "-";
  return DATASET_VERSION_ROLE_LABELS[code] ?? code;
}

export function datasetVersionStatusLabel(code?: string | null): string {
  if (!code) return "-";
  return DATASET_VERSION_STATUS_LABELS[code] ?? code;
}

export function buildScopeLabel(code?: string | null): string {
  if (!code) return "-";
  return BUILD_SCOPE_LABELS[code] ?? code;
}

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
