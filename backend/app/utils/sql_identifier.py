"""PostgreSQL identifier validation for managed physical table wizard (R9-S2-1)."""

from __future__ import annotations

import re
from typing import Any

IDENTIFIER_RE = re.compile(r"^[a-z][a-z0-9_]{0,62}$")
TABLE_NAME_RE = re.compile(r"^[a-z][a-z0-9_]{2,62}$")

MANAGED_TABLE_PREFIX = "std_"
ALLOWED_SCHEMA = "public"

BLOCKED_TABLE_PREFIXES = ("tb_", "pg_", "sql_")
BLOCKED_SCHEMAS = ("pg_catalog", "information_schema", "pg_toast")

POSTGRES_RESERVED = frozenset({
    "all", "analyse", "analyze", "and", "any", "array", "as", "asc", "asymmetric",
    "authorization", "binary", "both", "case", "cast", "check", "collate", "column",
    "constraint", "create", "cross", "current_catalog", "current_date", "current_role",
    "current_schema", "current_time", "current_timestamp", "current_user", "default",
    "deferrable", "desc", "distinct", "do", "else", "end", "except", "false", "fetch",
    "for", "foreign", "from", "grant", "group", "having", "in", "initially", "inner",
    "intersect", "into", "is", "isnull", "join", "lateral", "leading", "left", "like",
    "limit", "localtime", "localtimestamp", "natural", "not", "notnull", "null", "offset",
    "on", "only", "or", "order", "outer", "over", "placing", "primary", "references",
    "returning", "right", "select", "session_user", "similar", "some", "symmetric",
    "table", "tablesample", "then", "to", "trailing", "true", "union", "unique", "user",
    "using", "variadic", "verbose", "when", "where", "window", "with",
})


def _issue(code: str, message: str) -> dict[str, str]:
    return {"code": code, "message": message}


def quote_ident(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def normalize_physical_table_name(raw: str) -> str:
    return raw.strip().lower()


def suggest_physical_table_name(dataset_code: str) -> str:
    code = re.sub(r"[^a-z0-9_]+", "_", dataset_code.strip().lower())
    code = re.sub(r"_+", "_", code).strip("_")
    if not code:
        code = "dataset"
    if not code.startswith(MANAGED_TABLE_PREFIX):
        code = f"{MANAGED_TABLE_PREFIX}{code}"
    return code[:63]


def validate_schema_name(schema: str | None) -> list[dict[str, str]]:
    schema_name = (schema or ALLOWED_SCHEMA).strip().lower()
    if schema_name != ALLOWED_SCHEMA:
        return [_issue("INVALID_SCHEMA", f"허용된 스키마는 '{ALLOWED_SCHEMA}'만 가능합니다.")]
    if schema_name in BLOCKED_SCHEMAS:
        return [_issue("INVALID_SCHEMA", f"스키마 '{schema_name}'에는 테이블을 생성할 수 없습니다.")]
    return []


def validate_table_identifier(
    table_name: str,
    *,
    require_managed_prefix: bool = True,
) -> list[dict[str, str]]:
    errors: list[dict[str, str]] = []
    name = normalize_physical_table_name(table_name)
    if not name:
        return [_issue("INVALID_TABLE_NAME", "물리 테이블명을 입력하세요.")]
    if not TABLE_NAME_RE.match(name):
        errors.append(_issue("INVALID_TABLE_NAME", "테이블명은 소문자 영문으로 시작하고 3~63자의 영문/숫자/underscore만 허용됩니다."))
    if require_managed_prefix and not name.startswith(MANAGED_TABLE_PREFIX):
        errors.append(_issue("INVALID_TABLE_NAME", f"Wizard 생성 테이블은 '{MANAGED_TABLE_PREFIX}' prefix가 필요합니다."))
    for prefix in BLOCKED_TABLE_PREFIXES:
        if name.startswith(prefix):
            errors.append(_issue("SYSTEM_PREFIX_NOT_ALLOWED", f"시스템/레거시 prefix '{prefix}'는 사용할 수 없습니다."))
            break
    if name in POSTGRES_RESERVED:
        errors.append(_issue("RESERVED_TABLE_NAME", f"예약어 '{name}'는 테이블명으로 사용할 수 없습니다."))
    if any(ch in name for ch in (';', '"', "'", " ", ".", "-")):
        errors.append(_issue("INVALID_TABLE_NAME", "테이블명에 허용되지 않는 문자가 포함되어 있습니다."))
    return errors


def validate_column_identifier(column_name: str) -> list[dict[str, str]]:
    errors: list[dict[str, str]] = []
    name = normalize_physical_table_name(column_name)
    if not name:
        return [_issue("INVALID_COLUMN_NAME", "컬럼명을 입력하세요.")]
    if not IDENTIFIER_RE.match(name):
        errors.append(_issue("INVALID_COLUMN_NAME", "컬럼명은 소문자 영문으로 시작하고 1~63자의 영문/숫자/underscore만 허용됩니다."))
    if name in POSTGRES_RESERVED:
        errors.append(_issue("RESERVED_COLUMN_NAME", f"예약어 '{name}'는 컬럼명으로 사용할 수 없습니다."))
    if any(ch in name for ch in (';', '"', "'", " ", ".", "-")):
        errors.append(_issue("INVALID_COLUMN_NAME", "컬럼명에 허용되지 않는 문자가 포함되어 있습니다."))
    return errors


ALLOWED_LOGICAL_TYPES = frozenset({
    "TEXT", "VARCHAR", "INTEGER", "BIGINT", "NUMERIC", "DOUBLE", "BOOLEAN",
    "DATE", "TIMESTAMP", "TIMESTAMPTZ", "JSONB",
    # legacy R7 logical labels
    "STRING", "DATETIME", "NUMERIC_INPUT",
})


def validate_column_definition(col: dict[str, Any]) -> list[dict[str, str]]:
    errors: list[dict[str, str]] = []
    name = str(col.get("column_name") or "").strip()
    errors.extend(validate_column_identifier(name))

    data_type = str(col.get("data_type") or "TEXT").strip().upper()
    if data_type == "STRING":
        data_type = "VARCHAR"
    if data_type == "DATETIME":
        data_type = "TIMESTAMP"
    if data_type == "NUMERIC_INPUT":
        data_type = "NUMERIC"
    if data_type not in ALLOWED_LOGICAL_TYPES and data_type not in {"VARCHAR", "NUMERIC", "DOUBLE PRECISION"}:
        errors.append(_issue("INVALID_DATA_TYPE", f"허용되지 않는 데이터 타입: {data_type}"))

    if data_type == "VARCHAR":
        length = col.get("data_length")
        if length is None:
            length = 255
        try:
            length_i = int(length)
        except (TypeError, ValueError):
            errors.append(_issue("INVALID_LENGTH", "VARCHAR length는 정수여야 합니다."))
        else:
            if not 1 <= length_i <= 4000:
                errors.append(_issue("INVALID_LENGTH", "VARCHAR length는 1~4000 범위여야 합니다."))

    if data_type == "NUMERIC":
        precision = col.get("numeric_precision")
        scale = col.get("numeric_scale")
        if precision is None:
            precision = 18
        if scale is None:
            scale = 6
        try:
            p = int(precision)
            s = int(scale)
        except (TypeError, ValueError):
            errors.append(_issue("INVALID_NUMERIC_PRECISION", "NUMERIC precision/scale는 정수여야 합니다."))
        else:
            if not 1 <= p <= 38:
                errors.append(_issue("INVALID_NUMERIC_PRECISION", "NUMERIC precision은 1~38 범위여야 합니다."))
            if not 0 <= s <= p:
                errors.append(_issue("INVALID_NUMERIC_PRECISION", "NUMERIC scale은 0~precision 범위여야 합니다."))

    return errors


def render_postgres_type(col: dict[str, Any]) -> str:
    data_type = str(col.get("data_type") or "TEXT").strip().upper()
    if data_type == "STRING":
        data_type = "VARCHAR"
    if data_type == "DATETIME":
        data_type = "TIMESTAMP"
    if data_type == "NUMERIC_INPUT":
        data_type = "NUMERIC"

    if data_type == "VARCHAR":
        length = int(col.get("data_length") or 255)
        return f"VARCHAR({length})"
    if data_type == "NUMERIC":
        precision = int(col.get("numeric_precision") or 18)
        scale = int(col.get("numeric_scale") or 6)
        return f"NUMERIC({precision},{scale})"
    if data_type == "DOUBLE":
        return "DOUBLE PRECISION"
    mapping = {
        "TEXT": "TEXT",
        "INTEGER": "INTEGER",
        "BIGINT": "BIGINT",
        "BOOLEAN": "BOOLEAN",
        "DATE": "DATE",
        "TIMESTAMP": "TIMESTAMP",
        "TIMESTAMPTZ": "TIMESTAMPTZ",
        "JSONB": "JSONB",
    }
    return mapping.get(data_type, "TEXT")
