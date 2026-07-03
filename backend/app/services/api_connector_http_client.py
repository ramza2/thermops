"""REST API Connector HTTP 클라이언트."""

from __future__ import annotations

import os
import time
from typing import Any, Callable
from urllib.parse import urlencode, urljoin, urlparse

import httpx

from app.utils.masking import mask_url

MAX_RESPONSE_BYTES = int(os.environ.get("THERMOOPS_API_MAX_RESPONSE_BYTES", "5242880"))
DEFAULT_TIMEOUT = float(os.environ.get("THERMOOPS_API_CONNECTOR_TIMEOUT", "30"))
BLOCKED_HOSTS = frozenset({"169.254.169.254", "metadata.google.internal"})

_mock_handler: Callable[..., dict[str, Any]] | None = None


def set_http_mock_handler(handler: Callable[..., dict[str, Any]] | None) -> None:
    global _mock_handler
    _mock_handler = handler


def _allow_internal_hosts() -> bool:
    return os.environ.get("THERMOOPS_API_CONNECTOR_ALLOW_INTERNAL", "1") == "1"


def validate_url(url: str) -> None:
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    if not host:
        raise ValueError("유효하지 않은 URL입니다.")
    if host in BLOCKED_HOSTS:
        raise ValueError("허용되지 않은 호스트입니다.")
    if not _allow_internal_hosts() and host in {"localhost", "127.0.0.1", "::1"}:
        raise ValueError("내부 호스트 호출이 차단되었습니다.")


def build_full_url(base_url: str, endpoint_path: str) -> str:
    base = (base_url or "").rstrip("/")
    path = endpoint_path or ""
    if path.startswith("http://") or path.startswith("https://"):
        return path
    return urljoin(base + "/", path.lstrip("/"))


def encode_query_value(value: Any, *, encode: bool) -> str:
    text = "" if value is None else str(value)
    if encode:
        from urllib.parse import quote

        return quote(text, safe="")
    return text


def execute_http_request(
    *,
    method: str,
    url: str,
    query_params: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    body: dict[str, Any] | None = None,
    timeout: float | None = None,
    retries: int = 0,
) -> dict[str, Any]:
    if _mock_handler is not None:
        return _mock_handler(
            method=method,
            url=url,
            query_params=query_params,
            headers=headers,
            body=body,
        )

    validate_url(url)
    method = (method or "GET").upper()
    timeout = timeout or DEFAULT_TIMEOUT
    last_error: Exception | None = None

    for attempt in range(retries + 1):
        started = time.perf_counter()
        try:
            with httpx.Client(timeout=timeout, follow_redirects=True) as client:
                if method == "GET":
                    resp = client.get(url, params=query_params or {}, headers=headers or {})
                elif method == "POST":
                    if body:
                        resp = client.post(url, params=query_params or {}, json=body, headers=headers or {})
                    else:
                        resp = client.post(url, params=query_params or {}, headers=headers or {})
                else:
                    raise ValueError(f"지원하지 않는 HTTP 메서드: {method}")
            duration_ms = int((time.perf_counter() - started) * 1000)
            content = resp.content
            if len(content) > MAX_RESPONSE_BYTES:
                raise ValueError(f"응답 크기가 제한({MAX_RESPONSE_BYTES} bytes)을 초과했습니다.")
            text = resp.text
            return {
                "http_status": resp.status_code,
                "text": text,
                "duration_ms": duration_ms,
                "request_url": str(resp.request.url),
                "request_url_masked": mask_url(str(resp.request.url)),
            }
        except httpx.TimeoutException as exc:
            last_error = ValueError("API 요청 시간이 초과되었습니다.")
            last_error.__cause__ = exc
        except ValueError:
            raise
        except Exception as exc:
            last_error = ValueError(f"API 요청에 실패했습니다: {exc}")
        if attempt < retries:
            time.sleep(0.3)
    assert last_error is not None
    raise last_error
