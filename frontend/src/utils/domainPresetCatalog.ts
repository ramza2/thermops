/**
 * R11-S8-9-24 / B2: FE-only Domain Preset catalog (no DB / no API).
 * Guides + safe Type A hints only. Type B fields stay empty.
 */

import type { StarterTemplateId } from "@/utils/starterTemplateCatalog";

export type DomainPresetId = "generic_time_series_load" | "heat_demand_forecast";

export type DomainPresetExpectedColumn = {
  name: string;
  type?: string;
  required?: boolean;
  description?: string;
};

export type DomainPreset = {
  id: DomainPresetId;
  title: string;
  category: "generic" | "energy" | "custom";
  description: string;
  recommendedTemplateIds: StarterTemplateId[];
  recommendedTransformType?: string;
  recommendedConflictKeys?: string[];
  expectedOutputColumns?: DomainPresetExpectedColumn[];
  requiredSetup: string[];
  validationHints: string[];
  targetSchemaHints: string[];
  limitations: string[];
};

export const DOMAIN_PRESET_NONE_LABEL = "사용 안 함";

export const DOMAIN_PRESET_SECTION_HINT =
  "Preset은 설정 가이드와 추천값만 제공합니다. Data Source, Standard Dataset, Target Table, credential은 직접 설정해야 합니다.";

export const DOMAIN_PRESET_APPLY_TOAST =
  "Starter Template과 Domain Preset이 적용되었습니다. Preset은 transform/key/schema 힌트만 제공합니다. Data Source, Standard Dataset, Target Table, credential은 직접 설정한 뒤 Graph 저장 → 검증 → Compile 순서로 진행하세요.";

/** Fields that Domain Preset must never auto-fill. */
export const DOMAIN_PRESET_TYPE_B_FIELDS = [
  "data_source_id",
  "standard_dataset_id",
  "target_table",
  "credential_ref",
  "conflict_key_columns_json",
] as const;

export const DOMAIN_PRESET_CATALOG: DomainPreset[] = [
  {
    id: "generic_time_series_load",
    title: "Generic Time-Series Load",
    category: "generic",
    description:
      "시계열형 source를 표준 target table로 적재하는 일반 preset입니다. transform type을 강제하지 않습니다.",
    recommendedTemplateIds: ["cron-full", "rest-upsert"],
    recommendedConflictKeys: ["entity_id", "measured_at"],
    requiredSetup: ["Data Source", "Standard Dataset", "Target Table", "credential", "기준키"],
    validationHints: [
      "Source ↔ Target 컬럼 매칭(B15)을 확인하세요.",
      "Upsert 기준키는 Schema/Key Helper 추천을 참고한 뒤 직접 선택하세요.",
    ],
    targetSchemaHints: ["entity_id + measured_at 기준의 시계열 적재에 적합합니다."],
    limitations: [
      "Preset은 안내/추천만 제공하며 자동 저장·실행하지 않습니다.",
      "Data Source / Standard Dataset / Target Table / credential은 비워 둡니다.",
    ],
  },
  {
    id: "heat_demand_forecast",
    title: "Heat Demand Forecast Data Load",
    category: "energy",
    description:
      "열수요 예측 데이터 적재 예시 preset입니다. wide-hour → long 변환과 공통 출력 컬럼 힌트를 제공합니다.",
    recommendedTemplateIds: ["cron-full"],
    recommendedTransformType: "WIDE_HOUR_TO_LONG",
    recommendedConflictKeys: ["entity_id", "measured_at"],
    expectedOutputColumns: [
      { name: "entity_id", type: "VARCHAR", required: true, description: "엔티티 식별자" },
      { name: "measured_at", type: "TIMESTAMP", required: true, description: "측정 시각" },
      { name: "heat_demand", type: "NUMERIC", required: true, description: "열수요 값" },
      { name: "site_id", type: "VARCHAR", description: "사이트 식별자" },
      { name: "source_system", type: "VARCHAR", description: "원천 시스템" },
      { name: "raw_date", type: "DATE", description: "원본 일자" },
      { name: "raw_hour", type: "INTEGER", description: "원본 시(0–23)" },
    ],
    requiredSetup: ["Data Source", "Standard Dataset", "Target Table", "credential", "기준키", "CRON"],
    validationHints: [
      "Transform 출력 컬럼 제안(B21)과 Source↔Target 매칭(B15)을 확인하세요.",
      "추천 기준키 entity_id + measured_at는 Helper 안내이며 자동 확정되지 않습니다.",
    ],
    targetSchemaHints: [
      "예상 출력: entity_id, measured_at, heat_demand, site_id, source_system, raw_date, raw_hour",
    ],
    limitations: [
      "예시 preset이며 특정 고객/조직 전용이 아닙니다.",
      "실제 Data Source / Standard Dataset / Target Table ID는 자동 채우지 않습니다.",
      "물리 테이블·unique index·compile/run을 수행하지 않습니다.",
    ],
  },
];

export function getDomainPreset(id: DomainPresetId | null | undefined): DomainPreset | undefined {
  if (!id) return undefined;
  return DOMAIN_PRESET_CATALOG.find((p) => p.id === id);
}

export function formatDomainPresetKeys(keys: string[] | undefined): string {
  if (!keys?.length) return "—";
  return keys.join(" + ");
}
