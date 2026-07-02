export interface StandardDatasetColumn {
  column_id: string;
  column_name: string;
  display_name?: string | null;
  data_type: string;
  nullable: boolean;
  required: boolean;
  primary_key: boolean;
  default_column_role?: string | null;
  role_required: boolean;
  description?: string | null;
  example_value?: string | null;
  sort_order: number;
}

export interface StandardDatasetType {
  dataset_type_id: string;
  dataset_type_code: string;
  dataset_type_name: string;
  description?: string | null;
  domain?: string | null;
  category?: string | null;
  target_table: string;
  status: string;
  physical_table_yn: boolean;
  physical_table_exists: boolean;
  mapping_supported: boolean;
  recipe_supported: boolean;
  build_supported: boolean;
  active: boolean;
  owner?: string | null;
  column_count?: number;
  required_column_count?: number;
  default_roles?: Record<string, string[]>;
  columns?: StandardDatasetColumn[];
  recipe_readiness?: StandardDatasetRecipeReadiness;
}

export interface StandardTargetTable {
  dataset_type_id: string;
  dataset_type_code: string;
  dataset_type_name: string;
  target_table: string;
  domain?: string | null;
  category?: string | null;
  description?: string | null;
  build_supported: boolean;
  recipe_supported: boolean;
  standard_columns: string[];
}

export interface StandardDatasetValidation {
  valid: boolean;
  dataset_type?: StandardDatasetType;
  warnings?: string[];
  allowed_tables?: string[];
}

export interface StandardDatasetColumnInput {
  column_name: string;
  display_name?: string;
  data_type?: string;
  required?: boolean;
  primary_key?: boolean;
  default_column_role?: string;
  role_required?: boolean;
  description?: string;
  example_value?: string;
  sort_order?: number;
}

export interface StandardDatasetTypeCreateRequest {
  dataset_type_code: string;
  dataset_type_name: string;
  description?: string;
  domain?: string;
  category?: string;
  target_table: string;
  status?: string;
  owner?: string;
  build_supported?: boolean;
  recipe_supported?: boolean;
  mapping_supported?: boolean;
  columns?: StandardDatasetColumnInput[];
}

export interface StandardDatasetTypeUpdateRequest {
  dataset_type_name?: string;
  description?: string;
  domain?: string;
  category?: string;
  target_table?: string;
  owner?: string;
  build_supported?: boolean;
  recipe_supported?: boolean;
  mapping_supported?: boolean;
  columns?: StandardDatasetColumnInput[];
}

export interface StandardDatasetRecipeReadiness {
  role_summary: Record<string, unknown>;
  templates: {
    recipe_type: string;
    display_name: string;
    status: string;
    available: boolean;
    missing_roles: string[];
    warnings: string[];
  }[];
  available_count: number;
}

export const R7_DATASET_BUILDER_NOTE =
  "R7에서는 물리 테이블을 자동 생성하지 않습니다. ACTIVE 상태의 표준 대상 테이블만 데이터 매핑 대상으로 사용할 수 있습니다.";

export const R7_MAPPING_TARGET_NOTE =
  "대상 테이블은 표준 대상 테이블 목록에서 선택합니다. 새로운 도메인/테이블은 표준 데이터셋 관리에서 먼저 등록하세요.";
