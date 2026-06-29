"""Connector registry."""

from __future__ import annotations

from app.models.entities import DataSource
from app.services.connectors.base import BaseConnector, ConnectorError
from app.services.connectors.csv_connector import CsvConnector
from app.services.connectors.postgres_connector import PostgresConnector
from app.services.connectors.rest_api_connector import RestApiConnector

_CONNECTORS: list[BaseConnector] = [
    CsvConnector(),
    PostgresConnector(),
    RestApiConnector(),
]

_BY_TYPE: dict[str, BaseConnector] = {}
for _c in _CONNECTORS:
    for _t in _c.source_types:
        _BY_TYPE[_t.upper()] = _c

SUPPORTED_SOURCE_TYPES = sorted(_BY_TYPE.keys())


def get_connector(source: DataSource) -> BaseConnector:
    key = (source.source_type or "").upper()
    connector = _BY_TYPE.get(key)
    if not connector:
        raise ConnectorError(f"지원하지 않는 source_type: {source.source_type}")
    return connector


def normalize_source_type(source_type: str) -> str:
    return (source_type or "").upper()
