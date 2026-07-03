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
  managed_table?: boolean;
  table_create_status?: string;
  table_create_sql_preview?: string | null;
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
  data_length?: number;
  numeric_precision?: number;
  numeric_scale?: number;
  required?: boolean;
  primary_key?: boolean;
  unique?: boolean;
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
  managed_table?: boolean;
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

export const R9_DATASET_WIZARD_NOTE =
  "R9-S2-1부터 clean 설치 후 표준 데이터셋은 0건으로 시작합니다. Wizard로 논리 데이터셋·컬럼을 정의한 뒤 Backend가 생성한 SQL Preview를 확인하고 내부 물리 테이블(std_ prefix)을 생성하세요. 사용자가 SQL을 직접 입력·수정해 실행하는 방식은 허용하지 않습니다.";

export const R7_DATASET_BUILDER_NOTE = R9_DATASET_WIZARD_NOTE;

export const R9_MAPPING_TARGET_NOTE =
  "Data Mapping 대상 테이블은 ACTIVE 상태이며 물리 테이블이 생성된 표준 데이터셋(std_*)만 선택할 수 있습니다. 표준 데이터셋이 없으면 먼저 표준 데이터셋 Wizard에서 물리 테이블을 생성하세요.";

export const R7_MAPPING_TARGET_NOTE = R9_MAPPING_TARGET_NOTE;
