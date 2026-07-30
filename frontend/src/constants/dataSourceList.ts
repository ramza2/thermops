import type { PagedData } from "@/api/client";
import { fetchApi } from "@/api/client";

/** Backend `GET /data-sources` accepts size 1..100. Keep list fetches within this cap. */
export const DATA_SOURCE_LIST_PAGE_SIZE = 100;

export const DATA_SOURCE_LIST_HINT =
  "최대 100건씩 조회합니다. 원하는 항목이 보이지 않으면 검색어를 입력하거나 더 보기를 눌러 주세요.";

export const DATA_SOURCE_SEARCH_HINT =
  "현재 로드된 항목 내에서만 검색합니다. 100건 초과 환경에서는 더 보기를 눌러 추가 항목을 불러오세요.";

export const DATA_SOURCE_SEARCH_PLACEHOLDER = "Data Source 이름, 코드, URL, 유형으로 검색";

export type DataSourceListItem = {
  source_id: string;
  source_name: string;
  source_type?: string;
  connection_info?: Record<string, string>;
  data_domain?: string | null;
};

export async function fetchDataSourcesPage(page: number): Promise<PagedData<DataSourceListItem>> {
  return fetchApi<PagedData<DataSourceListItem>>("/data-sources", {
    page,
    size: DATA_SOURCE_LIST_PAGE_SIZE,
  });
}

export async function fetchDataSourceById(sourceId: string): Promise<DataSourceListItem | null> {
  try {
    return await fetchApi<DataSourceListItem>(`/data-sources/${encodeURIComponent(sourceId)}`);
  } catch {
    return null;
  }
}

/** Client-side filter over already-loaded items (API has no keyword param). */
export function filterDataSourcesLocal<T extends DataSourceListItem>(
  items: T[],
  keyword: string,
): T[] {
  const q = keyword.trim().toLowerCase();
  if (!q) return items;
  return items.filter((s) => {
    const url = String(s.connection_info?.base_url || "");
    const hay = `${s.source_name} ${s.source_id} ${s.source_type || ""} ${url} ${s.data_domain || ""}`.toLowerCase();
    return hay.includes(q);
  });
}

export function mergeDataSourcePages<T extends DataSourceListItem>(
  current: T[],
  next: T[],
): T[] {
  const seen = new Set(current.map((s) => s.source_id));
  const merged = [...current];
  for (const item of next) {
    if (seen.has(item.source_id)) continue;
    seen.add(item.source_id);
    merged.push(item);
  }
  return merged;
}

export function selectedDataSourceMissingLabel(sourceId: string, resolvedName?: string | null): string {
  if (resolvedName) return `${resolvedName} (${sourceId}) · 현재 목록에 없음`;
  return `선택된 Data Source: ${sourceId} (현재 목록에 없음)`;
}
