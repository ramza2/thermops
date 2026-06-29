"""REST JSON API Connector."""

from __future__ import annotations

import time
from datetime import datetime
from typing import Any
from urllib.parse import urljoin

import httpx

from app.models.entities import DataMapping, DataSource
from app.services.connectors.base import BaseConnector, ConnectorError, mask_sensitive
from app.services.mapping_service import apply_mapping

API_TYPES = {"REST_API", "API"}
_CONNECTOR = "REST_API"


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
                raise ConnectorError(
                    f"item_path 해석 실패: {path}",
                    error_code="API_RESPONSE_PARSE_FAILED",
                    connector_type=_CONNECTOR,
                ) from exc
        else:
            raise ConnectorError(
                f"item_path 해석 실패: {path}",
                error_code="API_RESPONSE_PARSE_FAILED",
                connector_type=_CONNECTOR,
            )
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


def _validate_connection_info(info: dict[str, Any]) -> None:
    if not info.get("base_url"):
        raise ConnectorError(
            "connection_info.base_url이 필요합니다.",
            error_code="INVALID_CONNECTION_INFO",
            connector_type=_CONNECTOR,
        )
    if not info.get("endpoint"):
        raise ConnectorError(
            "connection_info.endpoint가 필요합니다.",
            error_code="INVALID_CONNECTION_INFO",
            connector_type=_CONNECTOR,
        )
    if not info.get("item_path"):
        raise ConnectorError(
            "connection_info.item_path가 필요합니다.",
            error_code="INVALID_CONNECTION_INFO",
            connector_type=_CONNECTOR,
        )
    method = (info.get("method") or "GET").upper()
    if method != "GET":
        raise ConnectorError(
            f"지원하지 않는 HTTP 메서드: {method} (GET만 지원)",
            error_code="INVALID_CONNECTION_INFO",
            connector_type=_CONNECTOR,
            recoverable=False,
        )


def _build_url(info: dict[str, Any]) -> str:
    base = (info.get("base_url") or "").rstrip("/")
    endpoint = info.get("endpoint") or ""
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
    _validate_connection_info(info)
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
                raise ConnectorError(
                    f"API 요청 실패 (HTTP {resp.status_code})",
                    error_code="API_REQUEST_FAILED",
                    connector_type=_CONNECTOR,
                    detail=resp.text[:300],
                )
            return resp.json()
        except ConnectorError:
            raise
        except httpx.TimeoutException as exc:
            last_exc = ConnectorError(
                "API 요청 시간이 초과되었습니다.",
                error_code="API_REQUEST_FAILED",
                connector_type=_CONNECTOR,
                detail=str(exc),
            )
        except Exception as exc:
            last_exc = ConnectorError(
                "API 요청에 실패했습니다.",
                error_code="API_REQUEST_FAILED",
                connector_type=_CONNECTOR,
                detail=mask_sensitive(str(exc)),
            )
        if attempt < retries:
            time.sleep(0.5)
    assert last_exc is not None
    raise last_exc


def _extract_items(payload: Any, info: dict[str, Any]) -> list[dict[str, Any]]:
    item_path = info.get("item_path") or "items"
    items = _extract_path(payload, item_path)
    if items is None:
        return []
    if isinstance(items, dict):
        return [items]
    if isinstance(items, list):
        return [i for i in items if isinstance(i, dict)]
    raise ConnectorError(
        "item_path가 객체 배열을 가리키지 않습니다.",
        error_code="API_RESPONSE_PARSE_FAILED",
        connector_type=_CONNECTOR,
    )


def _fail_result(exc: Exception, latency_ms: int) -> dict[str, Any]:
    if isinstance(exc, ConnectorError):
        return {
            "success": False,
            "message": exc.message,
            "latency_ms": latency_ms,
            "error_message": exc.message,
            "error_code": exc.error_code,
            "error": exc.to_dict(),
            "sample_row_count": 0,
            "columns": [],
            "fields": [],
            "connector_type": _CONNECTOR,
        }
    msg = mask_sensitive(str(exc))
    return {
        "success": False,
        "message": "연결 테스트에 실패했습니다.",
        "latency_ms": latency_ms,
        "error_message": msg,
        "error_code": "CONNECTION_FAILED",
        "sample_row_count": 0,
        "columns": [],
        "fields": [],
        "connector_type": _CONNECTOR,
    }


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
                "sample_row_count": min(len(items), 5),
                "columns": [f["name"] for f in fields],
                "fields": fields,
                "connector_type": _CONNECTOR,
                "status_code": 200,
            }
        except Exception as exc:
            latency_ms = int((time.perf_counter() - started) * 1000)
            return _fail_result(exc, latency_ms)

    def discover_schema(self, source: DataSource) -> dict[str, Any]:
        info = source.connection_info or {}
        payload = _request(info)
        items = _extract_items(payload, info)
        if not items:
            return {"fields": [], "connector_type": _CONNECTOR, "warnings": ["응답 item이 비어 있습니다."]}
        sample = items[0]
        fields = [
            {"name": k, "data_type": _infer_type(v), "nullable": v is None}
            for k, v in sample.items()
        ]
        return {"fields": fields, "connector_type": _CONNECTOR}

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
        return {"rows": rows[:limit], "columns": columns, "connector_type": _CONNECTOR}

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
        if limit is not None:
            items = items[: int(limit)]
        str_rows = [{k: "" if v is None else str(v) for k, v in row.items()} for row in items]
        columns = list(items[0].keys()) if items else []
        if mapping:
            str_rows = apply_mapping(str_rows, mapping)
        return str_rows, columns
