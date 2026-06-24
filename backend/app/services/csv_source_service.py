"""CSV file data source utilities."""

from __future__ import annotations

import csv
import time
from pathlib import Path
from typing import Any

from app.core.config import get_settings

CSV_SOURCE_TYPES = {"CSV", "FILE_CSV"}


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
