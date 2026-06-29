"""CSV / FILE_CSV Connector."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from app.models.entities import DataMapping, DataSource
from app.services.connectors.base import BaseConnector
from app.services.csv_source_service import read_csv_rows, test_csv_connection
from app.services.mapping_service import apply_mapping

CSV_TYPES = {"CSV", "FILE_CSV"}


class CsvConnector(BaseConnector):
    source_types = CSV_TYPES

    def test_connection(self, source: DataSource) -> dict[str, Any]:
        result = test_csv_connection(source.connection_info)
        fields = [
            {"name": c, "data_type": "string", "nullable": True}
            for c in result.get("columns") or []
        ]
        return {**result, "fields": fields, "connector_type": "CSV"}

    def discover_schema(self, source: DataSource) -> dict[str, Any]:
        _, columns = read_csv_rows(source.connection_info)
        return {
            "fields": [{"name": c, "data_type": "string", "nullable": True} for c in columns],
            "connector_type": "CSV",
        }

    def preview(
        self,
        source: DataSource,
        *,
        mapping: DataMapping | None = None,
        limit: int = 10,
        start_at: datetime | None = None,
        end_at: datetime | None = None,
    ) -> dict[str, Any]:
        raw_rows, columns = read_csv_rows(source.connection_info)
        if start_at or end_at:
            ts_col = "measured_at"
            filtered = []
            for row in raw_rows:
                val = row.get(ts_col) or row.get("target_at")
                if not val:
                    filtered.append(row)
                    continue
                try:
                    dt = datetime.fromisoformat(str(val).replace("Z", "+00:00")).replace(tzinfo=None)
                except ValueError:
                    filtered.append(row)
                    continue
                if start_at and dt < start_at:
                    continue
                if end_at and dt > end_at:
                    continue
                filtered.append(row)
            raw_rows = filtered
        preview_rows = raw_rows[:limit]
        if mapping:
            preview_rows = apply_mapping(preview_rows, mapping)[:limit]
        return {"rows": preview_rows, "columns": columns, "connector_type": "CSV"}

    def fetch_rows(
        self,
        source: DataSource,
        *,
        mapping: DataMapping | None = None,
        start_at: datetime | None = None,
        end_at: datetime | None = None,
        limit: int | None = None,
    ) -> tuple[list[dict[str, Any]], list[str]]:
        preview = self.preview(
            source,
            mapping=None,
            limit=limit or 10_000_000,
            start_at=start_at,
            end_at=end_at,
        )
        raw_rows = preview["rows"]
        columns = preview["columns"]
        if mapping:
            raw_rows = apply_mapping(raw_rows, mapping)
        if limit:
            raw_rows = raw_rows[:limit]
        return raw_rows, columns
