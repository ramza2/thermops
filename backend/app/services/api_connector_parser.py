"""REST API 응답 파싱 — JSON/XML/TEXT."""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from typing import Any

from app.utils.json_path import JsonPathError, extract_json_path


def parse_response_body(text: str, response_format: str) -> Any:
    fmt = (response_format or "JSON").upper()
    if fmt == "JSON" or fmt == "AUTO":
        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            if fmt == "AUTO":
                return _parse_xml(text)
            raise ValueError("JSON 응답 파싱에 실패했습니다.") from exc
    if fmt == "XML":
        return _parse_xml(text)
    if fmt == "TEXT":
        return text
    raise ValueError(f"지원하지 않는 응답 형식: {response_format}")


def _parse_xml(text: str) -> dict[str, Any]:
    root = ET.fromstring(text)
    return {root.tag: _xml_to_dict(root)}


def _xml_to_dict(node: ET.Element) -> Any:
    children = list(node)
    if not children:
        return (node.text or "").strip()
    result: dict[str, Any] = {}
    for child in children:
        val = _xml_to_dict(child)
        if child.tag in result:
            existing = result[child.tag]
            if not isinstance(existing, list):
                result[child.tag] = [existing]
            result[child.tag].append(val)
        else:
            result[child.tag] = val
    return result


def normalize_items(
    payload: Any,
    *,
    item_path: str | None,
    array_mode: str = "AUTO",
) -> list[dict[str, Any]]:
    try:
        items = extract_json_path(payload, item_path) if item_path else payload
    except JsonPathError as exc:
        raise ValueError(str(exc)) from exc

    mode = (array_mode or "AUTO").upper()
    if items is None:
        return []
    if isinstance(items, list):
        return [i for i in items if isinstance(i, dict)]
    if isinstance(items, dict):
        if mode == "ARRAY":
            return []
        return [items]
    if mode == "SINGLE_OBJECT" and isinstance(items, (str, int, float, bool)):
        return [{"value": items}]
    raise ValueError("응답 데이터 경로가 객체 배열을 가리키지 않습니다.")
