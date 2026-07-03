"""JSON dot path 추출."""

from __future__ import annotations

from typing import Any


class JsonPathError(ValueError):
    pass


def extract_json_path(data: Any, path: str | None) -> Any:
    if not path or path in ("$", ""):
        return data
    cleaned = path.strip()
    if cleaned.startswith("$."):
        cleaned = cleaned[2:]
    if cleaned.startswith("$"):
        cleaned = cleaned[1:].lstrip(".")
    current = data
    for part in cleaned.split("."):
        if part == "":
            continue
        if isinstance(current, dict):
            current = current.get(part)
        elif isinstance(current, list):
            try:
                current = current[int(part)]
            except (ValueError, IndexError) as exc:
                raise JsonPathError(f"경로 해석 실패: {path}") from exc
        else:
            raise JsonPathError(f"경로 해석 실패: {path}")
    return current
