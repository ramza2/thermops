import axios from "axios";

const API_BASE = import.meta.env.VITE_API_BASE_URL || "/api/v1";

export const api = axios.create({ baseURL: API_BASE, headers: { "Content-Type": "application/json" } });

export interface ApiResponse<T = unknown> {
  success: boolean;
  code: string;
  message: string;
  data: T;
}

export interface PagedData<T> {
  items: T[];
  page: number;
  size: number;
  total_count: number;
  total_pages: number;
}

export async function fetchApi<T>(path: string, params?: Record<string, unknown>): Promise<T> {
  const { data } = await api.get<ApiResponse<T>>(path, { params });
  return data.data;
}

export function extractApiErrorMessage(err: unknown, fallback = "요청에 실패했습니다."): string {
  const raw = (err as { response?: { data?: { detail?: unknown; message?: string } } })?.response?.data;
  if (typeof raw?.detail === "string") return raw.detail;
  if (raw?.detail && typeof raw.detail === "object") {
    const detail = raw.detail as { message?: string; errors?: string[]; hint?: string };
    if (detail.errors?.length) return detail.errors[0];
    if (detail.message && detail.hint) return `${detail.message} ${detail.hint}`;
    if (detail.message) return detail.message;
  }
  if (typeof raw?.message === "string" && raw.message) return raw.message;
  if (err instanceof Error && err.message) return err.message;
  return fallback;
}

export async function postApi<T>(path: string, body?: unknown): Promise<T> {
  const { data } = await api.post<ApiResponse<T>>(path, body ?? {});
  if (!data.success) {
    throw new Error(data.message || "요청에 실패했습니다.");
  }
  if (data.data === undefined || data.data === null) {
    throw new Error(data.message || "응답 데이터가 없습니다.");
  }
  return data.data;
}

export async function putApi<T>(path: string, body?: unknown): Promise<T> {
  const { data } = await api.put<ApiResponse<T>>(path, body);
  return data.data;
}

export async function deleteApi(path: string): Promise<void> {
  await api.delete(path);
}

export async function patchApi<T>(path: string, body?: unknown): Promise<T> {
  const { data } = await api.patch<ApiResponse<T>>(path, body);
  return data.data;
}
