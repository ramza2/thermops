/**
 * R11-S8-9-23 / B1: FE-only Starter Template catalog (no DB / no API).
 * Skeletons reuse GraphTemplateId + buildTemplateGraph. Type B fields stay empty.
 */

import type { GraphTemplateId } from "@/types/visualPipeline";

export type StarterTemplateId = Exclude<GraphTemplateId, "blank">;

export type StarterTemplateCatalogItem = {
  id: StarterTemplateId;
  title: string;
  description: string;
  requiredSetup: string[];
  expectedNodeCount: number;
  expectedEdgeCount: number;
};

export const STARTER_TEMPLATE_CATALOG: StarterTemplateCatalogItem[] = [
  {
    id: "cron-full",
    title: "Scheduled REST Data Load",
    description:
      "REST API Source → Transform → Upsert Load, CRON Schedule trigger 포함. 시작용 skeleton이며 즉시 실행용이 아닙니다.",
    requiredSetup: ["Data Source", "Standard Dataset", "Target Table", "기준키", "CRON"],
    expectedNodeCount: 4,
    expectedEdgeCount: 3,
  },
  {
    id: "rest-upsert",
    title: "Manual REST Data Load",
    description:
      "REST API Source → Transform → Upsert Load. CRON 없이 수동 실행 전용 골격입니다.",
    requiredSetup: ["Data Source", "Standard Dataset", "Target Table", "기준키"],
    expectedNodeCount: 3,
    expectedEdgeCount: 2,
  },
];

export const STARTER_TEMPLATE_HINT =
  "자주 사용하는 Visual Pipeline 골격을 선택해 시작합니다. 적용 후 저장 전까지는 현재 graph에만 반영됩니다.";

export const STARTER_TEMPLATE_APPLY_TOAST =
  "Starter Template이 graph에 적용되었습니다. Data Source, Standard Dataset, Target Table, 기준키를 설정한 뒤 Graph 저장 → 검증 → Compile → 실행 설정 반영 순서로 진행하세요.";

/** Type B fields that must remain empty after starter apply (no fake sample ids). */
export const STARTER_TEMPLATE_TYPE_B_FIELDS = [
  "data_source_id",
  "standard_dataset_id",
  "target_table",
  "credential_ref",
  "conflict_key_columns_json",
] as const;

export function getStarterTemplateCatalogItem(
  id: StarterTemplateId,
): StarterTemplateCatalogItem | undefined {
  return STARTER_TEMPLATE_CATALOG.find((t) => t.id === id);
}
