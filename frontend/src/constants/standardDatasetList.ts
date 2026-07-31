import { extractApiErrorMessage } from "@/api/client";
import {
  createStandardDatasetType,
  getStandardDatasetType,
  getStandardDatasetTypes,
  suggestTableName,
} from "@/api/standardDatasets";
import type { StandardDatasetColumnInput, StandardDatasetType } from "@/types/standardDatasets";

export const STANDARD_DATASET_LIST_HINT =
  "보관된 표준 데이터셋은 기본 선택 목록에서 제외됩니다. 원하는 항목이 보이지 않으면 검색어를 입력하거나 새로고침해 주세요.";

export const STANDARD_DATASET_SEARCH_HINT =
  "서버 keyword로 이름·코드·설명·업무 영역을 검색합니다. 목록은 page/size 없이 한 번에 조회됩니다.";

export const STANDARD_DATASET_SEARCH_PLACEHOLDER = "표준 데이터셋 이름, 코드, 테이블명으로 검색";

export const STANDARD_DATASET_INLINE_CREATE_HINT =
  "메타데이터(DRAFT)만 등록합니다. 물리 테이블 생성·ACTIVE 전환은 표준 데이터셋 화면 Wizard에서 진행하세요.";

export const DEFAULT_DATASET_CATEGORY = "CUSTOM";

export type CreateInlineStandardDatasetInput = {
  dataset_type_name: string;
  dataset_type_code: string;
  dataset_category?: string;
  business_domain?: string;
  description?: string;
  target_table: string;
  columns?: StandardDatasetColumnInput[];
};

/** Active (non-archived) datasets for Upsert target picker. */
export async function fetchActiveStandardDatasets(keyword?: string): Promise<StandardDatasetType[]> {
  const res = await getStandardDatasetTypes({
    keyword: keyword?.trim() || undefined,
    include_columns: false,
    include_planned: true,
  });
  return (res.items || []).filter(isSelectableStandardDataset);
}

export async function fetchStandardDatasetById(id: string): Promise<StandardDatasetType | null> {
  try {
    return await getStandardDatasetType(id, { include_columns: false });
  } catch {
    return null;
  }
}

/** B15: load columns for Source↔Target preview. Failure returns null (non-blocking). */
export async function fetchStandardDatasetColumns(id: string): Promise<StandardDatasetType | null> {
  const trimmed = id.trim();
  if (!trimmed) return null;
  try {
    return await getStandardDatasetType(trimmed, { include_columns: true });
  } catch {
    return null;
  }
}

export async function suggestStandardTargetTable(datasetCode: string): Promise<string> {
  const code = datasetCode.trim();
  if (!code) return "";
  try {
    const res = await suggestTableName(code);
    return res.physical_table_name || `std_${code.toLowerCase().replace(/[^a-z0-9_]+/g, "_")}`;
  } catch {
    return `std_${code.toLowerCase().replace(/[^a-z0-9_]+/g, "_")}`;
  }
}

/** Create DRAFT metadata only. No physical table / ACTIVE. */
export async function createInlineStandardDataset(
  input: CreateInlineStandardDatasetInput,
): Promise<StandardDatasetType> {
  const dataset_type_name = input.dataset_type_name.trim();
  const dataset_type_code = input.dataset_type_code.trim().toUpperCase();
  const target_table = input.target_table.trim().toLowerCase();
  if (!dataset_type_name) throw new Error("데이터셋명을 입력하세요.");
  if (!dataset_type_code) throw new Error("데이터셋 코드를 입력하세요.");
  if (!target_table) throw new Error("물리 테이블명을 입력하세요.");

  const columns = (input.columns || []).filter((c) => c.column_name?.trim());

  return createStandardDatasetType({
    dataset_type_name,
    dataset_type_code,
    description: input.description?.trim() || undefined,
    dataset_category: (input.dataset_category || DEFAULT_DATASET_CATEGORY).trim() || DEFAULT_DATASET_CATEGORY,
    business_domain: input.business_domain?.trim() || undefined,
    target_table,
    status: "DRAFT",
    managed_table: true,
    mapping_supported: false,
    columns,
  });
}

export function createStandardDatasetErrorMessage(
  err: unknown,
  fallback = "표준 데이터셋 등록에 실패했습니다.",
): string {
  return extractApiErrorMessage(err, fallback);
}

export function isSelectableStandardDataset(item: StandardDatasetType): boolean {
  if (!item?.dataset_type_id) return false;
  if (item.active === false) return false;
  const status = String(item.status || "").toUpperCase();
  if (status === "ARCHIVED") return false;
  return true;
}

export function mergeStandardDatasetItems(
  current: StandardDatasetType[],
  next: StandardDatasetType[],
): StandardDatasetType[] {
  const seen = new Set(current.map((s) => s.dataset_type_id));
  const merged = [...current];
  for (const item of next) {
    if (!isSelectableStandardDataset(item)) continue;
    if (seen.has(item.dataset_type_id)) {
      const idx = merged.findIndex((s) => s.dataset_type_id === item.dataset_type_id);
      if (idx >= 0) merged[idx] = item;
      continue;
    }
    seen.add(item.dataset_type_id);
    merged.push(item);
  }
  return merged;
}

export function selectedStandardDatasetMissingLabel(
  datasetId: string,
  resolvedName?: string | null,
): string {
  if (resolvedName) return `${resolvedName} (${datasetId}) · 현재 목록에 없음`;
  return `선택된 표준 데이터셋: ${datasetId} (현재 목록에 없음)`;
}

export function formatStandardDatasetOptionLabel(item: StandardDatasetType): string {
  return `${item.dataset_type_name} (${item.dataset_type_code}) · ${item.target_table}`;
}
