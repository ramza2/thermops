export type ExternalCodeMapping = {
  mapping_id: string;
  source_system: string;
  source_operation_id?: string | null;
  external_code_group: string;
  external_code: string;
  external_code_name?: string | null;
  external_code_description?: string | null;
  target_type: string;
  target_id: string;
  target_display_name?: string | null;
  mapping_status: string;
  mapping_method: string;
  confidence_score?: number | null;
  priority: number;
  valid_from?: string | null;
  valid_to?: string | null;
  active_yn: boolean;
  created_at?: string;
  updated_at?: string;
};

export type UnmappedExternalCode = {
  unmapped_id: string;
  source_system: string;
  source_operation_id?: string | null;
  external_code_group: string;
  external_code: string;
  external_code_name?: string | null;
  first_seen_at?: string;
  last_seen_at?: string;
  seen_count: number;
  sample_payload_json?: Record<string, unknown> | null;
  review_status: string;
  ignored_reason?: string | null;
  resolved_mapping_id?: string | null;
};

export type TargetCandidate = {
  target_id: string;
  target_display_name: string;
  target_type: string;
  subtitle?: string;
};

export type ResolveResult = {
  resolved: boolean;
  target_type?: string;
  target_id?: string;
  target_display_name?: string;
  mapping_id?: string;
  unmapped_id?: string;
  warnings?: string[];
};

export type MappingOptions = {
  source_systems: string[];
  external_code_groups: string[];
  target_types: string[];
  mapping_statuses: string[];
  review_statuses: string[];
  mapping_methods: string[];
};

export const TARGET_TYPE_OPTIONS = [
  { value: "PREDICTION_ENTITY", label: "예측 대상" },
  { value: "FORECAST_GRID", label: "단기예보 격자" },
  { value: "OBSERVATION_STATION", label: "ASOS 관측소" },
  { value: "STANDARD_DATASET", label: "표준 데이터셋" },
  { value: "COMMON_CODE", label: "공통코드" },
  { value: "CUSTOM", label: "사용자 정의" },
];

export const MAPPING_STATUS_OPTIONS = [
  { value: "ACTIVE", label: "사용 중" },
  { value: "INACTIVE", label: "비활성" },
  { value: "PENDING_REVIEW", label: "검토 대기" },
  { value: "ARCHIVED", label: "보관됨" },
];

export function targetTypeLabel(code?: string | null): string {
  return TARGET_TYPE_OPTIONS.find((o) => o.value === code)?.label ?? code ?? "-";
}

export function mappingStatusLabel(code?: string | null): string {
  return MAPPING_STATUS_OPTIONS.find((o) => o.value === code)?.label ?? code ?? "-";
}

export function reviewStatusLabel(code?: string | null): string {
  const map: Record<string, string> = {
    NEW: "신규",
    REVIEWING: "검토 중",
    MAPPED: "연결됨",
    IGNORED: "무시",
    ARCHIVED: "보관됨",
  };
  return map[code || ""] ?? code ?? "-";
}
