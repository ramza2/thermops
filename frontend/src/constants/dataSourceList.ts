import type { PagedData } from "@/api/client";
import { extractApiErrorMessage, fetchApi, postApi } from "@/api/client";

/** Backend `GET /data-sources` accepts size 1..100. Keep list fetches within this cap. */
export const DATA_SOURCE_LIST_PAGE_SIZE = 100;

export const DATA_SOURCE_LIST_HINT =
  "최대 100건씩 조회합니다. 원하는 항목이 보이지 않으면 검색어를 입력하거나 더 보기를 눌러 주세요.";

export const DATA_SOURCE_SEARCH_HINT =
  "현재 로드된 항목 내에서만 검색합니다. 100건 초과 환경에서는 더 보기를 눌러 추가 항목을 불러오세요.";

export const DATA_SOURCE_SEARCH_PLACEHOLDER = "Data Source 이름, 코드, URL, 유형으로 검색";

export const DATA_SOURCE_INLINE_CREATE_AUTH_HINT =
  "인증이 필요한 API는 Data Sources 화면의 REST API 연결 Wizard 「인증 정보」단계에서 등록하세요. Studio에서는 API Key/Token 원문을 저장하지 않습니다.";

export const DATA_SOURCE_CREDENTIAL_REF_HELP =
  "API Key나 Token 원문을 입력하지 말고 CRED-... 형태의 참조 ID만 입력하세요. 기존 Data Source credential 정책에 따라 인증 정보가 참조됩니다.";

/** Align with DataSourcesPage create form defaults. */
export const DATA_SOURCE_DOMAIN_OPTIONS = [
  { value: "HEAT_DEMAND", label: "열수요" },
  { value: "WEATHER", label: "기상" },
  { value: "OPERATION", label: "운영" },
  { value: "CALENDAR", label: "캘린더" },
] as const;

export const DEFAULT_DATA_SOURCE_DOMAIN = "HEAT_DEMAND";

export type DataSourceListItem = {
  source_id: string;
  source_name: string;
  source_type?: string;
  connection_info?: Record<string, string>;
  data_domain?: string | null;
};

export type CreateRestDataSourceInput = {
  source_name: string;
  data_domain?: string;
  base_url: string;
  endpoint?: string;
  item_path?: string;
  active_yn?: boolean;
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

/** Create REST_API Data Source. Response is `{ source_id }` only. */
export async function createRestDataSource(
  input: CreateRestDataSourceInput,
): Promise<{ source_id: string }> {
  const source_name = input.source_name.trim();
  const base_url = input.base_url.trim();
  if (!source_name) throw new Error("소스명을 입력하세요.");
  if (!base_url) throw new Error("Base URL을 입력하세요.");
  return postApi<{ source_id: string }>("/data-sources", {
    source_name,
    source_type: "REST_API",
    data_domain: (input.data_domain || DEFAULT_DATA_SOURCE_DOMAIN).trim() || DEFAULT_DATA_SOURCE_DOMAIN,
    connection_info: {
      base_url,
      endpoint: (input.endpoint || "").trim(),
      method: "GET",
      headers: {},
      query_params: {},
      auth_type: "NONE",
      api_key_header: null,
      api_key: null,
      item_path: (input.item_path || "data.items").trim() || "data.items",
      pagination: { type: "NONE" },
    },
    active_yn: input.active_yn !== false,
  });
}

export function createDataSourceErrorMessage(err: unknown, fallback = "Data Source 등록에 실패했습니다."): string {
  return extractApiErrorMessage(err, fallback);
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

export function isRestApiDataSourceType(sourceType?: string | null): boolean {
  const t = String(sourceType || "").toUpperCase();
  return t === "REST_API" || t === "API";
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
