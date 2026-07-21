#!/usr/bin/env python3
"""R11-S2 Visual Pipeline graph storage / CRUD tests."""

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


def _psql_scalar(sql: str) -> str:
    from test_fixtures import psql_scalar

    return str(psql_scalar(sql) or "").strip()


def test_schema_and_template() -> None:
    assert _psql_scalar(
        "SELECT COUNT(*) FROM information_schema.columns "
        "WHERE table_name='tb_pipeline_definition' AND column_name='pipeline_kind'"
    ) == "1"
    assert _psql_scalar(
        "SELECT COUNT(*) FROM information_schema.columns "
        "WHERE table_name='tb_pipeline_definition' AND column_name='current_graph_json'"
    ) == "1"
    assert _psql_scalar(
        "SELECT COUNT(*) FROM information_schema.columns "
        "WHERE table_name='tb_pipeline_definition' AND column_name='current_sync_status'"
    ) == "1"
    assert _psql_scalar(
        "SELECT COUNT(*) FROM tb_pipeline_template WHERE template_id='PT-VISUAL-DATA-LOAD'"
    ) == "1"
    assert _psql_scalar(
        "SELECT pipeline_type FROM tb_pipeline_template WHERE template_id='PT-VISUAL-DATA-LOAD'"
    ) == "DATA_LOAD"
    print("  [ok] schema columns + PT-VISUAL-DATA-LOAD")


def test_catalog_still_works() -> None:
    data = api("GET", "/visual-pipelines/components")
    assert data.get("total") == 12
    print("  [ok] catalog API still works")


def test_crud_and_versions() -> str:
    listed = api("GET", "/visual-pipelines")
    assert "items" in listed and "total" in listed
    print("  [ok] list visual pipelines")

    sample_graph = {
        "nodes": [
            {
                "id": "node-source-1",
                "type": "VP_REST_API_SOURCE",
                "position": {"x": 100, "y": 120},
                "data": {"label": "REST API Source", "config": {"http_method": "GET"}},
            },
            {
                "id": "node-load-1",
                "type": "VP_UPSERT_LOAD",
                "position": {"x": 360, "y": 120},
                "data": {"label": "Upsert Load", "config": {}},
            },
        ],
        "edges": [
            {
                "id": "e1",
                "source": "node-source-1",
                "target": "node-load-1",
                "sourceHandle": "raw_rows",
                "targetHandle": "input_rows",
            }
        ],
        "viewport": {"x": 0, "y": 0, "zoom": 1},
    }
    created = api(
        "POST",
        "/visual-pipelines",
        {
            "pipeline_name": "R11-S2 Graph Storage Test",
            "description": "visual pipeline graph storage",
            "graph": sample_graph,
        },
    )
    pid = created["pipeline_id"]
    assert created["pipeline_kind"] == "VISUAL_DATA_LOAD"
    assert created["template_id"] == "PT-VISUAL-DATA-LOAD"
    assert created["pipeline_type"] == "DATA_LOAD"
    assert created["current_sync_status"] == "NOT_COMPILED"
    assert created["status"] == "DRAFT"
    assert created["node_count"] == 2
    assert created["edge_count"] == 1
    assert created["graph"]["nodes"][0]["type"] == "VP_REST_API_SOURCE"
    print(f"  [ok] create {pid}")

    detail = api("GET", f"/visual-pipelines/{pid}")
    assert detail["pipeline_id"] == pid
    assert len(detail["graph"]["nodes"]) == 2
    print("  [ok] get detail with graph")

    versions_after_create = api("GET", f"/visual-pipelines/{pid}/versions")
    count_after_create = versions_after_create["total"]
    assert count_after_create >= 1
    print(f"  [ok] initial version count={count_after_create}")

    updated_graph = dict(sample_graph)
    updated_graph["nodes"] = list(sample_graph["nodes"]) + [
        {
            "id": "node-cron-1",
            "type": "VP_CRON_SCHEDULE",
            "position": {"x": 100, "y": 300},
            "data": {"label": "CRON", "config": {"cron_expression": "0 1 * * *"}},
        }
    ]
    updated = api(
        "PUT",
        f"/visual-pipelines/{pid}",
        {"graph": updated_graph, "description": "updated graph"},
    )
    assert updated["node_count"] == 3
    assert updated["current_sync_status"] == "NOT_COMPILED"
    versions_after_put = api("GET", f"/visual-pipelines/{pid}/versions")
    assert versions_after_put["total"] == count_after_create
    reloaded = api("GET", f"/visual-pipelines/{pid}")
    assert len(reloaded["graph"]["nodes"]) == 3
    print("  [ok] put graph update (create_version default false, version unchanged)")

    # R11-S4-2: sourceHandle/targetHandle/data round-trip
    handle_graph = {
        "nodes": [
            {
                "id": "n-rest",
                "type": "VP_REST_API_SOURCE",
                "position": {"x": 0, "y": 0},
                "data": {"label": "REST"},
            },
            {
                "id": "n-xform",
                "type": "VP_TRANSFORM",
                "position": {"x": 200, "y": 0},
                "data": {"label": "XFORM"},
            },
        ],
        "edges": [
            {
                "id": "e-handle",
                "source": "n-rest",
                "target": "n-xform",
                "sourceHandle": "output:raw_rows",
                "targetHandle": "input:input_rows",
                "label": "raw_rows → input_rows",
                "data": {
                    "source_port": "raw_rows",
                    "target_port": "input_rows",
                    "data_type": "RAW_ROWS",
                },
            }
        ],
        "viewport": {"x": 0, "y": 0, "zoom": 1},
    }
    api("PUT", f"/visual-pipelines/{pid}", {"graph": handle_graph, "create_version": False})
    got = api("GET", f"/visual-pipelines/{pid}")["graph"]["edges"][0]
    assert got.get("sourceHandle") == "output:raw_rows"
    assert got.get("targetHandle") == "input:input_rows"
    assert got.get("data", {}).get("source_port") == "raw_rows"
    assert got.get("data", {}).get("target_port") == "input_rows"
    snap = api("POST", f"/visual-pipelines/{pid}/versions", {"change_summary": "handle snapshot"})
    snap_edge = snap["snapshot"]["graph"]["edges"][0]
    assert snap_edge.get("sourceHandle") == "output:raw_rows"
    assert snap_edge.get("targetHandle") == "input:input_rows"
    print("  [ok] put/get/version preserve sourceHandle/targetHandle/data")

    # dirty-style: PUT create_version=false then POST /versions -> exactly +1
    # (continue with handle_graph as current)
    versions_after_put = api("GET", f"/visual-pipelines/{pid}/versions")
    count_before_dirty = versions_after_put["total"]
    dirty_graph = dict(handle_graph)
    dirty_graph["viewport"] = {"x": 5, "y": 10, "zoom": 0.95}
    api(
        "PUT",
        f"/visual-pipelines/{pid}",
        {"graph": dirty_graph, "create_version": False},
    )
    after_silent_put = api("GET", f"/visual-pipelines/{pid}/versions")
    assert after_silent_put["total"] == count_before_dirty
    ver = api("POST", f"/visual-pipelines/{pid}/versions", {"change_summary": "manual snapshot"})
    assert ver["version_id"]
    assert ver["snapshot"]["graph"]["nodes"]
    assert ver["snapshot"]["pipeline_kind"] == "VISUAL_DATA_LOAD"
    assert ver["snapshot"]["component_contract_version"]
    versions_after_post = api("GET", f"/visual-pipelines/{pid}/versions")
    assert versions_after_post["total"] == count_before_dirty + 1
    print(f"  [ok] dirty PUT(false)+POST version +1 -> no={ver['version_no']} total={versions_after_post['total']}")

    # optional create_version=true on PUT -> +1
    count_before_opt = versions_after_post["total"]
    opt_graph = dict(dirty_graph)
    opt_graph["viewport"] = {"x": 1, "y": 2, "zoom": 1.1}
    api(
        "PUT",
        f"/visual-pipelines/{pid}",
        {
            "graph": opt_graph,
            "create_version": True,
            "change_summary": "optional put version",
        },
    )
    versions_after_opt = api("GET", f"/visual-pipelines/{pid}/versions")
    assert versions_after_opt["total"] == count_before_opt + 1
    print("  [ok] put create_version=true -> version +1")

    versions = api("GET", f"/visual-pipelines/{pid}/versions")
    assert versions["total"] >= 2
    assert versions["items"][0]["version_no"] >= versions["items"][-1]["version_no"]
    print("  [ok] list versions")

    one = api("GET", f"/visual-pipelines/{pid}/versions/{ver['version_id']}")
    assert one["version_id"] == ver["version_id"]
    assert "graph" in one["snapshot"]
    print("  [ok] get version detail")

    archived = api("POST", f"/visual-pipelines/{pid}/archive")
    assert archived["status"] == "ARCHIVED"
    listed_after = api("GET", "/visual-pipelines")
    assert all(i["pipeline_id"] != pid for i in listed_after["items"])
    listed_arch = api("GET", "/visual-pipelines?include_archived=true")
    assert any(i["pipeline_id"] == pid for i in listed_arch["items"])
    print("  [ok] archive + list exclusion")
    return pid


def test_isolation_and_errors(visual_pid: str) -> None:
    # Visual must not appear in MLOps pipeline-definitions list
    defs = api("GET", "/pipeline-definitions")
    items = defs.get("items") if isinstance(defs, dict) else defs
    if isinstance(items, list):
        assert all(i.get("pipeline_id") != visual_pid for i in items)
        assert all(i.get("template_id") != "PT-VISUAL-DATA-LOAD" or i.get("pipeline_kind") != "VISUAL_DATA_LOAD" for i in items)
    print("  [ok] pipeline-definitions excludes visual pipeline")

    bad = api("POST", "/visual-pipelines", {"pipeline_name": "x", "graph": "not-object"}, expect_fail=True)
    assert bad.get("_http_status") == 400
    print("  [ok] invalid graph shape -> 400")

    missing = api("GET", "/visual-pipelines/PIPE-DOESNOTEXIST", expect_fail=True)
    assert missing.get("_http_status") == 404
    print("  [ok] missing visual pipeline -> 404")

    # If an MLOps definition exists, visual get must 404 for non-visual kind
    # Create is hard without template fixture; skip if none
    mlops_id = _psql_scalar(
        "SELECT pipeline_id FROM tb_pipeline_definition "
        "WHERE COALESCE(pipeline_kind,'MLOPS_FLOW') <> 'VISUAL_DATA_LOAD' "
        "ORDER BY created_at DESC LIMIT 1"
    )
    if mlops_id:
        resp = api("GET", f"/visual-pipelines/{mlops_id}", expect_fail=True)
        assert resp.get("_http_status") == 404
        print(f"  [ok] non-visual pipeline_id blocked ({mlops_id})")
    else:
        print("  [skip] no MLOps definition for non-visual 404 check")


def main() -> int:
    print("THERMOps R11-S2 Visual Pipeline graph storage test")
    try:
        with urllib.request.urlopen(f"{BASE_URL}/health", timeout=5) as resp:
            assert resp.status == 200
    except Exception as exc:
        print(f"FAIL: backend not reachable: {exc}")
        return 1

    try:
        test_schema_and_template()
        test_catalog_still_works()
        pid = test_crud_and_versions()
        test_isolation_and_errors(pid)
        # repeat key create once more for idempotent behavior
        again = api(
            "POST",
            "/visual-pipelines",
            {"pipeline_name": "R11-S2 Repeat", "graph": {"nodes": [], "edges": []}},
        )
        assert again["pipeline_kind"] == "VISUAL_DATA_LOAD"
        api("POST", f"/visual-pipelines/{again['pipeline_id']}/archive")
        print("  [ok] repeat create")
        print("PASS")
        return 0
    except AssertionError as exc:
        print(f"FAIL: {exc}")
        return 1
    except Exception as exc:
        print(f"FAIL: {type(exc).__name__}: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
