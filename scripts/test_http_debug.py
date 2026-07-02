"""HTTP API 오류 응답 디버그 헬퍼 (회귀 테스트용)."""

from __future__ import annotations

import json
import urllib.error
from typing import Any


def format_http_error(exc: urllib.error.HTTPError) -> str:
    body = exc.read().decode(errors="replace")
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        return f"HTTP {exc.code}: {body[:2000]}"
    detail = payload.get("detail")
    if isinstance(detail, dict):
        return json.dumps(
            {
                "status_code": exc.code,
                "error_code": detail.get("error_code") or detail.get("code"),
                "message": detail.get("message") or detail,
                "detail": detail,
            },
            ensure_ascii=False,
            indent=2,
        )
    return json.dumps(
        {"status_code": exc.code, "detail": detail or payload},
        ensure_ascii=False,
        indent=2,
    )


def api_error_summary(method: str, path: str, exc: urllib.error.HTTPError) -> str:
    return f"{method} {path}\n{format_http_error(exc)}"


def print_precondition(label: str, data: dict[str, Any]) -> None:
    print(f"  [precondition] {label}: {json.dumps(data, ensure_ascii=False, default=str)}")
