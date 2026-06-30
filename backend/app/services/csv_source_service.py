"""CSV file data source utilities."""

from __future__ import annotations

import csv
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from app.core.config import get_settings

CSV_SOURCE_TYPES = {"CSV", "FILE_CSV"}
_TIMESTAMP_COLUMNS = ("measured_at", "target_at")


def is_csv_source(source_type: str) -> bool:
    return source_type.upper() in CSV_SOURCE_TYPES


def resolve_file_path(connection_info: dict[str, Any] | None) -> Path:
    if not connection_info or not connection_info.get("file_path"):
        raise ValueError("connection_info.file_path가 필요합니다.")
    raw = str(connection_info["file_path"]).strip()
    path = Path(raw)
    if path.is_absolute():
        return path
    root = get_settings().project_root
    return (root / raw).resolve()


def read_csv_rows(connection_info: dict[str, Any] | None) -> tuple[list[dict[str, str]], list[str]]:
    path = resolve_file_path(connection_info)
    if not path.exists():
        raise FileNotFoundError(f"CSV 파일을 찾을 수 없습니다: {path}")
    if not path.is_file():
        raise ValueError(f"경로가 파일이 아닙니다: {path}")

    encoding = (connection_info or {}).get("encoding", "utf-8")
    delimiter = (connection_info or {}).get("delimiter", ",")

    with path.open("r", encoding=encoding, newline="") as f:
        reader = csv.DictReader(f, delimiter=delimiter)
        if not reader.fieldnames:
            raise ValueError("CSV 헤더(컬럼명)가 없습니다.")
        rows = [dict(row) for row in reader]
    return rows, list(reader.fieldnames)


def test_csv_connection(connection_info: dict[str, Any] | None) -> dict[str, Any]:
    started = time.perf_counter()
    try:
        rows, columns = read_csv_rows(connection_info)
        latency_ms = int((time.perf_counter() - started) * 1000)
        return {
            "success": True,
            "message": "연결 테스트에 성공했습니다.",
            "latency_ms": latency_ms,
            "error_message": None,
            "sample_row_count": len(rows),
            "columns": columns,
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
        }


def _parse_row_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        return None


def get_csv_data_range(connection_info: dict[str, Any] | None) -> dict[str, Any]:
    rows, columns = read_csv_rows(connection_info)
    ts_col = next((c for c in _TIMESTAMP_COLUMNS if c in columns), None)
    if not ts_col:
        return {
            "exists": False,
            "row_count": len(rows),
            "valid_timestamp_count": 0,
            "min_at": None,
            "max_at": None,
            "timestamp_column": None,
        }

    min_dt: datetime | None = None
    max_dt: datetime | None = None
    valid_count = 0
    for row in rows:
        dt = _parse_row_timestamp(row.get(ts_col))
        if dt is None:
            continue
        valid_count += 1
        if min_dt is None or dt < min_dt:
            min_dt = dt
        if max_dt is None or dt > max_dt:
            max_dt = dt

    return {
        "exists": min_dt is not None and max_dt is not None,
        "row_count": len(rows),
        "valid_timestamp_count": valid_count,
        "min_at": min_dt.isoformat() if min_dt else None,
        "max_at": max_dt.isoformat() if max_dt else None,
        "timestamp_column": ts_col,
    }
