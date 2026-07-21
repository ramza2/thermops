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
            {"id": "e1", "source": "n-cron", "target": "n-rest", "label": "trigger"},
            {"id": "e2", "source": "n-rest", "target": "n-xform", "label": "raw_rows"},
            {"id": "e3", "source": "n-xform", "target": "n-load", "label": "transformed_rows"},
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
    print("  [ok] 4-node MVP valid")

    rest_upsert = {
        "nodes": [
            {"id": "a", "type": "VP_REST_API_SOURCE", "position": {"x": 0, "y": 0}, "data": {}},
            {"id": "b", "type": "VP_UPSERT_LOAD", "position": {"x": 100, "y": 0}, "data": {}},
        ],
        "edges": [{"id": "e", "source": "a", "target": "b", "label": "raw_rows"}],
    }
    ru = validate_visual_pipeline_graph(rest_upsert, validation_level="BASIC")
    assert ru["valid"] is True
    assert "TRANSFORM_RECOMMENDED" in codes(ru)
    print("  [ok] REST→UPSERT allowed + INFO")

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
    print("  [ok] port unspecified warning")

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
