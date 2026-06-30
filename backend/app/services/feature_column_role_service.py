"""Feature Column Role 저장·조회·추론·검증."""

from __future__ import annotations

import re
from typing import Any
from uuid import uuid4

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.time import utc_now
from app.models.entities import DataMapping, FeatureColumnRole

COLUMN_ROLE_CODES: frozenset[str] = frozenset({
    "ENTITY_KEY",
    "TIME_KEY",
    "TARGET",
    "NUMERIC_INPUT",
    "CATEGORICAL_INPUT",
    "BOOLEAN_INPUT",
    "JOIN_KEY",
    "EXCLUDE",
    "ID",
    "TEXT",
    "LOCATION",
    "DATETIME",
    "MEASURE",
})

ROLE_CODE_META: list[dict[str, Any]] = [
    {
        "code": "ENTITY_KEY",
        "label": "개체 키",
        "description": "시계열 그룹 기준이 되는 키 (지사, 매장, 설비 등)",
        "feature_candidate": False,
        "required_for": ["LAG", "ROLLING", "DIFF"],
    },
    {
        "code": "TIME_KEY",
        "label": "시간 키",
        "description": "시계열 정렬·shift 기준 시각 컬럼",
        "feature_candidate": False,
        "required_for": ["LAG", "ROLLING", "DIFF", "DATE_PART"],
    },
    {
        "code": "TARGET",
        "label": "예측 대상",
        "description": "모델 학습 라벨(타깃) 컬럼",
        "feature_candidate": False,
        "required_for": [],
    },
    {
        "code": "NUMERIC_INPUT",
        "label": "수치 입력",
        "description": "수치형 Feature 입력 컬럼",
        "feature_candidate": True,
        "required_for": ["LAG", "ROLLING", "RATIO", "BINNING"],
    },
    {
        "code": "CATEGORICAL_INPUT",
        "label": "범주 입력",
        "description": "범주형 Feature 입력 컬럼",
        "feature_candidate": True,
        "required_for": ["CATEGORY_ENCODING"],
    },
    {
        "code": "BOOLEAN_INPUT",
        "label": "불리언 입력",
        "description": "0/1 또는 Y/N 불리언 컬럼",
        "feature_candidate": True,
        "required_for": [],
    },
    {
        "code": "JOIN_KEY",
        "label": "조인 키",
        "description": "테이블 조인에 사용되는 키",
        "feature_candidate": False,
        "required_for": [],
    },
    {
        "code": "EXCLUDE",
        "label": "제외",
        "description": "Feature 후보에서 제외",
        "feature_candidate": False,
        "required_for": [],
    },
    {
        "code": "ID",
        "label": "식별자",
        "description": "학습 Feature로 기본 제외되는 식별자",
        "feature_candidate": False,
        "required_for": [],
    },
    {
        "code": "TEXT",
        "label": "텍스트",
        "description": "자유 텍스트 컬럼 (1차 Recipe 미지원)",
        "feature_candidate": False,
        "required_for": [],
    },
    {
        "code": "LOCATION",
        "label": "위치",
        "description": "위도·경도·주소 등 위치 정보",
        "feature_candidate": False,
        "required_for": [],
    },
    {
        "code": "DATETIME",
        "label": "날짜/시간",
        "description": "날짜·시간 원본 컬럼 (DATE_PART 파생 가능)",
        "feature_candidate": True,
        "required_for": ["DATE_PART"],
    },
    {
        "code": "MEASURE",
        "label": "측정값",
        "description": "센서·계량 측정값 (수치 입력과 유사)",
        "feature_candidate": True,
        "required_for": ["LAG", "ROLLING"],
    },
]

FEATURE_CANDIDATE_ROLES = frozenset(
    m["code"] for m in ROLE_CODE_META if m.get("feature_candidate")
)

TARGET_TABLE_PRESETS: dict[str, dict[str, str]] = {
    "heat_demand_actual": {
        "site_id": "ENTITY_KEY",
        "measured_at": "TIME_KEY",
        "heat_demand": "TARGET",
        "supply_temp": "NUMERIC_INPUT",
        "return_temp": "NUMERIC_INPUT",
        "flow_rate": "NUMERIC_INPUT",
    },
    "tb_heat_demand_actual": {
        "site_id": "ENTITY_KEY",
        "measured_at": "TIME_KEY",
        "heat_demand": "TARGET",
        "supply_temp": "NUMERIC_INPUT",
    },
    "weather_observation": {
        "weather_area_id": "ENTITY_KEY",
        "measured_at": "TIME_KEY",
        "temperature": "NUMERIC_INPUT",
        "humidity": "NUMERIC_INPUT",
        "rainfall": "NUMERIC_INPUT",
        "wind_speed": "NUMERIC_INPUT",
        "data_type": "CATEGORICAL_INPUT",
    },
    "tb_weather_observation": {
        "weather_area_id": "ENTITY_KEY",
        "measured_at": "TIME_KEY",
        "temperature": "NUMERIC_INPUT",
        "humidity": "NUMERIC_INPUT",
    },
    "calendar": {
        "calendar_date": "TIME_KEY",
        "day_of_week": "NUMERIC_INPUT",
        "is_weekend": "BOOLEAN_INPUT",
        "is_holiday": "BOOLEAN_INPUT",
        "season": "CATEGORICAL_INPUT",
    },
    "tb_calendar": {
        "calendar_date": "TIME_KEY",
        "day_of_week": "NUMERIC_INPUT",
        "is_weekend": "BOOLEAN_INPUT",
        "is_holiday": "BOOLEAN_INPUT",
    },
}

_TIME_NAME_RE = re.compile(r"(^|_)(at|date|time|timestamp|datetime)($|_)", re.I)
_ID_NAME_RE = re.compile(r"(^|_)(id|_id|code)($|_)", re.I)
_TARGET_NAME_RE = re.compile(r"(heat_demand|demand|sales|amount|target|qty|quantity|y$)", re.I)
_MEASURE_NAME_RE = re.compile(
    r"(temperature|humidity|pressure|speed|count|qty|value|measure|rainfall|wind)", re.I
)
_LOCATION_NAME_RE = re.compile(r"(address|lat|lon|latitude|longitude|location)", re.I)
_TEXT_NAME_RE = re.compile(r"(text|content|description|memo|comment)", re.I)
_CATEGORY_NAME_RE = re.compile(r"(type|category|status|season|gender)", re.I)
_BOOLEAN_NAME_RE = re.compile(r"(is_|has_|flag|weekend|holiday)", re.I)


def list_role_codes() -> list[dict[str, Any]]:
    return list(ROLE_CODE_META)


def _normalize_table_key(target_table: str | None) -> str:
    if not target_table:
        return ""
    return target_table.lower().replace("tb_", "")


def _preset_role(target_table: str | None, column_name: str) -> str | None:
    if not target_table or not column_name:
        return None
    table_key = _normalize_table_key(target_table)
    for key in (target_table, table_key, f"tb_{table_key}"):
        preset = TARGET_TABLE_PRESETS.get(key)
        if preset and column_name in preset:
            return preset[column_name]
    return None


def _is_datetime_type(data_type: str | None) -> bool:
    if not data_type:
        return False
    dt = data_type.upper()
    return any(x in dt for x in ("DATE", "TIME", "TIMESTAMP"))


def infer_column_role(
    *,
    source_column: str,
    target_column: str | None = None,
    data_type: str | None = None,
    cardinality: int | None = None,
    target_table: str | None = None,
) -> tuple[str, float]:
    """단일 컬럼 role 추론. (role, confidence 0~100)."""
    col = (target_column or source_column or "").strip()
    src = (source_column or "").strip()
    name = col or src
    lower = name.lower()

    preset = _preset_role(target_table, col) or _preset_role(target_table, src)
    if preset:
        return preset, 95.0

    if _BOOLEAN_NAME_RE.search(lower) or (data_type and data_type.upper() in ("BOOL", "BOOLEAN")):
        return "BOOLEAN_INPUT", 85.0

    if _TIME_NAME_RE.search(lower) or _is_datetime_type(data_type):
        if lower in ("measured_at", "observed_at", "calendar_date", "transaction_date"):
            return "TIME_KEY", 92.0
        return "DATETIME", 80.0

    if lower in ("heat_demand", "target", "label", "y"):
        return "TARGET", 90.0
    if _TARGET_NAME_RE.search(lower) and (not data_type or "NUM" in data_type.upper() or data_type.upper() == "DECIMAL"):
        return "TARGET", 75.0

    if lower in ("site_id", "store_id", "equipment_id", "customer_id", "weather_area_id"):
        if lower == "weather_area_id" and _normalize_table_key(target_table) == "weather_observation":
            return "ENTITY_KEY", 90.0
        return "ENTITY_KEY", 88.0

    if _ID_NAME_RE.search(lower):
        if lower.endswith("_id") and lower not in ("site_id", "weather_area_id"):
            return "ID", 70.0
        return "ENTITY_KEY", 65.0

    if _LOCATION_NAME_RE.search(lower):
        return "LOCATION", 80.0

    if _TEXT_NAME_RE.search(lower):
        return "TEXT", 75.0

    if _CATEGORY_NAME_RE.search(lower):
        if cardinality is not None and cardinality <= 50:
            return "CATEGORICAL_INPUT", 82.0
        return "CATEGORICAL_INPUT", 70.0

    if _MEASURE_NAME_RE.search(lower):
        return "MEASURE", 82.0

    if data_type:
        upper = data_type.upper()
        if upper in ("STRING", "VARCHAR", "TEXT", "CHAR"):
            if cardinality is not None and cardinality <= 50:
                return "CATEGORICAL_INPUT", 72.0
            return "TEXT", 60.0
        if upper in ("INT", "INTEGER", "BIGINT", "FLOAT", "DOUBLE", "NUMERIC", "DECIMAL", "NUMBER"):
            return "NUMERIC_INPUT", 70.0
        if upper in ("BOOL", "BOOLEAN"):
            return "BOOLEAN_INPUT", 85.0

    return "NUMERIC_INPUT", 50.0


def infer_column_roles(
    columns: list[dict[str, Any]],
    *,
    target_table: str | None = None,
    source_table: str | None = None,
) -> list[dict[str, Any]]:
    _ = source_table
    results: list[dict[str, Any]] = []
    for col in columns:
        src = str(col.get("source_column") or "").strip()
        tgt = str(col.get("target_column") or "").strip() or None
        if not src and not tgt:
            continue
        role, confidence = infer_column_role(
            source_column=src,
            target_column=tgt,
            data_type=col.get("data_type"),
            cardinality=col.get("cardinality"),
            target_table=target_table,
        )
        results.append({
            "source_column": src,
            "target_column": tgt,
            "data_type": col.get("data_type"),
            "column_role": role,
            "inferred_role": role,
            "inference_confidence": round(confidence, 2),
            "role_source": "INFERRED",
            "saved": False,
        })
    return results


def validate_column_roles(
    roles: list[dict[str, Any]],
    *,
    mapping_columns: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    infos: list[str] = []

    seen_keys: set[str] = set()
    entity_keys = 0
    time_keys = 0
    target_keys = 0
    time_key_columns: list[str] = []
    entity_columns: list[str] = []

    known_columns: set[str] = set()
    if mapping_columns:
        for c in mapping_columns:
            if c.get("source_column"):
                known_columns.add(str(c["source_column"]))
            if c.get("target_column"):
                known_columns.add(str(c["target_column"]))

    for item in roles:
        role = str(item.get("column_role") or "").strip()
        src = str(item.get("source_column") or "").strip()
        tgt = str(item.get("target_column") or "").strip()
        key = src or tgt

        if not key:
            errors.append("source_column이 비어 있는 역할 행이 있습니다.")
            continue

        if role not in COLUMN_ROLE_CODES:
            errors.append(f"지원하지 않는 column_role: {role} ({key})")
            continue

        dedupe = f"{src}|{tgt}"
        if dedupe in seen_keys:
            errors.append(f"중복 컬럼 역할: {key}")
        seen_keys.add(dedupe)

        if mapping_columns and src and src not in known_columns and tgt not in known_columns:
            warnings.append(f"매핑 컬럼 목록에 없는 컬럼: {key}")

        if role == "ENTITY_KEY":
            entity_keys += 1
            entity_columns.append(key)
        elif role == "TIME_KEY":
            time_keys += 1
            time_key_columns.append(key)
        elif role == "TARGET":
            target_keys += 1
        elif role == "EXCLUDE":
            infos.append(f"{key}: Feature 후보에서 제외됩니다.")
        elif role == "ID":
            infos.append(f"{key}: 식별자로 기본 Feature 후보에서 제외됩니다. ENTITY_KEY가 필요하면 역할을 변경하세요.")

    for col in entity_columns:
        if col in time_key_columns:
            errors.append(f"ENTITY_KEY와 TIME_KEY가 동일 컬럼입니다: {col}")

    if time_keys == 0:
        warnings.append("TIME_KEY가 지정되지 않았습니다. 시계열 Feature Recipe(LAG/ROLLING/DIFF)를 사용할 수 없습니다.")
    elif time_keys > 1:
        errors.append(f"TIME_KEY는 1개만 지정할 수 있습니다. 현재 {time_keys}개: {', '.join(time_key_columns)}")

    if entity_keys == 0:
        warnings.append("ENTITY_KEY가 지정되지 않았습니다. 그룹 기준 시계열 Feature Recipe를 사용할 수 없습니다.")

    if target_keys == 0:
        warnings.append("TARGET이 지정되지 않았습니다. 학습 라벨 연결 시 TARGET 지정을 권장합니다.")
    elif target_keys > 1:
        warnings.append(f"TARGET이 {target_keys}개 지정되었습니다. 다중 타깃 학습은 아직 지원하지 않습니다.")

    blocking = len(errors) > 0
    return {
        "valid": not blocking,
        "blocking": blocking,
        "errors": errors,
        "warnings": warnings,
        "infos": infos,
    }


def summarize_role_coverage(roles: list[dict[str, Any]]) -> dict[str, Any]:
    counts: dict[str, int] = {code: 0 for code in COLUMN_ROLE_CODES}
    feature_candidate_count = 0
    for item in roles:
        role = str(item.get("column_role") or "")
        if role in counts:
            counts[role] += 1
        if role in FEATURE_CANDIDATE_ROLES:
            feature_candidate_count += 1

    entity_key_count = counts.get("ENTITY_KEY", 0)
    time_key_count = counts.get("TIME_KEY", 0)
    target_count = counts.get("TARGET", 0)
    numeric_count = counts.get("NUMERIC_INPUT", 0) + counts.get("MEASURE", 0)
    categorical_count = counts.get("CATEGORICAL_INPUT", 0)
    datetime_count = counts.get("DATETIME", 0)

    time_series_ready = entity_key_count >= 1 and time_key_count == 1 and numeric_count >= 1
    ratio_ready = numeric_count >= 2
    encoding_ready = categorical_count >= 1
    date_part_ready = time_key_count == 1 or datetime_count >= 1

    return {
        "entity_key_count": entity_key_count,
        "time_key_count": time_key_count,
        "target_count": target_count,
        "numeric_input_count": counts.get("NUMERIC_INPUT", 0),
        "measure_count": counts.get("MEASURE", 0),
        "categorical_input_count": categorical_count,
        "boolean_input_count": counts.get("BOOLEAN_INPUT", 0),
        "feature_candidate_count": feature_candidate_count,
        "recipe_readiness": {
            "time_series": {
                "ready": time_series_ready,
                "message": (
                    "LAG/ROLLING/DIFF 템플릿 사용 가능"
                    if time_series_ready
                    else "ENTITY_KEY, TIME_KEY(1개), 수치 입력이 필요합니다."
                ),
            },
            "ratio": {
                "ready": ratio_ready,
                "message": (
                    "RATIO 템플릿 사용 가능"
                    if ratio_ready
                    else "수치 입력 컬럼이 2개 이상 필요합니다."
                ),
            },
            "encoding": {
                "ready": encoding_ready,
                "message": (
                    "CATEGORY_ENCODING 템플릿 사용 가능"
                    if encoding_ready
                    else "범주 입력 컬럼이 필요합니다."
                ),
            },
            "date_part": {
                "ready": date_part_ready,
                "message": (
                    "DATE_PART 템플릿 사용 가능"
                    if date_part_ready
                    else "TIME_KEY 또는 DATETIME 컬럼이 필요합니다."
                ),
            },
        },
    }


def merge_mapping_columns_with_roles(
    mapping_columns: list[dict[str, Any]],
    saved_roles: list[FeatureColumnRole],
    inferred_roles: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    saved_by_src = {r.source_column: r for r in saved_roles if r.active_yn == "Y"}
    inferred_by_src = {
        str(i.get("source_column")): i for i in (inferred_roles or []) if i.get("source_column")
    }

    merged: list[dict[str, Any]] = []
    for col in mapping_columns:
        src = str(col.get("source_column") or "").strip()
        tgt = str(col.get("target_column") or "").strip() or None
        if not src:
            continue

        saved = saved_by_src.get(src)
        inferred = inferred_by_src.get(src)

        if saved:
            merged.append({
                "role_id": saved.role_id,
                "source_column": src,
                "target_column": saved.target_column or tgt,
                "data_type": saved.data_type or col.get("data_type"),
                "column_role": saved.column_role,
                "inferred_role": saved.inferred_role or (inferred or {}).get("inferred_role"),
                "inference_confidence": float(saved.inference_confidence)
                if saved.inference_confidence is not None
                else (inferred or {}).get("inference_confidence"),
                "role_source": saved.role_source,
                "description": saved.description,
                "saved": True,
            })
        elif inferred:
            merged.append({**inferred, "target_column": tgt or inferred.get("target_column"), "saved": False})
        else:
            merged.append({
                "source_column": src,
                "target_column": tgt,
                "data_type": col.get("data_type"),
                "column_role": None,
                "inferred_role": None,
                "inference_confidence": None,
                "role_source": None,
                "saved": False,
            })
    return merged


def _role_to_dict(row: FeatureColumnRole) -> dict[str, Any]:
    return {
        "role_id": row.role_id,
        "mapping_id": row.mapping_id,
        "data_source_id": row.data_source_id,
        "source_table": row.source_table,
        "target_table": row.target_table,
        "source_column": row.source_column,
        "target_column": row.target_column,
        "data_type": row.data_type,
        "column_role": row.column_role,
        "inferred_role": row.inferred_role,
        "inference_confidence": float(row.inference_confidence)
        if row.inference_confidence is not None
        else None,
        "role_source": row.role_source,
        "description": row.description,
        "saved": True,
    }


async def get_mapping_or_raise(db: AsyncSession, mapping_id: str) -> DataMapping:
    row = (
        await db.execute(select(DataMapping).where(DataMapping.mapping_id == mapping_id))
    ).scalar_one_or_none()
    if not row:
        raise LookupError(f"매핑을 찾을 수 없습니다: {mapping_id}")
    return row


async def list_column_roles(
    db: AsyncSession,
    *,
    mapping_id: str | None = None,
    data_source_id: str | None = None,
    target_table: str | None = None,
    source_table: str | None = None,
    include_inferred: bool = False,
) -> dict[str, Any]:
    clauses = [FeatureColumnRole.active_yn == "Y"]
    if mapping_id:
        clauses.append(FeatureColumnRole.mapping_id == mapping_id)
    if data_source_id:
        clauses.append(FeatureColumnRole.data_source_id == data_source_id)
    if target_table:
        clauses.append(FeatureColumnRole.target_table == target_table)
    if source_table:
        clauses.append(FeatureColumnRole.source_table == source_table)

    rows = (
        await db.execute(
            select(FeatureColumnRole).where(and_(*clauses)).order_by(FeatureColumnRole.source_column)
        )
    ).scalars().all()

    mapping_columns: list[dict[str, Any]] = []
    mapping: DataMapping | None = None
    if mapping_id:
        mapping = await get_mapping_or_raise(db, mapping_id)
        mapping_columns = list(mapping.columns or [])
        if not data_source_id:
            data_source_id = mapping.source_id
        if not target_table:
            target_table = mapping.target_table

    items: list[dict[str, Any]]
    if include_inferred and mapping_columns:
        inferred = infer_column_roles(
            mapping_columns,
            target_table=target_table,
            source_table=source_table,
        )
        items = merge_mapping_columns_with_roles(mapping_columns, rows, inferred)
    else:
        items = [_role_to_dict(r) for r in rows]

    role_values = [
        {"source_column": i["source_column"], "target_column": i.get("target_column"), "column_role": i["column_role"]}
        for i in items
        if i.get("column_role")
    ]
    validation = validate_column_roles(role_values, mapping_columns=mapping_columns or None)
    summary = summarize_role_coverage(role_values)

    return {
        "items": items,
        "mapping_id": mapping_id,
        "data_source_id": data_source_id,
        "target_table": target_table,
        "summary": summary,
        "validation": validation,
    }


async def upsert_column_roles(
    db: AsyncSession,
    mapping_id: str,
    roles: list[dict[str, Any]],
) -> dict[str, Any]:
    mapping = await get_mapping_or_raise(db, mapping_id)
    mapping_columns = list(mapping.columns or [])

    validation = validate_column_roles(roles, mapping_columns=mapping_columns)
    if validation["blocking"]:
        raise ValueError("; ".join(validation["errors"]))

    existing_rows = (
        await db.execute(
            select(FeatureColumnRole).where(
                FeatureColumnRole.mapping_id == mapping_id,
                FeatureColumnRole.active_yn == "Y",
            )
        )
    ).scalars().all()
    existing_by_src = {r.source_column: r for r in existing_rows}

    saved_items: list[dict[str, Any]] = []
    now = utc_now()

    for item in roles:
        src = str(item.get("source_column") or "").strip()
        role = str(item.get("column_role") or "").strip()
        if not src or not role:
            continue

        inferred_role, confidence = infer_column_role(
            source_column=src,
            target_column=item.get("target_column"),
            data_type=item.get("data_type"),
            target_table=mapping.target_table,
        )

        row = existing_by_src.get(src)
        if row:
            row.target_column = item.get("target_column") or row.target_column
            row.data_type = item.get("data_type") or row.data_type
            row.column_role = role
            row.inferred_role = inferred_role
            row.inference_confidence = confidence
            row.role_source = "MANUAL"
            row.description = item.get("description")
            row.target_table = mapping.target_table
            row.data_source_id = mapping.source_id
            row.updated_at = now
            saved_items.append(_role_to_dict(row))
        else:
            new_row = FeatureColumnRole(
                role_id=f"FCR-{uuid4().hex[:6].upper()}",
                mapping_id=mapping_id,
                data_source_id=mapping.source_id,
                target_table=mapping.target_table,
                source_column=src,
                target_column=item.get("target_column"),
                data_type=item.get("data_type"),
                column_role=role,
                inferred_role=inferred_role,
                inference_confidence=confidence,
                role_source="MANUAL",
                description=item.get("description"),
                active_yn="Y",
                created_at=now,
                updated_at=now,
            )
            db.add(new_row)
            saved_items.append(_role_to_dict(new_row))

    await db.flush()

    role_values = [
        {"source_column": i["source_column"], "target_column": i.get("target_column"), "column_role": i["column_role"]}
        for i in saved_items
    ]
    all_saved = (
        await db.execute(
            select(FeatureColumnRole).where(
                FeatureColumnRole.mapping_id == mapping_id,
                FeatureColumnRole.active_yn == "Y",
            )
        )
    ).scalars().all()
    all_role_values = [
        {"source_column": r.source_column, "target_column": r.target_column, "column_role": r.column_role}
        for r in all_saved
    ]
    final_validation = validate_column_roles(all_role_values, mapping_columns=mapping_columns)
    summary = summarize_role_coverage(all_role_values)

    return {
        "saved_count": len(saved_items),
        "items": [_role_to_dict(r) for r in all_saved],
        "summary": summary,
        "validation": final_validation,
    }
