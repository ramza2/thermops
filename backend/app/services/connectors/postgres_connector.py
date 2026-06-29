"""PostgreSQL DB Connector."""

from __future__ import annotations

import re
import time
from datetime import datetime
from typing import Any

import psycopg2
import psycopg2.extras

from app.models.entities import DataMapping, DataSource
from app.services.connectors.base import BaseConnector, ConnectorError
from app.services.mapping_service import apply_mapping

DB_TYPES = {"DB_POSTGRES", "DB"}
_FORBIDDEN_SQL = re.compile(
    r"\b(DROP|DELETE|UPDATE|INSERT|ALTER|TRUNCATE|CREATE|GRANT|REVOKE)\b",
    re.IGNORECASE,
)


def _conn_info(info: dict[str, Any] | None) -> dict[str, Any]:
    if not info:
        raise ConnectorError("connection_info가 필요합니다.")
    return info


def _connect(info: dict[str, Any]):
    ci = _conn_info(info)
    return psycopg2.connect(
        host=ci.get("host", "localhost"),
        port=int(ci.get("port", 5432)),
        dbname=ci.get("database") or ci.get("dbname"),
        user=ci.get("username") or ci.get("user"),
        password=ci.get("password", ""),
        connect_timeout=int(ci.get("connect_timeout", 10)),
    )


def _validate_select_query(query: str) -> None:
    if _FORBIDDEN_SQL.search(query):
        raise ConnectorError("SELECT 쿼리만 허용됩니다.")


def _build_query(info: dict[str, Any]) -> tuple[str, list[Any]]:
    ci = _conn_info(info)
    params: list[Any] = []
    custom = (ci.get("query") or "").strip()
    if custom:
        _validate_select_query(custom)
        base = f"({custom}) AS src"
    else:
        schema = ci.get("schema", "public")
        table = ci.get("table")
        if not table:
            raise ConnectorError("connection_info.table 또는 query가 필요합니다.")
        base = f'"{schema}"."{table}"'

    ts_col = ci.get("timestamp_column")
  # placeholder for time filter appended by caller
    return base, params


def _fetch(
    info: dict[str, Any],
    *,
    limit: int | None,
    start_at: datetime | None,
    end_at: datetime | None,
) -> tuple[list[dict[str, Any]], list[str]]:
    ci = _conn_info(info)
    custom = (ci.get("query") or "").strip()
    params: list[Any] = []
    if custom:
        _validate_select_query(custom)
        sql = custom
    else:
        schema = ci.get("schema", "public")
        table = ci.get("table")
        if not table:
            raise ConnectorError("connection_info.table 또는 query가 필요합니다.")
        sql = f'SELECT * FROM "{schema}"."{table}"'

    ts_col = ci.get("timestamp_column")
    clauses: list[str] = []
    if ts_col and (start_at or end_at):
        if not re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", ts_col):
            raise ConnectorError("timestamp_column 형식이 올바르지 않습니다.")
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
    if limit:
        sql += f" LIMIT {int(limit)}"

    with _connect(ci) as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, params)
            rows = [dict(r) for r in cur.fetchall()]
            columns = [d.name for d in cur.description] if cur.description else []
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
                "connector_type": "DB_POSTGRES",
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
                "connector_type": "DB_POSTGRES",
            }

    def discover_schema(self, source: DataSource) -> dict[str, Any]:
        ci = _conn_info(source.connection_info)
        custom = (ci.get("query") or "").strip()
        if custom:
            rows, columns = _fetch(ci, limit=1, start_at=None, end_at=None)
            fields = []
            if rows:
                sample = rows[0]
                fields = [
                    {"name": c, "data_type": _infer_type(sample.get(c)), "nullable": sample.get(c) is None}
                    for c in columns
                ]
            else:
                fields = [{"name": c, "data_type": "unknown", "nullable": True} for c in columns]
            return {"fields": fields, "connector_type": "DB_POSTGRES", "source": "query"}

        schema = ci.get("schema", "public")
        table = ci.get("table")
        if not table:
            raise ConnectorError("table 또는 query가 필요합니다.")
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
        return {"fields": fields, "connector_type": "DB_POSTGRES", "source": "information_schema"}

    def preview(
        self,
        source: DataSource,
        *,
        mapping: DataMapping | None = None,
        limit: int = 10,
        start_at: datetime | None = None,
        end_at: datetime | None = None,
    ) -> dict[str, Any]:
        raw_rows, columns = _fetch(
            source.connection_info or {},
            limit=limit,
            start_at=start_at,
            end_at=end_at,
        )
        str_rows = [{k: "" if v is None else str(v) for k, v in row.items()} for row in raw_rows]
        preview_rows = apply_mapping(str_rows, mapping) if mapping else str_rows
        return {"rows": preview_rows[:limit], "columns": columns, "connector_type": "DB_POSTGRES"}

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
