"""R11-S5-5 Visual Pipeline node config validation (read-only).

Extends graph validation with NODE_CONFIG_* issues. Does not mutate graph or DB.
"""

from __future__ import annotations

import re
from typing import Any

from app.services.cron_schedule_service import validate_cron_expression

ALLOWED_TIMEZONES = frozenset({"Asia/Seoul", "UTC", "Asia/Tokyo", "America/Los_Angeles"})

SECRET_KEY_RE = re.compile(
    r"(api[_-]?key|apikey|token|password|secret|authorization|auth[_-]?header|auth[_-]?token|bearer)",
    re.IGNORECASE,
)
SECRET_ALLOW_KEYS = frozenset({"credential_ref", "credential_id", "data_source_id"})

# FE overlay / catalog-aligned enums when catalog values are sparse
TRANSFORM_TYPES = frozenset(
    {
        "NONE",
        "WIDE_HOUR_TO_LONG",
        "ASOS_HOURLY_TO_CANONICAL",
        "CALENDAR_SPECIAL_DAY_TO_DATE",
        "CALENDAR_DATE_TO_HOUR",
    }
)
WRITE_MODES = frozenset({"INSERT_ONLY", "DEDUPLICATE", "UPSERT"})
HTTP_METHODS = frozenset({"GET", "POST"})
DUPLICATE_POLICIES = frozenset({"KEEP_FIRST", "KEEP_LAST", "ERROR"})
NULL_UPDATE_POLICIES = frozenset({"KEEP_EXISTING", "OVERWRITE_WITH_NULL"})


def _sev(level: str, *, basic: str = "WARNING", strict: str = "ERROR") -> str:
    return strict if level == "STRICT" else basic


def _is_empty(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str) and value.strip() == "":
        return True
    if isinstance(value, (list, dict)) and len(value) == 0:
        return True
    return False


def _extract_config(node: dict[str, Any]) -> tuple[dict[str, Any] | None, dict[str, Any], str | None]:
    """Return (raw_config_or_none, values, schema_version)."""
    data = node.get("data") if isinstance(node.get("data"), dict) else {}
    raw = data.get("config")
    if raw is None:
        return None, {}, None
    if not isinstance(raw, dict):
        return {}, {}, None
    if "values" in raw and isinstance(raw.get("values"), dict):
        schema_version = raw.get("schema_version")
        sv = str(schema_version) if isinstance(schema_version, str) else None
        if schema_version is None:
            sv = None
        return raw, dict(raw["values"]), sv
    # Legacy flat config
    meta = {"schema_version", "values", "validation"}
    values = {k: v for k, v in raw.items() if k not in meta}
    schema_version = raw.get("schema_version")
    sv = str(schema_version) if isinstance(schema_version, str) else None
    return raw, values, sv


def _issue(
    *,
    severity: str,
    code: str,
    message: str,
    node_id: str,
    component_type: str,
    field_key: str | None = None,
    hint: str | None = None,
) -> dict[str, Any]:
    item: dict[str, Any] = {
        "severity": severity,
        "code": code,
        "message": message,
        "phase": "CONFIG",
        "node_id": node_id,
        "component_type": component_type,
    }
    if field_key:
        item["field_key"] = field_key
    if hint:
        item["hint"] = hint
    return item


def _eval_required_if(expr: str | None, values: dict[str, Any]) -> bool:
    """Support simple forms: 'write_mode in [DEDUPLICATE, UPSERT]'."""
    if not expr:
        return False
    text = expr.strip()
    m = re.match(r"^(\w+)\s+in\s+\[([^\]]+)\]$", text, re.IGNORECASE)
    if not m:
        return False
    key = m.group(1)
    opts = [p.strip().strip("'\"") for p in m.group(2).split(",")]
    return str(values.get(key, "")) in opts


def _scan_secrets(values: dict[str, Any], node_id: str, ctype: str, level: str) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    sev = _sev(level)

    def walk(obj: Any, path: str) -> None:
        if isinstance(obj, dict):
            for k, v in obj.items():
                key = str(k)
                child = f"{path}.{key}" if path else key
                if key.lower() in SECRET_ALLOW_KEYS or key.endswith("_ref"):
                    walk(v, child)
                    continue
                if SECRET_KEY_RE.search(key):
                    issues.append(
                        _issue(
                            severity=sev,
                            code="NODE_CONFIG_SECRET_INLINE_NOT_ALLOWED",
                            message=f"Secret-like key '{key}' must not be stored in graph values.",
                            node_id=node_id,
                            component_type=ctype,
                            field_key=key,
                            hint="credential_ref 등 참조만 저장하세요.",
                        )
                    )
                walk(v, child)
        elif isinstance(obj, list):
            for i, v in enumerate(obj):
                walk(v, f"{path}[{i}]")
        elif isinstance(obj, str):
            s = obj.strip()
            if re.match(r"^(Bearer|Basic)\s+\S+", s, re.IGNORECASE) or re.match(r"^sk-[A-Za-z0-9]{8,}", s):
                issues.append(
                    _issue(
                        severity=sev,
                        code="NODE_CONFIG_SECRET_INLINE_NOT_ALLOWED",
                        message=f"Secret-like value detected at '{path or '(root)'}'.",
                        node_id=node_id,
                        component_type=ctype,
                        field_key=path.split(".")[0] if path else None,
                        hint="원문 secret 대신 credential_ref를 사용하세요.",
                    )
                )

    walk(values, "")
    return issues


def _check_enum(
    *,
    values: dict[str, Any],
    field: str,
    allowed: frozenset[str] | set[str] | list[str],
    node_id: str,
    ctype: str,
    level: str,
    code: str = "NODE_CONFIG_UNSUPPORTED_MODE",
) -> list[dict[str, Any]]:
    if field not in values or _is_empty(values.get(field)):
        return []
    raw = str(values.get(field))
    if raw not in set(allowed):
        return [
            _issue(
                severity=_sev(level),
                code=code,
                message=f"Unsupported value for {field}: {raw}",
                node_id=node_id,
                component_type=ctype,
                field_key=field,
                hint=f"허용: {', '.join(sorted(allowed))}",
            )
        ]
    return []


def _validate_rest(values: dict[str, Any], node_id: str, ctype: str, level: str) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    sev = _sev(level)
    if _is_empty(values.get("operation_name")):
        issues.append(
            _issue(
                severity=sev,
                code="NODE_CONFIG_REST_OPERATION_MISSING",
                message="operation_name is required.",
                node_id=node_id,
                component_type=ctype,
                field_key="operation_name",
            )
        )
    if _is_empty(values.get("endpoint_path")):
        issues.append(
            _issue(
                severity=sev,
                code="NODE_CONFIG_REST_ENDPOINT_MISSING",
                message="endpoint_path is required.",
                node_id=node_id,
                component_type=ctype,
                field_key="endpoint_path",
            )
        )
    if _is_empty(values.get("data_source_id")):
        issues.append(
            _issue(
                severity=sev,
                code="NODE_CONFIG_REQUIRED_FIELD_MISSING",
                message="data_source_id is required.",
                node_id=node_id,
                component_type=ctype,
                field_key="data_source_id",
            )
        )
    if _is_empty(values.get("http_method")):
        issues.append(
            _issue(
                severity=sev,
                code="NODE_CONFIG_REQUIRED_FIELD_MISSING",
                message="http_method is required.",
                node_id=node_id,
                component_type=ctype,
                field_key="http_method",
            )
        )
    else:
        issues.extend(
            _check_enum(
                values=values,
                field="http_method",
                allowed=HTTP_METHODS,
                node_id=node_id,
                ctype=ctype,
                level=level,
                code="NODE_CONFIG_FIELD_INVALID",
            )
        )
    for obj_field in ("request_params", "pagination"):
        if obj_field in values and values[obj_field] is not None and not isinstance(values[obj_field], dict):
            issues.append(
                _issue(
                    severity=sev,
                    code="NODE_CONFIG_FIELD_INVALID",
                    message=f"{obj_field} must be an object.",
                    node_id=node_id,
                    component_type=ctype,
                    field_key=obj_field,
                )
            )
    return issues


def _validate_transform(values: dict[str, Any], node_id: str, ctype: str, level: str, catalog_values: list[str] | None) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    sev = _sev(level)
    allowed = set(catalog_values) if catalog_values else set(TRANSFORM_TYPES)
    if _is_empty(values.get("transform_type")):
        issues.append(
            _issue(
                severity=sev,
                code="NODE_CONFIG_REQUIRED_FIELD_MISSING",
                message="transform_type is required.",
                node_id=node_id,
                component_type=ctype,
                field_key="transform_type",
            )
        )
    else:
        issues.extend(
            _check_enum(
                values=values,
                field="transform_type",
                allowed=allowed,
                node_id=node_id,
                ctype=ctype,
                level=level,
                code="NODE_CONFIG_TRANSFORM_TYPE_INVALID",
            )
        )
    if "mapping_config" in values and values["mapping_config"] is not None and not isinstance(values["mapping_config"], dict):
        issues.append(
            _issue(
                severity=sev,
                code="NODE_CONFIG_MAPPING_INVALID",
                message="mapping_config must be an object.",
                node_id=node_id,
                component_type=ctype,
                field_key="mapping_config",
            )
        )
    if "hour_policy" in values and values["hour_policy"] is not None and not isinstance(values["hour_policy"], dict):
        issues.append(
            _issue(
                severity=sev,
                code="NODE_CONFIG_FIELD_INVALID",
                message="hour_policy must be an object.",
                node_id=node_id,
                component_type=ctype,
                field_key="hour_policy",
            )
        )
    return issues


def _validate_upsert(values: dict[str, Any], node_id: str, ctype: str, level: str) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    sev = _sev(level)
    if _is_empty(values.get("target_table")):
        issues.append(
            _issue(
                severity=sev,
                code="NODE_CONFIG_TARGET_MISSING",
                message="target_table is required.",
                node_id=node_id,
                component_type=ctype,
                field_key="target_table",
            )
        )
    if _is_empty(values.get("write_mode")):
        issues.append(
            _issue(
                severity=sev,
                code="NODE_CONFIG_REQUIRED_FIELD_MISSING",
                message="write_mode is required.",
                node_id=node_id,
                component_type=ctype,
                field_key="write_mode",
            )
        )
    else:
        issues.extend(
            _check_enum(
                values=values,
                field="write_mode",
                allowed=WRITE_MODES,
                node_id=node_id,
                ctype=ctype,
                level=level,
                code="NODE_CONFIG_WRITE_MODE_INVALID",
            )
        )
    write_mode = str(values.get("write_mode") or "")
    keys = values.get("conflict_key_columns_json")
    if write_mode in {"DEDUPLICATE", "UPSERT"}:
        if _is_empty(keys):
            issues.append(
                _issue(
                    severity=sev,
                    code="NODE_CONFIG_KEY_COLUMNS_MISSING",
                    message="conflict_key_columns_json is required for DEDUPLICATE/UPSERT.",
                    node_id=node_id,
                    component_type=ctype,
                    field_key="conflict_key_columns_json",
                )
            )
        elif not isinstance(keys, list) or not all(isinstance(x, str) for x in keys):
            issues.append(
                _issue(
                    severity=sev,
                    code="NODE_CONFIG_KEY_COLUMNS_INVALID",
                    message="conflict_key_columns_json must be an array of strings.",
                    node_id=node_id,
                    component_type=ctype,
                    field_key="conflict_key_columns_json",
                )
            )
    elif keys is not None and not _is_empty(keys):
        if not isinstance(keys, list) or not all(isinstance(x, str) for x in keys):
            issues.append(
                _issue(
                    severity=sev,
                    code="NODE_CONFIG_KEY_COLUMNS_INVALID",
                    message="conflict_key_columns_json must be an array of strings.",
                    node_id=node_id,
                    component_type=ctype,
                    field_key="conflict_key_columns_json",
                )
            )
    issues.extend(
        _check_enum(
            values=values,
            field="duplicate_within_batch_policy",
            allowed=DUPLICATE_POLICIES,
            node_id=node_id,
            ctype=ctype,
            level=level,
            code="NODE_CONFIG_FIELD_INVALID",
        )
    )
    issues.extend(
        _check_enum(
            values=values,
            field="null_update_policy",
            allowed=NULL_UPDATE_POLICIES,
            node_id=node_id,
            ctype=ctype,
            level=level,
            code="NODE_CONFIG_FIELD_INVALID",
        )
    )
    if "save_dedup_summary_yn" in values and values["save_dedup_summary_yn"] is not None:
        if not isinstance(values["save_dedup_summary_yn"], bool):
            issues.append(
                _issue(
                    severity=sev,
                    code="NODE_CONFIG_FIELD_INVALID",
                    message="save_dedup_summary_yn must be a boolean.",
                    node_id=node_id,
                    component_type=ctype,
                    field_key="save_dedup_summary_yn",
                )
            )
    return issues


def _validate_cron(values: dict[str, Any], node_id: str, ctype: str, level: str) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    sev = _sev(level)
    if not _is_empty(values.get("schedule_type")) and str(values.get("schedule_type")) != "CRON":
        issues.append(
            _issue(
                severity=sev,
                code="NODE_CONFIG_UNSUPPORTED_MODE",
                message="schedule_type must be CRON in MVP.",
                node_id=node_id,
                component_type=ctype,
                field_key="schedule_type",
            )
        )
    cron_expr = values.get("cron_expression")
    if _is_empty(cron_expr):
        issues.append(
            _issue(
                severity=sev,
                code="NODE_CONFIG_CRON_INVALID",
                message="cron_expression is required.",
                node_id=node_id,
                component_type=ctype,
                field_key="cron_expression",
            )
        )
    else:
        result = validate_cron_expression(str(cron_expr))
        if not result.get("valid"):
            err = (result.get("errors") or ["invalid cron"])[0]
            issues.append(
                _issue(
                    severity=sev,
                    code="NODE_CONFIG_CRON_INVALID",
                    message=f"Invalid cron_expression: {err}",
                    node_id=node_id,
                    component_type=ctype,
                    field_key="cron_expression",
                )
            )
    tz = values.get("timezone")
    if _is_empty(tz):
        issues.append(
            _issue(
                severity=sev,
                code="NODE_CONFIG_TIMEZONE_INVALID",
                message="timezone is required.",
                node_id=node_id,
                component_type=ctype,
                field_key="timezone",
            )
        )
    elif str(tz) not in ALLOWED_TIMEZONES:
        issues.append(
            _issue(
                severity=sev,
                code="NODE_CONFIG_TIMEZONE_INVALID",
                message=f"Unsupported timezone: {tz}",
                node_id=node_id,
                component_type=ctype,
                field_key="timezone",
                hint=f"허용: {', '.join(sorted(ALLOWED_TIMEZONES))}",
            )
        )
    for bool_key in ("active_yn", "retry_enabled_yn"):
        if bool_key in values and values[bool_key] is not None and not isinstance(values[bool_key], bool):
            issues.append(
                _issue(
                    severity=sev,
                    code="NODE_CONFIG_FIELD_INVALID",
                    message=f"{bool_key} must be a boolean.",
                    node_id=node_id,
                    component_type=ctype,
                    field_key=bool_key,
                )
            )
    for num_key, minimum in (("max_retry_count", 0), ("retry_interval_minutes", 1)):
        if num_key not in values or values[num_key] is None:
            continue
        v = values[num_key]
        if isinstance(v, bool) or not isinstance(v, (int, float)) or int(v) != v or int(v) < minimum:
            issues.append(
                _issue(
                    severity=sev,
                    code="NODE_CONFIG_RETRY_INVALID",
                    message=f"{num_key} must be an integer >= {minimum}.",
                    node_id=node_id,
                    component_type=ctype,
                    field_key=num_key,
                )
            )
    return issues


def validate_node_configs(
    nodes: list[dict[str, Any]],
    catalog: dict[str, dict[str, Any]],
    *,
    validation_level: str = "BASIC",
) -> list[dict[str, Any]]:
    level = str(validation_level or "BASIC").strip().upper()
    if level not in {"BASIC", "STRICT"}:
        level = "BASIC"

    issues: list[dict[str, Any]] = []
    for node in nodes:
        nid = str(node.get("id") or "")
        data = node.get("data") if isinstance(node.get("data"), dict) else {}
        ctype = str(node.get("type") or data.get("component_type") or "").strip().upper()
        if not nid or not ctype or ctype not in catalog:
            continue

        raw_config, values, schema_version = _extract_config(node)
        if raw_config is None:
            issues.append(
                _issue(
                    severity="WARNING",
                    code="NODE_CONFIG_MISSING",
                    message=f"Node {nid} has no config values.",
                    node_id=nid,
                    component_type=ctype,
                    hint="Inspector에서 config를 설정하세요.",
                )
            )
            # Continue with empty values so required checks still fire
            values = {}
        elif not values:
            issues.append(
                _issue(
                    severity="WARNING",
                    code="NODE_CONFIG_MISSING",
                    message=f"Node {nid} config.values is empty.",
                    node_id=nid,
                    component_type=ctype,
                )
            )

        if schema_version is None:
            issues.append(
                _issue(
                    severity="WARNING" if level == "STRICT" else "INFO",
                    code="NODE_CONFIG_SCHEMA_VERSION_MISSING",
                    message=f"Node {nid} config.schema_version is missing (legacy).",
                    node_id=nid,
                    component_type=ctype,
                )
            )

        issues.extend(_scan_secrets(values, nid, ctype, level))

        comp = catalog.get(ctype) or {}
        schema_fields = comp.get("config_schema") if isinstance(comp.get("config_schema"), list) else []
        field_by_name = {f.get("name"): f for f in schema_fields if isinstance(f, dict) and f.get("name")}

        # Generic required_if / remaining required (skip fields with specific codes)
        specific_required = {
            "VP_REST_API_SOURCE": {"operation_name", "endpoint_path", "data_source_id", "http_method"},
            "VP_TRANSFORM": {"transform_type"},
            "VP_UPSERT_LOAD": {"target_table", "write_mode", "conflict_key_columns_json"},
            "VP_CRON_SCHEDULE": {"cron_expression", "timezone", "schedule_type"},
        }
        skip_required = specific_required.get(ctype, set())

        for fname, fdef in field_by_name.items():
            if fname in skip_required:
                continue
            need = bool(fdef.get("required")) or _eval_required_if(fdef.get("required_if"), values)
            if need and _is_empty(values.get(fname)):
                issues.append(
                    _issue(
                        severity=_sev(level),
                        code="NODE_CONFIG_REQUIRED_FIELD_MISSING",
                        message=f"{fname} is required.",
                        node_id=nid,
                        component_type=ctype,
                        field_key=fname,
                    )
                )
            enum_vals = fdef.get("values")
            if enum_vals and fname in values and not _is_empty(values.get(fname)):
                if str(values.get(fname)) not in set(enum_vals):
                    issues.append(
                        _issue(
                            severity=_sev(level),
                            code="NODE_CONFIG_UNSUPPORTED_MODE",
                            message=f"Unsupported value for {fname}: {values.get(fname)}",
                            node_id=nid,
                            component_type=ctype,
                            field_key=fname,
                        )
                    )

        if ctype == "VP_REST_API_SOURCE":
            issues.extend(_validate_rest(values, nid, ctype, level))
        elif ctype == "VP_TRANSFORM":
            tfield = field_by_name.get("transform_type") or {}
            issues.extend(_validate_transform(values, nid, ctype, level, tfield.get("values")))
        elif ctype == "VP_UPSERT_LOAD":
            issues.extend(_validate_upsert(values, nid, ctype, level))
        elif ctype == "VP_CRON_SCHEDULE":
            issues.extend(_validate_cron(values, nid, ctype, level))

    return issues
