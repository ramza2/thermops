"""REST JSON API Connector."""

from __future__ import annotations

import json
import time
from datetime import datetime
from typing import Any
from urllib.parse import urljoin

import httpx

from app.models.entities import DataMapping, DataSource
from app.services.connectors.base import BaseConnector, ConnectorError
from app.services.mapping_service import apply_mapping

API_TYPES = {"REST_API", "API"}


def _extract_path(data: Any, path: str | None) -> Any:
    if not path or path in ("$", ""):
        return data
    cleaned = path.strip()
    if cleaned.startswith("$."):
        cleaned = cleaned[2:]
    if cleaned.startswith("$"):
        cleaned = cleaned[1:].lstrip(".")
    current = data
    for part in cleaned.split("."):
        if part == "":
            continue
        if isinstance(current, dict):
            current = current.get(part)
        elif isinstance(current, list):
            try:
                current = current[int(part)]
            except (ValueError, IndexError) as exc:
                raise ConnectorError(f"item_path 해석 실패: {path}") from exc
        else:
            raise ConnectorError(f"item_path 해석 실패: {path}")
    return current


def _infer_type(value: Any) -> str:
    if value is None:
        return "unknown"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    return "string"


def _build_url(info: dict[str, Any]) -> str:
    base = (info.get("base_url") or "").rstrip("/")
    endpoint = info.get("endpoint") or ""
    if not base:
        raise ConnectorError("connection_info.base_url이 필요합니다.")
    return urljoin(base + "/", endpoint.lstrip("/"))


def _build_headers(info: dict[str, Any]) -> dict[str, str]:
    headers = dict(info.get("headers") or {})
    auth_type = (info.get("auth_type") or "NONE").upper()
    if auth_type == "API_KEY_HEADER":
        header_name = info.get("api_key_header") or "X-API-Key"
        api_key = info.get("api_key")
        if api_key:
            headers[header_name] = str(api_key)
    # TODO: BASIC/OAuth 인증
    return headers


def _substitute_params(params: dict[str, Any], start_at: datetime | None, end_at: datetime | None) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, val in (params or {}).items():
        text = str(val)
        if "{start_at}" in text:
            if not start_at:
                continue
            text = text.replace("{start_at}", start_at.isoformat())
        if "{end_at}" in text:
            if not end_at:
                continue
            text = text.replace("{end_at}", end_at.isoformat())
        out[key] = text
    return out


def _request(
    info: dict[str, Any],
    *,
    start_at: datetime | None = None,
    end_at: datetime | None = None,
) -> Any:
    method = (info.get("method") or "GET").upper()
    if method != "GET":
        raise ConnectorError("이번 단계에서는 GET 메서드만 지원합니다.")
    url = _build_url(info)
    headers = _build_headers(info)
    params = _substitute_params(info.get("query_params") or {}, start_at, end_at)
    timeout = float(info.get("timeout_sec", 10))
    retries = int(info.get("retries", 1))
    last_exc: Exception | None = None
    for attempt in range(retries + 1):
        try:
            with httpx.Client(timeout=timeout) as client:
                resp = client.get(url, headers=headers, params=params)
            if resp.status_code >= 400:
                raise ConnectorError(f"HTTP {resp.status_code}: {resp.text[:300]}")
            return resp.json()
        except Exception as exc:
            last_exc = exc
            if attempt < retries:
                time.sleep(0.5)
    raise ConnectorError(str(last_exc))


def _extract_items(payload: Any, info: dict[str, Any]) -> list[dict[str, Any]]:
    item_path = info.get("item_path") or "items"
    items = _extract_path(payload, item_path)
    if items is None:
        return []
    if isinstance(items, dict):
        return [items]
    if isinstance(items, list):
        return [i for i in items if isinstance(i, dict)]
    raise ConnectorError("item_path가 객체 배열을 가리키지 않습니다.")


class RestApiConnector(BaseConnector):
    source_types = API_TYPES

    def test_connection(self, source: DataSource) -> dict[str, Any]:
        info = source.connection_info or {}
        started = time.perf_counter()
        try:
            payload = _request(info)
            items = _extract_items(payload, info)
            fields = []
            if items:
                sample = items[0]
                fields = [
                    {"name": k, "data_type": _infer_type(v), "nullable": v is None}
                    for k, v in sample.items()
                ]
            latency_ms = int((time.perf_counter() - started) * 1000)
            return {
                "success": True,
                "message": "연결 테스트에 성공했습니다.",
                "latency_ms": latency_ms,
                "error_message": None,
                "sample_row_count": len(items[:5]),
                "columns": [f["name"] for f in fields],
                "fields": fields,
                "connector_type": "REST_API",
                "status_code": 200,
            }
        except Exception as exc:
            latency_ms = int((time.perf_counter() - started) * 1000)
            return {
                "success": False,
                "message": "연결 테스트에 실패했습니다.",
                "latency_ms": latency_ms,
                "error_message": str(exc),
                "sample_row_count": 0,
                "columns": [],
                "fields": [],
                "connector_type": "REST_API",
            }

    def discover_schema(self, source: DataSource) -> dict[str, Any]:
        info = source.connection_info or {}
        payload = _request(info)
        items = _extract_items(payload, info)
        if not items:
            return {"fields": [], "connector_type": "REST_API", "warnings": ["응답 item이 비어 있습니다."]}
        sample = items[0]
        fields = [
            {"name": k, "data_type": _infer_type(v), "nullable": v is None}
            for k, v in sample.items()
        ]
        return {"fields": fields, "connector_type": "REST_API"}

    def preview(
        self,
        source: DataSource,
        *,
        mapping: DataMapping | None = None,
        limit: int = 10,
        start_at: datetime | None = None,
        end_at: datetime | None = None,
    ) -> dict[str, Any]:
        info = source.connection_info or {}
        payload = _request(info, start_at=start_at, end_at=end_at)
        items = _extract_items(payload, info)[:limit]
        str_rows = [{k: "" if v is None else str(v) for k, v in row.items()} for row in items]
        rows = apply_mapping(str_rows, mapping) if mapping else str_rows
        columns = list(items[0].keys()) if items else []
        return {"rows": rows[:limit], "columns": columns, "connector_type": "REST_API"}

    def fetch_rows(
        self,
        source: DataSource,
        *,
        mapping: DataMapping | None = None,
        start_at: datetime | None = None,
        end_at: datetime | None = None,
        limit: int | None = None,
    ) -> tuple[list[dict[str, Any]], list[str]]:
        info = source.connection_info or {}
        payload = _request(info, start_at=start_at, end_at=end_at)
        items = _extract_items(payload, info)
        if limit:
            items = items[:limit]
        str_rows = [{k: "" if v is None else str(v) for k, v in row.items()} for row in items]
        columns = list(items[0].keys()) if items else []
        if mapping:
            str_rows = apply_mapping(str_rows, mapping)
        return str_rows, columns
