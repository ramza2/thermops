const TYPE_LABELS: Record<string, string> = {
  FULL_OPERATION: "전체 운영",
  FEATURE_BUILD: "Feature Build",
  BATCH_PREDICTION: "배치 예측",
  RETRAINING: "재학습",
};

const STATUS_LABELS: Record<string, string> = {
  DRAFT: "초안",
  VALIDATED: "검증됨",
  ACTIVE: "운영",
  ARCHIVED: "보관",
  PLANNED: "계획",
};

const NODE_TYPE_LABELS: Record<string, string> = {
  DATA_SOURCE: "데이터소스",
  DATA_MAPPING: "데이터 매핑",
  STANDARD_DATASET: "표준 데이터셋",
  FEATURE_SET: "Feature Set",
  FEATURE_BUILD: "Feature Build",
  FEATURE_QUALITY: "Feature 품질",
  MODEL_TRAINING: "모델 학습",
  MODEL_SELECTION: "모델 선택",
  BATCH_PREDICTION: "배치 예측",
  PERFORMANCE_EVAL: "성능 평가",
  DRIFT_CHECK: "Drift 점검",
  DATA_QUALITY: "데이터 품질",
  MONITORING: "모니터링",
  RETRAINING_CANDIDATE: "재학습 후보",
  APPROVAL: "승인",
  MODEL_REGISTRY: "모델 Registry",
};

export function pipelineTypeLabel(t: string): string {
  return TYPE_LABELS[t] || t;
}

export function pipelineStatusLabel(s: string): string {
  return STATUS_LABELS[s] || s;
}

export function pipelineStatusClass(s: string): string {
  switch (s) {
    case "ACTIVE":
      return "bg-emerald-100 text-emerald-800 border-emerald-200";
    case "VALIDATED":
      return "bg-blue-100 text-blue-800 border-blue-200";
    case "DRAFT":
      return "bg-slate-100 text-slate-700 border-slate-200";
    case "ARCHIVED":
      return "bg-slate-100 text-slate-500 border-slate-200";
    default:
      return "bg-amber-100 text-amber-800 border-amber-200";
  }
}

export function nodeTypeLabel(t: string): string {
  return NODE_TYPE_LABELS[t] || t;
}

export function nodeStateClass(state?: string): string {
  switch (state) {
    case "configured":
      return "border-emerald-400 bg-emerald-50";
    case "warning":
      return "border-amber-400 bg-amber-50";
    case "error":
      return "border-red-400 bg-red-50";
    case "required":
      return "border-blue-400 bg-blue-50";
    default:
      return "border-slate-200 bg-white";
  }
}

export function nodeStateLabel(state?: string): string {
  switch (state) {
    case "configured":
      return "설정 완료";
    case "warning":
      return "경고";
    case "error":
      return "오류";
    case "required":
      return "설정 필요";
    case "optional":
      return "선택";
    default:
      return "미설정";
  }
}

export function scheduleTypeLabel(t?: string): string {
  if (t === "MANUAL") return "수동";
  if (t === "CRON") return "스케줄";
  return t || "수동";
}
