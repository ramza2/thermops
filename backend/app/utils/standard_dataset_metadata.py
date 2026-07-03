"""표준 데이터셋 메타데이터 분류 (R9-S2-2)."""

from __future__ import annotations

import json
import re
from typing import Any

DATASET_CATEGORY_SPECS: list[dict[str, str]] = [
    {"code": "MASTER", "name": "기준/마스터", "description": "기준·마스터 데이터"},
    {"code": "FACT", "name": "실적/집계", "description": "실적·집계 Fact 데이터"},
    {"code": "TIMESERIES", "name": "시계열", "description": "시간 축 관측·측정 데이터"},
    {"code": "EVENT", "name": "이벤트", "description": "이벤트·상태 변화 데이터"},
    {"code": "TRANSACTION", "name": "거래/이력", "description": "거래·이력 트랜잭션 데이터"},
    {"code": "LOG", "name": "로그", "description": "로그·감사 추적 데이터"},
    {"code": "MAPPING", "name": "매핑", "description": "코드·엔티티 매핑 데이터"},
    {"code": "CUSTOM", "name": "사용자 정의", "description": "사용자 정의 분류"},
]

DATASET_CATEGORY_CODES = {spec["code"] for spec in DATASET_CATEGORY_SPECS}

_LEGACY_CATEGORY_ALIASES = {
    "TIME_SERIES": "TIMESERIES",
    "CODE": "MASTER",
    "SENSOR": "TIMESERIES",
}

MAX_BUSINESS_DOMAIN_LEN = 100
MAX_TAGS = 20
MAX_TAG_LEN = 30


def normalize_dataset_category(value: str | None, *, required: bool = True) -> str:
    raw = (value or "").strip().upper()
    if not raw:
        if required:
            return "CUSTOM"
        return ""
    raw = _LEGACY_CATEGORY_ALIASES.get(raw, raw)
    if raw not in DATASET_CATEGORY_CODES:
        allowed = ", ".join(sorted(DATASET_CATEGORY_CODES))
        raise ValueError(f"dataset_category는 다음 값 중 하나여야 합니다: {allowed}")
    return raw


def normalize_business_domain(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = re.sub(r"\s+", " ", str(value).strip())
    if not cleaned:
        return None
    if len(cleaned) > MAX_BUSINESS_DOMAIN_LEN:
        raise ValueError(f"business_domain은 {MAX_BUSINESS_DOMAIN_LEN}자 이하여야 합니다.")
    return cleaned


def normalize_tags(value: Any) -> list[str] | None:
    if value is None:
        return None
    items: list[str]
    if isinstance(value, str):
        items = [part.strip() for part in value.split(",")]
    elif isinstance(value, list):
        items = [str(part).strip() for part in value]
    else:
        raise ValueError("tags는 문자열 배열 또는 comma-separated 문자열이어야 합니다.")

    seen: set[str] = set()
    normalized: list[str] = []
    for item in items:
        if not item:
            continue
        if len(item) > MAX_TAG_LEN:
            raise ValueError(f"각 tag는 {MAX_TAG_LEN}자 이하여야 합니다.")
        key = item.casefold()
        if key in seen:
            continue
        seen.add(key)
        normalized.append(item)
        if len(normalized) > MAX_TAGS:
            raise ValueError(f"tags는 최대 {MAX_TAGS}개까지 등록할 수 있습니다.")
    return normalized or None


def tags_to_json(tags: list[str] | None) -> list[str] | None:
    return normalize_tags(tags)


def tags_from_json(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return normalize_tags(value) or []
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            if isinstance(parsed, list):
                return normalize_tags(parsed) or []
        except json.JSONDecodeError:
            return normalize_tags(value) or []
    return []


def resolve_metadata_fields(payload: dict[str, Any]) -> dict[str, Any]:
    """Create/Update payload에서 dataset_category, business_domain, tags를 정규화."""
    category_raw = payload.get("dataset_category")
    if category_raw is None:
        category_raw = payload.get("category")
    dataset_category = normalize_dataset_category(category_raw)

    business_domain = payload.get("business_domain")
    if business_domain is None and payload.get("domain") is not None:
        legacy = str(payload.get("domain") or "").strip()
        if legacy and legacy.upper() in {"HEAT_DEMAND", "WEATHER", "MASTER", "FACILITY", "COST", "EMISSION", "OPERATION"}:
            _legacy_labels = {
                "HEAT_DEMAND": "열수요",
                "WEATHER": "기상",
                "MASTER": "기준정보",
                "FACILITY": "설비",
            }
            business_domain = _legacy_labels.get(legacy.upper(), legacy)
        else:
            business_domain = legacy or None
    business_domain = normalize_business_domain(business_domain)

    tags = None
    if "tags" in payload:
        tags = normalize_tags(payload.get("tags"))

    return {
        "dataset_category": dataset_category,
        "business_domain": business_domain,
        "tags": tags,
    }


def dataset_category_options() -> list[dict[str, str]]:
    return [dict(spec) for spec in DATASET_CATEGORY_SPECS]
