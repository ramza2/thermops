#!/usr/bin/env python3
"""R11-S4-1 Visual Pipeline graph validation tests."""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent
_BACKEND = _SCRIPTS.parent / "backend"
for p in (str(_SCRIPTS), str(_BACKEND)):
    if p not in sys.path:
        sys.path.insert(0, p)

API_BASE = os.environ.get("THERMOOPS_API_BASE", "http://localhost:8000/api/v1")
BASE_URL = API_BASE.rsplit("/api/v1", 1)[0]


def api(method: str, path: str, body: dict | None = None, expect_fail: bool = False) -> dict | list:
    url = f"{API_BASE}{path}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={"Content-Type": "application/json"} if data else {},
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            payload = json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode()
        if expect_fail:
            try:
                parsed = json.loads(detail)
            except json.JSONDecodeError:
                parsed = {"detail": detail}
            if isinstance(parsed, dict):
                parsed["_http_status"] = exc.code
            return parsed
        raise RuntimeError(f"HTTP {exc.code} {method} {path}: {detail}") from exc
    if not payload.get("success"):
        raise RuntimeError(f"API failed {method} {path}: {payload}")
    return payload["data"]


def codes(result: dict) -> set[str]:
    return {i["code"] for i in result.get("issues", [])}


def validate_graph(graph: dict, *, level: str = "BASIC") -> dict:
    from app.services.visual_pipeline.graph_validation_service import validate_visual_pipeline_graph

    return validate_visual_pipeline_graph(graph, validation_level=level)


def assert_issue(
    result: dict,
    code: str,
    *,
    node_id: str | None = None,
    field_key: str | None = None,
    severity: str | None = None,
    phase: str | None = None,
) -> dict:
    matches = [i for i in result.get("issues", []) if i.get("code") == code]
    if node_id is not None:
        matches = [i for i in matches if i.get("node_id") == node_id]
    if field_key is not None:
        matches = [i for i in matches if i.get("field_key") == field_key]
    if severity is not None:
        matches = [i for i in matches if i.get("severity") == severity]
    if phase is not None:
        matches = [i for i in matches if i.get("phase") == phase]
    assert matches, f"expected issue {code} (node={node_id} field={field_key} sev={severity} phase={phase}); got {codes(result)}"
    return matches[0]


def _deep_copy(obj: dict) -> dict:
    return json.loads(json.dumps(obj))


def mutate_node_config(graph: dict, node_id: str, patch: dict) -> dict:
    """Patch node.data.config.values (creates structured config if needed)."""
    out = _deep_copy(graph)
    for node in out.get("nodes") or []:
        if node.get("id") != node_id:
            continue
        data = node.setdefault("data", {})
        raw = data.get("config")
        if not isinstance(raw, dict):
            raw = {}
        if "values" in raw and isinstance(raw.get("values"), dict):
            values = dict(raw["values"])
            values.update(patch)
            for k, v in list(values.items()):
                if v is None:
                    del values[k]
            raw = {**raw, "values": values}
            if "schema_version" not in raw:
                raw["schema_version"] = "R11-S5-0"
        else:
            values = {k: v for k, v in raw.items() if k not in {"schema_version", "values", "validation"}}
            values.update(patch)
            for k, v in list(values.items()):
                if v is None:
                    del values[k]
            raw = {
                "schema_version": raw.get("schema_version") or "R11-S5-0",
                "values": values,
                "validation": raw.get("validation")
                or {"status": "NOT_VALIDATED", "last_validated_at": None, "issue_count": 0},
            }
        data["config"] = raw
        return out
    raise AssertionError(f"node not found: {node_id}")


def build_valid_visual_pipeline_graph_with_config() -> dict:
    """Topology-valid MVP graph with good structured configs (R11-S5-6)."""
    return {
        "nodes": [
            {
                "id": "n-cron",
                "type": "VP_CRON_SCHEDULE",
                "position": {"x": 0, "y": 0},
                "data": {
                    "label": "CRON",
                    "config": {
                        "schema_version": "R11-S5-0",
                        "values": {
                            "schedule_type": "CRON",
                            "cron_expression": "0 6 * * *",
                            "timezone": "Asia/Seoul",
                            "active_yn": False,
                        },
                    },
                },
            },
            {
                "id": "n-rest",
                "type": "VP_REST_API_SOURCE",
                "position": {"x": 200, "y": 0},
                "data": {
                    "label": "REST",
                    "config": {
                        "schema_version": "R11-S5-0",
                        "values": {
                            "data_source_id": "DS-1",
                            "operation_name": "op",
                            "endpoint_path": "/x",
                            "http_method": "GET",
                            "credential_ref": "CRED-1",
                        },
                    },
                },
            },
            {
                "id": "n-xform",
                "type": "VP_TRANSFORM",
                "position": {"x": 400, "y": 0},
                "data": {
                    "label": "XFORM",
                    "config": {
                        "schema_version": "R11-S5-0",
                        "values": {"transform_type": "WIDE_HOUR_TO_LONG", "mapping_config": {}},
                    },
                },
            },
            {
                "id": "n-load",
                "type": "VP_UPSERT_LOAD",
                "position": {"x": 600, "y": 0},
                "data": {
                    "label": "LOAD",
                    "config": {
                        "schema_version": "R11-S5-0",
                        "values": {
                            "standard_dataset_id": "SD-1",
                            "target_table": "tb_x",
                            "write_mode": "UPSERT",
                            "conflict_key_columns_json": ["entity_id", "measured_at"],
                        },
                    },
                },
            },
        ],
        "edges": [
            {
                "id": "e1",
                "source": "n-cron",
                "target": "n-rest",
                "sourceHandle": "output:schedule_config",
                "targetHandle": "input:trigger",
                "data": {
                    "source_port": "schedule_config",
                    "target_port": "trigger",
                    "data_type": "SCHEDULE_CONFIG",
                },
            },
            {
                "id": "e2",
                "source": "n-rest",
                "target": "n-xform",
                "sourceHandle": "output:raw_rows",
                "targetHandle": "input:input_rows",
                "data": {"source_port": "raw_rows", "target_port": "input_rows", "data_type": "RAW_ROWS"},
            },
            {
                "id": "e3",
                "source": "n-xform",
                "target": "n-load",
                "sourceHandle": "output:transformed_rows",
                "targetHandle": "input:input_rows",
                "data": {
                    "source_port": "transformed_rows",
                    "target_port": "input_rows",
                    "data_type": "TRANSFORMED_ROWS",
                },
            },
        ],
        "viewport": {"x": 0, "y": 0, "zoom": 1},
    }


def mvp_graph() -> dict:
    return {
        "nodes": [
            {"id": "n-cron", "type": "VP_CRON_SCHEDULE", "position": {"x": 0, "y": 0}, "data": {"label": "CRON"}},
            {"id": "n-rest", "type": "VP_REST_API_SOURCE", "position": {"x": 200, "y": 0}, "data": {"label": "REST"}},
            {"id": "n-xform", "type": "VP_TRANSFORM", "position": {"x": 400, "y": 0}, "data": {"label": "XFORM"}},
            {"id": "n-load", "type": "VP_UPSERT_LOAD", "position": {"x": 600, "y": 0}, "data": {"label": "LOAD"}},
        ],
        "edges": [
            {
                "id": "e1",
                "source": "n-cron",
                "target": "n-rest",
                "sourceHandle": "output:schedule_config",
                "targetHandle": "input:trigger",
                "label": "schedule_config → trigger",
                "data": {"source_port": "schedule_config", "target_port": "trigger", "data_type": "SCHEDULE_CONFIG"},
            },
            {
                "id": "e2",
                "source": "n-rest",
                "target": "n-xform",
                "sourceHandle": "output:raw_rows",
                "targetHandle": "input:input_rows",
                "label": "raw_rows → input_rows",
                "data": {"source_port": "raw_rows", "target_port": "input_rows", "data_type": "RAW_ROWS"},
            },
            {
                "id": "e3",
                "source": "n-xform",
                "target": "n-load",
                "sourceHandle": "output:transformed_rows",
                "targetHandle": "input:input_rows",
                "label": "transformed_rows → input_rows",
                "data": {"source_port": "transformed_rows", "target_port": "input_rows", "data_type": "TRANSFORMED_ROWS"},
            },
        ],
        "viewport": {"x": 0, "y": 0, "zoom": 1},
    }


def test_service_direct() -> None:
    from app.services.visual_pipeline.graph_validation_service import validate_visual_pipeline_graph

    empty_basic = validate_visual_pipeline_graph({"nodes": [], "edges": []}, validation_level="BASIC")
    assert empty_basic["valid"] is True
    assert "GRAPH_EMPTY" in codes(empty_basic)
    assert empty_basic["severity"] == "WARNING"
    print("  [ok] empty BASIC warning")

    empty_strict = validate_visual_pipeline_graph({"nodes": [], "edges": []}, validation_level="STRICT")
    assert empty_strict["valid"] is False
    assert "GRAPH_EMPTY" in codes(empty_strict)
    print("  [ok] empty STRICT error")

    ok = validate_visual_pipeline_graph(mvp_graph(), validation_level="BASIC")
    assert ok["valid"] is True
    assert ok["summary"]["error_count"] == 0
    assert "EDGE_PORT_UNSPECIFIED" not in codes(ok)
    print("  [ok] 4-node MVP valid with handles (no PORT_UNSPECIFIED)")

    rest_upsert = {
        "nodes": [
            {"id": "a", "type": "VP_REST_API_SOURCE", "position": {"x": 0, "y": 0}, "data": {}},
            {"id": "b", "type": "VP_UPSERT_LOAD", "position": {"x": 100, "y": 0}, "data": {}},
        ],
        "edges": [
            {
                "id": "e",
                "source": "a",
                "target": "b",
                "sourceHandle": "output:raw_rows",
                "targetHandle": "input:input_rows",
                "data": {"source_port": "raw_rows", "target_port": "input_rows", "data_type": "RAW_ROWS"},
            }
        ],
    }
    ru = validate_visual_pipeline_graph(rest_upsert, validation_level="BASIC")
    assert ru["valid"] is True
    assert "TRANSFORM_RECOMMENDED" in codes(ru)
    assert "EDGE_PORT_UNSPECIFIED" not in codes(ru)
    print("  [ok] REST→UPSERT handles ALLOW + INFO")

    bad_src = validate_visual_pipeline_graph(
        {
            "nodes": [
                {"id": "a", "type": "VP_REST_API_SOURCE", "position": {"x": 0, "y": 0}, "data": {}},
                {"id": "b", "type": "VP_TRANSFORM", "position": {"x": 10, "y": 0}, "data": {}},
            ],
            "edges": [
                {
                    "id": "e",
                    "source": "a",
                    "target": "b",
                    "sourceHandle": "input:raw_rows",
                    "targetHandle": "input:input_rows",
                }
            ],
        }
    )
    assert "EDGE_SOURCE_PORT_INVALID" in codes(bad_src)
    print("  [ok] sourceHandle direction mismatch")

    bad_tgt = validate_visual_pipeline_graph(
        {
            "nodes": [
                {"id": "a", "type": "VP_REST_API_SOURCE", "position": {"x": 0, "y": 0}, "data": {}},
                {"id": "b", "type": "VP_TRANSFORM", "position": {"x": 10, "y": 0}, "data": {}},
            ],
            "edges": [
                {
                    "id": "e",
                    "source": "a",
                    "target": "b",
                    "sourceHandle": "output:raw_rows",
                    "targetHandle": "output:input_rows",
                }
            ],
        }
    )
    assert "EDGE_TARGET_PORT_INVALID" in codes(bad_tgt)
    print("  [ok] targetHandle direction mismatch")

    malformed = validate_visual_pipeline_graph(
        {
            "nodes": [
                {"id": "a", "type": "VP_REST_API_SOURCE", "position": {"x": 0, "y": 0}, "data": {}},
                {"id": "b", "type": "VP_TRANSFORM", "position": {"x": 10, "y": 0}, "data": {}},
            ],
            "edges": [
                {
                    "id": "e",
                    "source": "a",
                    "target": "b",
                    "sourceHandle": "raw_rows",
                    "targetHandle": ":::bad",
                }
            ],
        }
    )
    assert "EDGE_TARGET_PORT_INVALID" in codes(malformed)
    print("  [ok] malformed targetHandle")

    unknown_port = validate_visual_pipeline_graph(
        {
            "nodes": [
                {"id": "a", "type": "VP_REST_API_SOURCE", "position": {"x": 0, "y": 0}, "data": {}},
                {"id": "b", "type": "VP_TRANSFORM", "position": {"x": 10, "y": 0}, "data": {}},
            ],
            "edges": [
                {
                    "id": "e",
                    "source": "a",
                    "target": "b",
                    "sourceHandle": "output:nope",
                    "targetHandle": "input:input_rows",
                }
            ],
        }
    )
    assert "EDGE_SOURCE_PORT_INVALID" in codes(unknown_port)
    print("  [ok] unknown source port")

    dangling = validate_visual_pipeline_graph(
        {
            "nodes": [{"id": "a", "type": "VP_REST_API_SOURCE", "position": {"x": 0, "y": 0}, "data": {}}],
            "edges": [{"id": "e", "source": "missing", "target": "a"}],
        }
    )
    assert dangling["valid"] is False
    assert "EDGE_DANGLING_SOURCE" in codes(dangling)
    print("  [ok] dangling source")

    unknown = validate_visual_pipeline_graph(
        {"nodes": [{"id": "a", "type": "VP_NOPE", "position": {"x": 0, "y": 0}, "data": {}}], "edges": []}
    )
    assert "NODE_COMPONENT_UNKNOWN" in codes(unknown)
    print("  [ok] unknown component")

    disabled = validate_visual_pipeline_graph(
        {
            "nodes": [{"id": "a", "type": "VP_NOTIFICATION", "position": {"x": 0, "y": 0}, "data": {}}],
            "edges": [],
        }
    )
    assert "NODE_COMPONENT_DISABLED" in codes(disabled)
    print("  [ok] disabled component")

    self_loop = validate_visual_pipeline_graph(
        {
            "nodes": [{"id": "a", "type": "VP_TRANSFORM", "position": {"x": 0, "y": 0}, "data": {}}],
            "edges": [{"id": "e", "source": "a", "target": "a"}],
        }
    )
    assert "EDGE_SELF_LOOP" in codes(self_loop)
    print("  [ok] self-loop")

    cycle = validate_visual_pipeline_graph(
        {
            "nodes": [
                {"id": "a", "type": "VP_TRANSFORM", "position": {"x": 0, "y": 0}, "data": {}},
                {"id": "b", "type": "VP_TRANSFORM", "position": {"x": 10, "y": 0}, "data": {}},
            ],
            "edges": [
                {"id": "e1", "source": "a", "target": "b"},
                {"id": "e2", "source": "b", "target": "a"},
            ],
        }
    )
    assert "GRAPH_CYCLE_DETECTED" in codes(cycle)
    print("  [ok] cycle")

    disc = validate_visual_pipeline_graph(
        {
            "nodes": [
                {"id": "a", "type": "VP_REST_API_SOURCE", "position": {"x": 0, "y": 0}, "data": {}},
                {"id": "b", "type": "VP_UPSERT_LOAD", "position": {"x": 100, "y": 0}, "data": {}},
                {"id": "c", "type": "VP_TRANSFORM", "position": {"x": 200, "y": 0}, "data": {}},
            ],
            "edges": [{"id": "e", "source": "a", "target": "b", "label": "raw_rows"}],
        }
    )
    assert "NODE_DISCONNECTED" in codes(disc)
    print("  [ok] disconnected node")

    no_port = validate_visual_pipeline_graph(
        {
            "nodes": [
                {"id": "a", "type": "VP_REST_API_SOURCE", "position": {"x": 0, "y": 0}, "data": {}},
                {"id": "b", "type": "VP_TRANSFORM", "position": {"x": 100, "y": 0}, "data": {}},
            ],
            "edges": [{"id": "e", "source": "a", "target": "b"}],
        }
    )
    assert "EDGE_PORT_UNSPECIFIED" in codes(no_port)
    print("  [ok] port unspecified warning (legacy label-only / no handle)")

    deny = validate_visual_pipeline_graph(
        {
            "nodes": [
                {"id": "a", "type": "VP_UPSERT_LOAD", "position": {"x": 0, "y": 0}, "data": {}},
                {"id": "b", "type": "VP_CRON_SCHEDULE", "position": {"x": 100, "y": 0}, "data": {}},
            ],
            "edges": [{"id": "e", "source": "a", "target": "b", "label": "load_result"}],
        }
    )
    assert deny["valid"] is False
    assert "EDGE_CONNECTION_DISALLOWED" in codes(deny) or "EDGE_CONNECTION_RULE_NOT_FOUND" in codes(deny)
    print("  [ok] disallowed connection")

    # --- R11-S5-5 / S5-6 config validation ---
    test_config_validation_cases()


def test_config_validation_cases() -> None:
    """CONFIG phase cases (policy unchanged). Separated for maintainability."""
    cfg_missing = validate_graph(
        {"nodes": [{"id": "r", "type": "VP_REST_API_SOURCE", "position": {"x": 0, "y": 0}, "data": {}}], "edges": []},
        level="BASIC",
    )
    assert cfg_missing["valid"] is True
    assert_issue(cfg_missing, "NODE_CONFIG_MISSING", node_id="r", phase="CONFIG")
    assert_issue(
        cfg_missing,
        "NODE_CONFIG_REST_OPERATION_MISSING",
        node_id="r",
        field_key="operation_name",
        phase="CONFIG",
        severity="WARNING",
    )
    print("  [ok] BASIC config missing → WARNING, valid=true")

    missing_op_basic = validate_graph(
        mutate_node_config(build_valid_visual_pipeline_graph_with_config(), "n-rest", {"operation_name": None}),
        level="BASIC",
    )
    assert missing_op_basic["valid"] is True
    assert_issue(
        missing_op_basic,
        "NODE_CONFIG_REST_OPERATION_MISSING",
        node_id="n-rest",
        field_key="operation_name",
        severity="WARNING",
    )
    print("  [ok] BASIC missing operation_name → WARNING, valid=true")

    missing_op_strict = validate_graph(
        mutate_node_config(build_valid_visual_pipeline_graph_with_config(), "n-rest", {"operation_name": None}),
        level="STRICT",
    )
    assert missing_op_strict["valid"] is False
    assert_issue(
        missing_op_strict,
        "NODE_CONFIG_REST_OPERATION_MISSING",
        node_id="n-rest",
        field_key="operation_name",
        severity="ERROR",
    )
    print("  [ok] STRICT missing operation_name → ERROR, valid=false")

    # Legacy compatibility: no crash; INFO/WARNING only for config shape
    for label, node_data in (
        ("no-config", {}),
        ("empty-config", {"config": {}}),
        ("flat-legacy", {"config": {"endpoint_path": "/legacy", "http_method": "GET"}}),
        ("structured-no-sv", {"config": {"values": {"operation_name": "op", "endpoint_path": "/x", "http_method": "GET", "data_source_id": "DS-1"}}}),
    ):
        legacy = validate_graph(
            {
                "nodes": [{"id": "r", "type": "VP_REST_API_SOURCE", "position": {"x": 0, "y": 0}, "data": node_data}],
                "edges": [],
            },
            level="BASIC",
        )
        assert legacy["valid"] is True
        assert legacy["summary"]["error_count"] == 0
        if label == "no-config" or label == "empty-config":
            assert "NODE_CONFIG_MISSING" in codes(legacy)
        if label == "structured-no-sv":
            assert_issue(legacy, "NODE_CONFIG_SCHEMA_VERSION_MISSING", node_id="r", phase="CONFIG")
        print(f"  [ok] legacy {label} BASIC no ERROR")

    rest_secret = validate_graph(
        mutate_node_config(
            build_valid_visual_pipeline_graph_with_config(),
            "n-rest",
            {"api_key": "sk-secret-inline"},
        ),
        level="BASIC",
    )
    assert rest_secret["valid"] is True
    assert_issue(rest_secret, "NODE_CONFIG_SECRET_INLINE_NOT_ALLOWED", field_key="api_key", severity="WARNING")
    nv = next(n for n in rest_secret["normalized_graph"]["nodes"] if n["id"] == "n-rest")
    assert nv["data"]["config"]["values"].get("api_key") == "sk-secret-inline"
    print("  [ok] secret inline issue only (value retained)")

    upsert_keys = validate_graph(
        mutate_node_config(
            build_valid_visual_pipeline_graph_with_config(),
            "n-load",
            {"conflict_key_columns_json": None},
        ),
        level="STRICT",
    )
    assert upsert_keys["valid"] is False
    assert_issue(
        upsert_keys,
        "NODE_CONFIG_KEY_COLUMNS_MISSING",
        node_id="n-load",
        field_key="conflict_key_columns_json",
        severity="ERROR",
    )
    print("  [ok] STRICT upsert key columns ERROR")

    cron_bad = validate_graph(
        mutate_node_config(
            build_valid_visual_pipeline_graph_with_config(),
            "n-cron",
            {"cron_expression": "not a cron", "timezone": "Mars/Phobos"},
        ),
        level="BASIC",
    )
    assert cron_bad["valid"] is True
    assert_issue(cron_bad, "NODE_CONFIG_CRON_INVALID", node_id="n-cron", field_key="cron_expression")
    assert_issue(cron_bad, "NODE_CONFIG_TIMEZONE_INVALID", node_id="n-cron", field_key="timezone")
    print("  [ok] BASIC cron/timezone WARNING")

    good_cfg = validate_graph(build_valid_visual_pipeline_graph_with_config(), level="BASIC")
    assert good_cfg["valid"] is True
    assert "NODE_CONFIG_REST_OPERATION_MISSING" not in codes(good_cfg)
    assert not any(
        i.get("code") == "NODE_CONFIG_REQUIRED_FIELD_MISSING" and i.get("field_key") == "credential_ref"
        for i in good_cfg["issues"]
    )
    print("  [ok] REST/MVP good config; credential_ref not forced required")


def test_http() -> None:
    empty = api("POST", "/visual-pipelines/validate-graph", {"graph": {"nodes": [], "edges": []}, "validation_level": "BASIC"})
    assert empty["valid"] is True
    assert "GRAPH_EMPTY" in codes(empty)
    print("  [ok] HTTP validate-graph empty BASIC")

    strict = api("POST", "/visual-pipelines/validate-graph", {"graph": {"nodes": [], "edges": []}, "validation_level": "STRICT"})
    assert strict["valid"] is False
    print("  [ok] HTTP validate-graph empty STRICT")

    ok = api("POST", "/visual-pipelines/validate-graph", {"graph": mvp_graph(), "validation_level": "BASIC"})
    assert ok["valid"] is True
    assert ok["summary"]["error_count"] == 0
    print("  [ok] HTTP validate-graph MVP")

    created = api(
        "POST",
        "/visual-pipelines",
        {"pipeline_name": "R11-S4-1 validation", "graph": mvp_graph()},
    )
    pid = created["pipeline_id"]
    wrapped = api("POST", f"/visual-pipelines/{pid}/validate", {"validation_level": "BASIC"})
    assert wrapped["valid"] is True
    assert wrapped.get("pipeline_id") == pid
    print(f"  [ok] HTTP pipeline validate {pid}")

    # ensure no version bump from validate
    before = api("GET", f"/visual-pipelines/{pid}/versions")["total"]
    api("POST", "/visual-pipelines/validate-graph", {"graph": mvp_graph(), "pipeline_id": pid})
    after = api("GET", f"/visual-pipelines/{pid}/versions")["total"]
    assert before == after
    print("  [ok] validate does not write versions")

    api("POST", f"/visual-pipelines/{pid}/archive")


def main() -> int:
    print("THERMOps R11-S4-1 Visual Pipeline graph validation test")
    try:
        test_service_direct()
    except Exception as exc:
        print(f"FAIL service: {type(exc).__name__}: {exc}")
        return 1

    try:
        with urllib.request.urlopen(f"{BASE_URL}/health", timeout=5) as resp:
            assert resp.status == 200
    except Exception as exc:
        print(f"  [skip] HTTP (backend not reachable: {exc})")
        print("PASS (service=ok, http=SKIP)")
        return 0

    try:
        test_http()
        print("PASS (service=ok, http=PASS)")
        return 0
    except Exception as exc:
        print(f"FAIL http: {type(exc).__name__}: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
