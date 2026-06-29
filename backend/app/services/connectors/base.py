"""데이터 소스 Connector 공통 인터페이스."""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any

from app.models.entities import DataMapping, DataSource

_SENSITIVE_PATTERN = re.compile(
    r'(password|api_key|secret|token)(["\']?\s*[:=]\s*["\']?)([^\s"\',}]+)',
    re.IGNORECASE,
)


def mask_sensitive(text: str) -> str:
    """로그/API 응답에서 credential 노출 방지."""
    if not text:
        return text
    return _SENSITIVE_PATTERN.sub(r"\1\2***", str(text))


class ConnectorError(Exception):
    """Connector 공통 예외 — error_code 기반 표준화."""

    def __init__(
        self,
        message: str,
        *,
        error_code: str = "CONNECTION_FAILED",
        connector_type: str | None = None,
        source_type: str | None = None,
        detail: str | None = None,
        recoverable: bool = True,
    ) -> None:
        self.message = mask_sensitive(message)
        self.error_code = error_code
        self.connector_type = connector_type
        self.source_type = source_type
        self.detail = mask_sensitive(detail) if detail else None
        self.recoverable = recoverable
        super().__init__(self.message)

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "error_code": self.error_code,
            "message": self.message,
            "recoverable": self.recoverable,
        }
        if self.connector_type:
            out["connector_type"] = self.connector_type
        if self.source_type:
            out["source_type"] = self.source_type
        if self.detail:
            out["detail"] = self.detail
        return out


class BaseConnector(ABC):
    source_types: set[str]

    @abstractmethod
    def test_connection(self, source: DataSource) -> dict[str, Any]:
        ...

    @abstractmethod
    def discover_schema(self, source: DataSource) -> dict[str, Any]:
        ...

    @abstractmethod
    def preview(
        self,
        source: DataSource,
        *,
        mapping: DataMapping | None = None,
        limit: int = 10,
        start_at: datetime | None = None,
        end_at: datetime | None = None,
    ) -> dict[str, Any]:
        ...

    @abstractmethod
    def fetch_rows(
        self,
        source: DataSource,
        *,
        mapping: DataMapping | None = None,
        start_at: datetime | None = None,
        end_at: datetime | None = None,
        limit: int | None = None,
    ) -> tuple[list[dict[str, Any]], list[str]]:
        ...
