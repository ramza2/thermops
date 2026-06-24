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

export async function postApi<T>(path: string, body?: unknown): Promise<T> {
  const { data } = await api.post<ApiResponse<T>>(path, body);
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
