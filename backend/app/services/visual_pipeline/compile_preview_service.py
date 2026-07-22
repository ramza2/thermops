"""R11-S6-1 Visual Pipeline Compile Preview (read-only, no persistence).

Converts a STRICT-valid VISUAL_DATA_LOAD graph into a compiled artifact JSON.
Does not write DB, update sync status, materialize R10 targets, or call externals.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any

from app.services.visual_pipeline.config_validation_service import (
    SECRET_ALLOW_KEYS,
    SECRET_KEY_RE,
    TRANSFORM_TYPES,
    _extract_config,
)
from app.services.visual_pipeline.graph_schema_service import normalize_graph
from app.services.visual_pipeline.graph_validation_service import (
    _node_component_type,
    validate_visual_pipeline_graph,
)

COMPILE_VERSION = "R11-S6-1"

REST_CONFIG_KEYS = (
    "data_source_id",
    "operation_name",
    "endpoint_path",
    "http_method",
    "request_params",
    "pagination",
    "response_item_path",
    "credential_ref",
)
TRANSFORM_CONFIG_KEYS = (
    "transform_type",
    "mapping_config",
    "unmapped_policy",
    "hour_policy",
)
UPSERT_CONFIG_KEYS = (
    "standard_dataset_id",
    "target_table",
    "write_mode",
    "conflict_key_columns_json",
    "duplicate_within_batch_policy",
    "null_update_policy",
    "save_dedup_summary_yn",
)
CRON_CONFIG_KEYS = (
    "schedule_type",
    "cron_expression",
    "timezone",
    "start_at",
    "end_at",
    "active_yn",
    "retry_enabled_yn",
    "max_retry_count",
    "retry_interval_minutes",
)


def make_compile_issue(
    *,
    code: str,
    message: str,
    severity: str = "ERROR",
    node_id: str | None = None,
    component_type: str | None = None,
    field_key: str | None = None,
    details: Any = None,
    hint: str | None = None,
) -> dict[str, Any]:
    item: dict[str, Any] = {
        "severity": severity,
        "code": code,
        "message": message,
        "phase": "COMPILE",
    }
    if node_id:
        item["node_id"] = node_id
    if component_type:
        item["component_type"] = component_type
    if field_key:
        item["field_key"] = field_key
    if details is not None:
        item["details"] = details
    if hint:
        item["hint"] = hint
    return item


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def _sha256_prefixed(payload: Any) -> str:
    digest = hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def _node_values(node: dict[str, Any]) -> dict[str, Any]:
    _, values, _ = _extract_config(node)
    return values


def _node_schema_version(node: dict[str, Any]) -> str | None:
    _, _, schema_version = _extract_config(node)
    return schema_version


def calculate_graph_version_hash(graph: dict[str, Any] | None) -> str:
    """Hash semantic graph fields only (D6). Excludes viewport/position/label/validation."""
    try:
        normalized = normalize_graph(graph)
    except Exception:
        normalized = graph if isinstance(graph, dict) else {"nodes": [], "edges": []}

    nodes_payload: list[dict[str, Any]] = []
    for node in list(normalized.get("nodes") or []):
        if not isinstance(node, dict):
            continue
        nid = str(node.get("id") or "")
        ctype = _node_component_type(node)
        schema_version = _node_schema_version(node)
        values = _node_values(node)
        nodes_payload.append(
            {
                "id": nid,
                "component_type": ctype,
                "schema_version": schema_version,
                "values": values,
            }
        )
    nodes_payload.sort(key=lambda n: n["id"])

    edges_payload: list[dict[str, Any]] = []
    for edge in list(normalized.get("edges") or []):
        if not isinstance(edge, dict):
            continue
        data = edge.get("data") if isinstance(edge.get("data"), dict) else {}
        edges_payload.append(
            {
                "source": edge.get("source"),
                "target": edge.get("target"),
                "sourceHandle": edge.get("sourceHandle") or edge.get("source_handle"),
                "targetHandle": edge.get("targetHandle") or edge.get("target_handle"),
                "source_port": data.get("source_port"),
                "target_port": data.get("target_port"),
                "data_type": data.get("data_type"),
            }
        )
    edges_payload.sort(
        key=lambda e: (
            str(e.get("source") or ""),
            str(e.get("target") or ""),
            str(e.get("sourceHandle") or ""),
            str(e.get("targetHandle") or ""),
        )
    )
    return _sha256_prefixed({"nodes": nodes_payload, "edges": edges_payload})


def calculate_config_hash(graph: dict[str, Any] | None) -> str:
    """Hash of node config.values only (sorted by node id)."""
    try:
        normalized = normalize_graph(graph)
    except Exception:
        normalized = graph if isinstance(graph, dict) else {"nodes": [], "edges": []}

    items: list[dict[str, Any]] = []
    for node in list(normalized.get("nodes") or []):
        if not isinstance(node, dict):
            continue
        items.append({"id": str(node.get("id") or ""), "values": _node_values(node)})
    items.sort(key=lambda n: n["id"])
    return _sha256_prefixed(items)


def _pick_config(values: dict[str, Any], keys: tuple[str, ...]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key in keys:
        if key in values:
            out[key] = values[key]
    return out


def _contains_secret_like(values: dict[str, Any]) -> list[str]:
    found: list[str] = []

    def walk(obj: Any, path: str) -> None:
        if isinstance(obj, dict):
            for k, v in obj.items():
                key = str(k)
                child = f"{path}.{key}" if path else key
                if key.lower() in SECRET_ALLOW_KEYS or key.endswith("_ref"):
                    walk(v, child)
                    continue
                if SECRET_KEY_RE.search(key):
                    found.append(key)
                walk(v, child)
        elif isinstance(obj, list):
            for i, v in enumerate(obj):
                walk(v, f"{path}[{i}]")

    walk(values, "")
    return found


def _step_id(kind: str, node_id: str) -> str:
    return f"{kind}-{node_id}"


def extract_compile_nodes(graph: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    try:
        normalized = normalize_graph(graph)
    except Exception:
        normalized = graph if isinstance(graph, dict) else {"nodes": [], "edges": []}

    buckets: dict[str, list[dict[str, Any]]] = {
        "VP_REST_API_SOURCE": [],
        "VP_TRANSFORM": [],
        "VP_UPSERT_LOAD": [],
        "VP_CRON_SCHEDULE": [],
        "OTHER": [],
    }
    for node in list(normalized.get("nodes") or []):
        if not isinstance(node, dict):
            continue
        ctype = _node_component_type(node)
        if ctype in buckets:
            buckets[ctype].append(node)
        else:
            buckets["OTHER"].append(node)
    return buckets


def _check_mvp_shape(buckets: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    rest = buckets["VP_REST_API_SOURCE"]
    load = buckets["VP_UPSERT_LOAD"]
    xform = buckets["VP_TRANSFORM"]
    cron = buckets["VP_CRON_SCHEDULE"]
    other = buckets["OTHER"]

    if other:
        for node in other:
            ctype = _node_component_type(node)
            issues.append(
                make_compile_issue(
                    code="COMPILE_GRAPH_UNSUPPORTED_SHAPE",
                    message=f"Unsupported or non-MVP component for compile: {ctype or '(missing)'}",
                    node_id=str(node.get("id") or ""),
                    component_type=ctype or None,
                )
            )
    if len(rest) != 1:
        issues.append(
            make_compile_issue(
                code="COMPILE_GRAPH_UNSUPPORTED_SHAPE",
                message=f"MVP requires exactly 1 REST source, found {len(rest)}.",
                details={"count": len(rest), "component_type": "VP_REST_API_SOURCE"},
            )
        )
    if len(load) != 1:
        issues.append(
            make_compile_issue(
                code="COMPILE_GRAPH_UNSUPPORTED_SHAPE",
                message=f"MVP requires exactly 1 Upsert load, found {len(load)}.",
                details={"count": len(load), "component_type": "VP_UPSERT_LOAD"},
            )
        )
    if len(xform) > 1:
        issues.append(
            make_compile_issue(
                code="COMPILE_GRAPH_UNSUPPORTED_SHAPE",
                message=f"MVP allows at most 1 Transform, found {len(xform)}.",
                details={"count": len(xform), "component_type": "VP_TRANSFORM"},
            )
        )
    if len(cron) > 1:
        issues.append(
            make_compile_issue(
                code="COMPILE_GRAPH_UNSUPPORTED_SHAPE",
                message=f"MVP allows at most 1 CRON schedule, found {len(cron)}.",
                details={"count": len(cron), "component_type": "VP_CRON_SCHEDULE"},
            )
        )
    return issues


def _check_transform_supported(buckets: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    for node in buckets["VP_TRANSFORM"]:
        values = _node_values(node)
        raw = values.get("transform_type")
        if raw is None or (isinstance(raw, str) and raw.strip() == ""):
            issues.append(
                make_compile_issue(
                    code="COMPILE_NODE_CONFIG_MISSING",
                    message="transform_type is required for compile.",
                    node_id=str(node.get("id") or ""),
                    component_type="VP_TRANSFORM",
                    field_key="transform_type",
                )
            )
            continue
        ttype = str(raw)
        if ttype not in TRANSFORM_TYPES:
            issues.append(
                make_compile_issue(
                    code="COMPILE_TRANSFORM_UNSUPPORTED",
                    message=f"Unsupported transform_type: {ttype}",
                    node_id=str(node.get("id") or ""),
                    component_type="VP_TRANSFORM",
                    field_key="transform_type",
                    hint=f"허용: {', '.join(sorted(TRANSFORM_TYPES))}",
                )
            )
    return issues


def _check_secret_inline(buckets: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    for ctype, nodes in buckets.items():
        if ctype == "OTHER":
            continue
        for node in nodes:
            values = _node_values(node)
            keys = _contains_secret_like(values)
            for key in keys:
                issues.append(
                    make_compile_issue(
                        code="COMPILE_SECRET_INLINE_FORBIDDEN",
                        message=f"Secret-like key '{key}' must not appear in compile input values.",
                        node_id=str(node.get("id") or ""),
                        component_type=ctype,
                        field_key=key,
                        hint="credential_ref 등 참조만 사용하세요.",
                    )
                )
    return issues


def _check_required_values(buckets: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    for node in buckets["VP_REST_API_SOURCE"]:
        values = _node_values(node)
        for key in ("data_source_id", "operation_name", "endpoint_path", "http_method"):
            val = values.get(key)
            if val is None or (isinstance(val, str) and not str(val).strip()):
                issues.append(
                    make_compile_issue(
                        code="COMPILE_NODE_CONFIG_MISSING",
                        message=f"{key} is required for compile.",
                        node_id=str(node.get("id") or ""),
                        component_type="VP_REST_API_SOURCE",
                        field_key=key,
                    )
                )
    for node in buckets["VP_UPSERT_LOAD"]:
        values = _node_values(node)
        for key in ("target_table", "write_mode"):
            val = values.get(key)
            if val is None or (isinstance(val, str) and not str(val).strip()):
                issues.append(
                    make_compile_issue(
                        code="COMPILE_NODE_CONFIG_MISSING",
                        message=f"{key} is required for compile.",
                        node_id=str(node.get("id") or ""),
                        component_type="VP_UPSERT_LOAD",
                        field_key=key,
                    )
                )
    return issues


def map_rest_source_node(node: dict[str, Any]) -> dict[str, Any]:
    nid = str(node.get("id") or "")
    values = _node_values(node)
    return {
        "step_id": _step_id("source", nid),
        "type": "source",
        "component_type": "VP_REST_API_SOURCE",
        "node_id": nid,
        "adapter": "api_connector_operation",
        "config": _pick_config(values, REST_CONFIG_KEYS),
        "outputs": [{"port": "raw_rows", "data_type": "RAW_ROWS"}],
    }


def map_transform_node(node: dict[str, Any], *, from_step: str) -> dict[str, Any]:
    nid = str(node.get("id") or "")
    values = _node_values(node)
    return {
        "step_id": _step_id("transform", nid),
        "type": "transform",
        "component_type": "VP_TRANSFORM",
        "node_id": nid,
        "adapter": "connector_transform_config",
        "config": _pick_config(values, TRANSFORM_CONFIG_KEYS),
        "inputs": [{"port": "input_rows", "data_type": "RAW_ROWS", "from_step": from_step}],
        "outputs": [{"port": "transformed_rows", "data_type": "TRANSFORMED_ROWS"}],
    }


def map_upsert_load_node(
    node: dict[str, Any],
    *,
    from_step: str,
    input_data_type: str,
) -> dict[str, Any]:
    nid = str(node.get("id") or "")
    values = _node_values(node)
    return {
        "step_id": _step_id("load", nid),
        "type": "load",
        "component_type": "VP_UPSERT_LOAD",
        "node_id": nid,
        "adapter": "api_connector_load_write_policy",
        "config": _pick_config(values, UPSERT_CONFIG_KEYS),
        "inputs": [{"port": "input_rows", "data_type": input_data_type, "from_step": from_step}],
        "outputs": [{"port": "load_result", "data_type": "LOAD_RESULT"}],
    }


def map_cron_schedule_node(node: dict[str, Any], *, binds_to_node_id: str | None) -> dict[str, Any]:
    nid = str(node.get("id") or "")
    values = _node_values(node)
    cfg = _pick_config(values, CRON_CONFIG_KEYS)
    active_yn = bool(cfg.get("active_yn")) if "active_yn" in cfg else False
    return {
        "enabled": True,
        "component_type": "VP_CRON_SCHEDULE",
        "node_id": nid,
        "adapter": "data_load_scheduler",
        "schedule_type": cfg.get("schedule_type") or "CRON",
        "cron_expression": cfg.get("cron_expression"),
        "timezone": cfg.get("timezone"),
        "start_at": cfg.get("start_at"),
        "end_at": cfg.get("end_at"),
        "active_yn": active_yn,
        "retry_enabled_yn": cfg.get("retry_enabled_yn"),
        "max_retry_count": cfg.get("max_retry_count"),
        "retry_interval_minutes": cfg.get("retry_interval_minutes"),
        "binds_to_node_id": binds_to_node_id,
        "activation": "NOT_REQUESTED",
    }


def build_compile_artifact(graph: dict[str, Any], buckets: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    rest = buckets["VP_REST_API_SOURCE"][0]
    load = buckets["VP_UPSERT_LOAD"][0]
    xform = buckets["VP_TRANSFORM"][0] if buckets["VP_TRANSFORM"] else None
    cron = buckets["VP_CRON_SCHEDULE"][0] if buckets["VP_CRON_SCHEDULE"] else None

    rest_id = str(rest.get("id") or "")
    load_id = str(load.get("id") or "")
    xform_id = str(xform.get("id") or "") if xform else None
    cron_id = str(cron.get("id") or "") if cron else None

    source_step = map_rest_source_node(rest)
    steps: list[dict[str, Any]] = [source_step]
    lineage: list[dict[str, Any]] = []

    if xform:
        transform_step = map_transform_node(xform, from_step=source_step["step_id"])
        load_step = map_upsert_load_node(
            load,
            from_step=transform_step["step_id"],
            input_data_type="TRANSFORMED_ROWS",
        )
        steps.extend([transform_step, load_step])
        lineage = [
            {"from_step": source_step["step_id"], "to_step": transform_step["step_id"], "port": "raw_rows"},
            {
                "from_step": transform_step["step_id"],
                "to_step": load_step["step_id"],
                "port": "transformed_rows",
            },
        ]
        pattern = "REST_TRANSFORM_UPSERT"
    else:
        load_step = map_upsert_load_node(
            load,
            from_step=source_step["step_id"],
            input_data_type="RAW_ROWS",
        )
        steps.append(load_step)
        lineage = [
            {"from_step": source_step["step_id"], "to_step": load_step["step_id"], "port": "raw_rows"},
        ]
        pattern = "REST_UPSERT_DIRECT"

    schedule = map_cron_schedule_node(cron, binds_to_node_id=rest_id) if cron else None

    try:
        normalized = normalize_graph(graph)
    except Exception:
        normalized = graph if isinstance(graph, dict) else {"nodes": [], "edges": []}

    return {
        "version": COMPILE_VERSION,
        "kind": "VISUAL_DATA_LOAD",
        "steps": steps,
        "schedule": schedule,
        "write_policy": dict(load_step.get("config") or {}),
        "lineage": lineage,
        "metadata": {
            "source_node_id": rest_id,
            "transform_node_id": xform_id,
            "load_node_id": load_id,
            "schedule_node_id": cron_id,
            "has_transform": xform is not None,
            "has_schedule": cron is not None,
            "pattern": pattern,
            "generated_by": COMPILE_VERSION,
            "graph_node_count": len(list(normalized.get("nodes") or [])),
            "graph_edge_count": len(list(normalized.get("edges") or [])),
        },
    }


def compile_visual_pipeline_preview(
    pipeline_id: str,
    graph: dict[str, Any] | None,
    *,
    validation_level: str = "STRICT",
) -> dict[str, Any]:
    """Build compile-preview response. Never persists or mutates DB state."""
    level = str(validation_level or "STRICT").strip().upper() or "STRICT"
    compiled_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    graph_version_hash = calculate_graph_version_hash(graph if isinstance(graph, dict) else {})
    config_hash = calculate_config_hash(graph if isinstance(graph, dict) else {})

    validation = validate_visual_pipeline_graph(
        graph,
        validation_level=level,
        pipeline_id=pipeline_id,
    )
    validation_issues = list(validation.get("issues") or [])
    has_validation_error = any(i.get("severity") == "ERROR" for i in validation_issues)

    buckets = extract_compile_nodes(graph if isinstance(graph, dict) else {})
    compile_issues: list[dict[str, Any]] = []
    compile_issues.extend(_check_mvp_shape(buckets))
    compile_issues.extend(_check_transform_supported(buckets))
    compile_issues.extend(_check_secret_inline(buckets))
    if not has_validation_error:
        # Defensive required-field check after STRICT pass
        compile_issues.extend(_check_required_values(buckets))

    issues: list[dict[str, Any]] = []
    issues.extend(validation_issues)

    has_compile_error = any(i.get("severity") == "ERROR" for i in compile_issues)
    if has_validation_error:
        issues.append(
            make_compile_issue(
                code="COMPILE_VALIDATION_FAILED",
                message="STRICT graph validation failed; compile preview aborted.",
                hint="Validation Panel의 ERROR를 먼저 해결하세요.",
            )
        )
    issues.extend(compile_issues)

    if has_validation_error or has_compile_error:
        return {
            "pipeline_id": pipeline_id,
            "compile_status": "FAILED",
            "validation_level": level,
            "graph_version_hash": graph_version_hash,
            "config_hash": config_hash,
            "compiled_at": compiled_at,
            "compile_version": COMPILE_VERSION,
            "compiled_artifact": None,
            "issues": issues,
            "persisted": False,
        }

    artifact = build_compile_artifact(graph if isinstance(graph, dict) else {}, buckets)
    # Final safety: ensure secret-like keys never appear under step/schedule configs
    _assert_no_secret_keys_in_artifact(artifact)

    return {
        "pipeline_id": pipeline_id,
        "compile_status": "SUCCESS",
        "validation_level": level,
        "graph_version_hash": graph_version_hash,
        "config_hash": config_hash,
        "compiled_at": compiled_at,
        "compile_version": COMPILE_VERSION,
        "compiled_artifact": artifact,
        "issues": issues,
        "persisted": False,
    }


def _assert_no_secret_keys_in_artifact(artifact: dict[str, Any]) -> None:
    """Drop any unexpected secret-like keys if present (defensive; allowlist mappers preferred)."""

    def scrub(obj: Any) -> Any:
        if isinstance(obj, dict):
            cleaned: dict[str, Any] = {}
            for k, v in obj.items():
                key = str(k)
                if key.lower() in SECRET_ALLOW_KEYS or key.endswith("_ref"):
                    cleaned[key] = scrub(v)
                    continue
                if SECRET_KEY_RE.search(key):
                    continue
                cleaned[key] = scrub(v)
            return cleaned
        if isinstance(obj, list):
            return [scrub(v) for v in obj]
        return obj

    scrubbed = scrub(artifact)
    if isinstance(scrubbed, dict):
        artifact.clear()
        artifact.update(scrubbed)
