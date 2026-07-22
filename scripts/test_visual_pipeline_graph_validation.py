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

    # --- R11-S5-5 config validation ---
    cfg_missing = validate_visual_pipeline_graph(
        {
            "nodes": [{"id": "r", "type": "VP_REST_API_SOURCE", "position": {"x": 0, "y": 0}, "data": {}}],
            "edges": [],
        },
        validation_level="BASIC",
    )
    assert cfg_missing["valid"] is True
    assert "NODE_CONFIG_MISSING" in codes(cfg_missing)
    assert "NODE_CONFIG_REST_OPERATION_MISSING" in codes(cfg_missing)
    assert any(i.get("phase") == "CONFIG" and i.get("field_key") == "operation_name" for i in cfg_missing["issues"])
    print("  [ok] BASIC config missing → WARNING, valid=true")

    rest_secret = validate_visual_pipeline_graph(
        {
            "nodes": [
                {
                    "id": "r",
                    "type": "VP_REST_API_SOURCE",
                    "position": {"x": 0, "y": 0},
                    "data": {
                        "config": {
                            "schema_version": "R11-S5-0",
                            "values": {
                                "data_source_id": "DS-1",
                                "operation_name": "op",
                                "endpoint_path": "/x",
                                "http_method": "GET",
                                "api_key": "sk-secret-inline",
                            },
                        }
                    },
                }
            ],
            "edges": [],
        },
        validation_level="BASIC",
    )
    assert rest_secret["valid"] is True
    assert "NODE_CONFIG_SECRET_INLINE_NOT_ALLOWED" in codes(rest_secret)
    assert any(i.get("field_key") == "api_key" for i in rest_secret["issues"])
    # secret not stripped from normalized graph values
    nv = rest_secret["normalized_graph"]["nodes"][0]["data"]["config"]["values"]
    assert nv.get("api_key") == "sk-secret-inline"
    print("  [ok] secret inline issue only (value retained)")

    upsert_keys = validate_visual_pipeline_graph(
        {
            "nodes": [
                {
                    "id": "u",
                    "type": "VP_UPSERT_LOAD",
                    "position": {"x": 0, "y": 0},
                    "data": {
                        "config": {
                            "schema_version": "R11-S5-0",
                            "values": {
                                "standard_dataset_id": "SD-1",
                                "target_table": "tb_x",
                                "write_mode": "UPSERT",
                            },
                        }
                    },
                }
            ],
            "edges": [],
        },
        validation_level="STRICT",
    )
    assert upsert_keys["valid"] is False
    assert "NODE_CONFIG_KEY_COLUMNS_MISSING" in codes(upsert_keys)
    assert any(i.get("severity") == "ERROR" and i.get("code") == "NODE_CONFIG_KEY_COLUMNS_MISSING" for i in upsert_keys["issues"])
    print("  [ok] STRICT upsert key columns ERROR")

    cron_bad = validate_visual_pipeline_graph(
        {
            "nodes": [
                {
                    "id": "c",
                    "type": "VP_CRON_SCHEDULE",
                    "position": {"x": 0, "y": 0},
                    "data": {
                        "config": {
                            "schema_version": "R11-S5-0",
                            "values": {
                                "schedule_type": "CRON",
                                "cron_expression": "not a cron",
                                "timezone": "Mars/Phobos",
                            },
                        }
                    },
                }
            ],
            "edges": [],
        },
        validation_level="BASIC",
    )
    assert cron_bad["valid"] is True
    assert "NODE_CONFIG_CRON_INVALID" in codes(cron_bad)
    assert "NODE_CONFIG_TIMEZONE_INVALID" in codes(cron_bad)
    print("  [ok] BASIC cron/timezone WARNING")

    good_cfg = validate_visual_pipeline_graph(
        {
            "nodes": [
                {
                    "id": "r",
                    "type": "VP_REST_API_SOURCE",
                    "position": {"x": 0, "y": 0},
                    "data": {
                        "config": {
                            "schema_version": "R11-S5-0",
                            "values": {
                                "data_source_id": "DS-1",
                                "operation_name": "op",
                                "endpoint_path": "/x",
                                "http_method": "GET",
                                "credential_ref": "CRED-1",
                            },
                        }
                    },
                }
            ],
            "edges": [],
        },
        validation_level="BASIC",
    )
    assert "NODE_CONFIG_REST_OPERATION_MISSING" not in codes(good_cfg)
    assert "NODE_CONFIG_REQUIRED_FIELD_MISSING" not in codes(good_cfg)
    assert not any(
        i.get("code") == "NODE_CONFIG_REQUIRED_FIELD_MISSING" and i.get("field_key") == "credential_ref"
        for i in good_cfg["issues"]
    )
    print("  [ok] REST good config; credential_ref not forced required")


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
