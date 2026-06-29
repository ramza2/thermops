"""데이터 소스 Connector 공통 인터페이스."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any

from app.models.entities import DataMapping, DataSource


class ConnectorError(Exception):
    pass


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
