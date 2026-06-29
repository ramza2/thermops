"""PostgreSQL DB Connector."""

from __future__ import annotations

import re
import time
from datetime import datetime
from typing import Any

import psycopg2
import psycopg2.extras

from app.models.entities import DataMapping, DataSource
from app.services.connectors.base import BaseConnector, ConnectorError, mask_sensitive
from app.services.mapping_service import apply_mapping

DB_TYPES = {"DB_POSTGRES", "DB"}
_CONNECTOR = "DB_POSTGRES"
_FORBIDDEN_SQL = re.compile(
    r"\b(DROP|DELETE|UPDATE|INSERT|ALTER|TRUNCATE|CREATE|GRANT|REVOKE)\b",
    re.IGNORECASE,
)


def _conn_info(info: dict[str, Any] | None) -> dict[str, Any]:
    if not info:
        raise ConnectorError(
            "connection_info가 필요합니다.",
            error_code="INVALID_CONNECTION_INFO",
            connector_type=_CONNECTOR,
        )
    return info


def _validate_connection_info(ci: dict[str, Any]) -> None:
    for field in ("host", "database", "username", "password"):
        if not ci.get(field):
            raise ConnectorError(
                f"connection_info.{field}가 필요합니다.",
                error_code="INVALID_CONNECTION_INFO",
                connector_type=_CONNECTOR,
            )
    custom = (ci.get("query") or "").strip()
    table = ci.get("table")
    if not custom and not table:
        raise ConnectorError(
            "connection_info.table 또는 query가 필요합니다.",
            error_code="INVALID_CONNECTION_INFO",
            connector_type=_CONNECTOR,
        )


def _connect(info: dict[str, Any]):
    ci = _conn_info(info)
    _validate_connection_info(ci)
    try:
        return psycopg2.connect(
            host=ci.get("host", "localhost"),
            port=int(ci.get("port", 5432)),
            dbname=ci.get("database") or ci.get("dbname"),
            user=ci.get("username") or ci.get("user"),
            password=ci.get("password", ""),
            connect_timeout=int(ci.get("connect_timeout", 10)),
        )
    except Exception as exc:
        raise ConnectorError(
            "PostgreSQL 연결에 실패했습니다.",
            error_code="CONNECTION_FAILED",
            connector_type=_CONNECTOR,
            detail=mask_sensitive(str(exc)),
        ) from exc


def _validate_select_query(query: str) -> None:
    stripped = query.strip()
    if not stripped.upper().startswith("SELECT"):
        raise ConnectorError(
            "SELECT 쿼리만 허용됩니다.",
            error_code="UNSAFE_QUERY",
            connector_type=_CONNECTOR,
        )
    if _FORBIDDEN_SQL.search(query):
        raise ConnectorError(
            "위험 SQL 키워드가 포함되어 실행할 수 없습니다.",
            error_code="UNSAFE_QUERY",
            connector_type=_CONNECTOR,
        )


def _table_columns(ci: dict[str, Any]) -> set[str]:
    schema = ci.get("schema", "public")
    table = ci.get("table")
    if not table:
        return set()
    with _connect(ci) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = %s AND table_name = %s
                """,
                (schema, table),
            )
            return {r[0] for r in cur.fetchall()}


def _ensure_timestamp_column(ci: dict[str, Any], ts_col: str, columns: set[str] | None = None) -> None:
    if not ts_col:
        return
    if not re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", ts_col):
        raise ConnectorError(
            "timestamp_column 형식이 올바르지 않습니다.",
            error_code="INVALID_CONNECTION_INFO",
            connector_type=_CONNECTOR,
        )
    if columns is not None:
        if ts_col not in columns:
            raise ConnectorError(
                f"timestamp_column '{ts_col}'이(가) 소스 스키마에 없습니다.",
                error_code="SCHEMA_DISCOVERY_FAILED",
                connector_type=_CONNECTOR,
            )
        return
    known = _table_columns(ci)
    if known and ts_col not in known:
        raise ConnectorError(
            f"timestamp_column '{ts_col}'이(가) 테이블에 없습니다.",
            error_code="SCHEMA_DISCOVERY_FAILED",
            connector_type=_CONNECTOR,
        )


def _fetch(
    info: dict[str, Any],
    *,
    limit: int | None,
    start_at: datetime | None,
    end_at: datetime | None,
) -> tuple[list[dict[str, Any]], list[str]]:
    ci = _conn_info(info)
    _validate_connection_info(ci)
    custom = (ci.get("query") or "").strip()
    params: list[Any] = []
    if custom:
        _validate_select_query(custom)
        sql = custom
    else:
        schema = ci.get("schema", "public")
        table = ci.get("table")
        sql = f'SELECT * FROM "{schema}"."{table}"'

    ts_col = ci.get("timestamp_column")
    if ts_col and (start_at or end_at):
        _ensure_timestamp_column(ci, ts_col)
        clauses: list[str] = []
        if start_at:
            clauses.append(f'"{ts_col}" >= %s')
            params.append(start_at)
        if end_at:
            clauses.append(f'"{ts_col}" <= %s')
            params.append(end_at)
        if clauses:
            if " where " in sql.lower():
                sql += " AND " + " AND ".join(clauses)
            else:
                sql += " WHERE " + " AND ".join(clauses)

    if limit is not None:
        safe_limit = int(limit)
        if safe_limit < 1:
            raise ConnectorError(
                "limit는 1 이상이어야 합니다.",
                error_code="INGESTION_FAILED",
                connector_type=_CONNECTOR,
            )
        sql += f" LIMIT {safe_limit}"

    try:
        with _connect(ci) as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(sql, params)
                rows = [dict(r) for r in cur.fetchall()]
                columns = [d.name for d in cur.description] if cur.description else []
    except ConnectorError:
        raise
    except Exception as exc:
        raise ConnectorError(
            "데이터 조회에 실패했습니다.",
            error_code="CONNECTION_FAILED",
            connector_type=_CONNECTOR,
            detail=mask_sensitive(str(exc)),
        ) from exc

    if ts_col and columns:
        _ensure_timestamp_column(ci, ts_col, set(columns))
    return rows, columns


def _infer_type(value: Any) -> str:
    if value is None:
        return "unknown"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    if isinstance(value, datetime):
        return "timestamp"
    return "string"


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


class PostgresConnector(BaseConnector):
    source_types = DB_TYPES

    def test_connection(self, source: DataSource) -> dict[str, Any]:
        started = time.perf_counter()
        try:
            rows, columns = _fetch(source.connection_info or {}, limit=5, start_at=None, end_at=None)
            latency_ms = int((time.perf_counter() - started) * 1000)
            return {
                "success": True,
                "message": "연결 테스트에 성공했습니다.",
                "latency_ms": latency_ms,
                "error_message": None,
                "sample_row_count": len(rows),
                "columns": columns,
                "fields": [{"name": c, "data_type": "unknown", "nullable": True} for c in columns],
                "connector_type": _CONNECTOR,
            }
        except Exception as exc:
            latency_ms = int((time.perf_counter() - started) * 1000)
            return _fail_result(exc, latency_ms)

    def discover_schema(self, source: DataSource) -> dict[str, Any]:
        ci = _conn_info(source.connection_info)
        _validate_connection_info(ci)
        custom = (ci.get("query") or "").strip()
        if custom:
            try:
                rows, columns = _fetch(ci, limit=1, start_at=None, end_at=None)
            except ConnectorError:
                raise
            except Exception as exc:
                raise ConnectorError(
                    "스키마 탐색에 실패했습니다.",
                    error_code="SCHEMA_DISCOVERY_FAILED",
                    connector_type=_CONNECTOR,
                    detail=mask_sensitive(str(exc)),
                ) from exc
            if rows:
                sample = rows[0]
                fields = [
                    {"name": c, "data_type": _infer_type(sample.get(c)), "nullable": sample.get(c) is None}
                    for c in columns
                ]
            else:
                fields = [{"name": c, "data_type": "unknown", "nullable": True} for c in columns]
            return {"fields": fields, "connector_type": _CONNECTOR, "source": "query"}

        schema = ci.get("schema", "public")
        table = ci.get("table")
        with _connect(ci) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT column_name, data_type, is_nullable
                    FROM information_schema.columns
                    WHERE table_schema = %s AND table_name = %s
                    ORDER BY ordinal_position
                    """,
                    (schema, table),
                )
                rows = cur.fetchall()
        fields = [
            {"name": r[0], "data_type": r[1], "nullable": r[2] == "YES"}
            for r in rows
        ]
        return {"fields": fields, "connector_type": _CONNECTOR, "source": "information_schema"}

    def preview(
        self,
        source: DataSource,
        *,
        mapping: DataMapping | None = None,
        limit: int = 10,
        start_at: datetime | None = None,
        end_at: datetime | None = None,
    ) -> dict[str, Any]:
        try:
            raw_rows, columns = _fetch(
                source.connection_info or {},
                limit=limit,
                start_at=start_at,
                end_at=end_at,
            )
        except Exception as exc:
            raise ConnectorError(
                "미리보기 조회에 실패했습니다.",
                error_code="PREVIEW_FAILED",
                connector_type=_CONNECTOR,
                detail=mask_sensitive(str(exc)),
            ) from exc
        str_rows = [{k: "" if v is None else str(v) for k, v in row.items()} for row in raw_rows]
        preview_rows = apply_mapping(str_rows, mapping) if mapping else str_rows
        return {"rows": preview_rows[:limit], "columns": columns, "connector_type": _CONNECTOR}

    def fetch_rows(
        self,
        source: DataSource,
        *,
        mapping: DataMapping | None = None,
        start_at: datetime | None = None,
        end_at: datetime | None = None,
        limit: int | None = None,
    ) -> tuple[list[dict[str, Any]], list[str]]:
        raw_rows, columns = _fetch(
            source.connection_info or {},
            limit=limit,
            start_at=start_at,
            end_at=end_at,
        )
        str_rows = [{k: "" if v is None else str(v) for k, v in row.items()} for row in raw_rows]
        if mapping:
            str_rows = apply_mapping(str_rows, mapping)
        return str_rows, columns
