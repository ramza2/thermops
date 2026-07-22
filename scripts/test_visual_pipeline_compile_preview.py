#!/usr/bin/env python3
"""R11-S6-1 Visual Pipeline Compile Preview API tests (no persistence)."""

from __future__ import annotations

import copy
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

from test_visual_pipeline_graph_validation import (  # noqa: E402
    build_valid_visual_pipeline_graph_with_config,
    mutate_node_config,
)


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
    return {i["code"] for i in result.get("issues") or []}


def _deep_copy(obj: dict) -> dict:
    return copy.deepcopy(obj)


def build_direct_rest_upsert_graph() -> dict:
    """REST → Upsert without Transform/CRON."""
    return {
        "nodes": [
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
                "id": "e-direct",
                "source": "n-rest",
                "target": "n-load",
                "sourceHandle": "output:raw_rows",
                "targetHandle": "input:input_rows",
                "data": {
                    "source_port": "raw_rows",
                    "target_port": "input_rows",
                    "data_type": "RAW_ROWS",
                },
            }
        ],
        "viewport": {"x": 0, "y": 0, "zoom": 1},
    }


def create_pipeline(name: str, graph: dict) -> dict:
    return api(
        "POST",
        "/visual-pipelines",
        {"pipeline_name": name, "description": "R11-S6-1 compile-preview test", "graph": graph},
    )


def archive_pipeline(pipeline_id: str) -> None:
    api("POST", f"/visual-pipelines/{pipeline_id}/archive")


def compile_preview(pipeline_id: str, body: dict | None = None) -> dict:
    return api("POST", f"/visual-pipelines/{pipeline_id}/compile-preview", body if body is not None else {})


def snapshot_pipeline(pipeline_id: str) -> dict:
    detail = api("GET", f"/visual-pipelines/{pipeline_id}")
    versions = api("GET", f"/visual-pipelines/{pipeline_id}/versions")
    return {
        "current_sync_status": detail.get("current_sync_status"),
        "graph": detail.get("graph"),
        "version_count": int(versions.get("total") or len(versions.get("items") or [])),
        "updated_at": detail.get("updated_at"),
    }


def test_valid_four_node_success() -> None:
    graph = build_valid_visual_pipeline_graph_with_config()
    created = create_pipeline("R11-S6-1 Compile 4-node", graph)
    pid = created["pipeline_id"]
    before = snapshot_pipeline(pid)
    try:
        result = compile_preview(pid, {"validation_level": "STRICT"})
        assert result["compile_status"] == "SUCCESS", result
        assert result["persisted"] is False
        assert result["validation_level"] == "STRICT"
        assert result["compile_version"] == "R11-S6-1"
        assert str(result.get("graph_version_hash") or "").startswith("sha256:")
        assert str(result.get("config_hash") or "").startswith("sha256:")
        art = result["compiled_artifact"]
        assert art is not None
        types = [s["type"] for s in art["steps"]]
        assert types == ["source", "transform", "load"], types
        assert art["schedule"] is not None
        assert art["schedule"]["activation"] == "NOT_REQUESTED"
        assert art["write_policy"].get("target_table") == "tb_x"
        assert art["metadata"]["pattern"] == "REST_TRANSFORM_UPSERT"
        assert art["metadata"]["has_schedule"] is True
        after = snapshot_pipeline(pid)
        assert after["current_sync_status"] == before["current_sync_status"]
        assert after["version_count"] == before["version_count"]
        assert after["graph"] == before["graph"]
        print("  [ok] valid 4-node SUCCESS + no status/version/graph change")
    finally:
        archive_pipeline(pid)


def test_rest_upsert_direct() -> None:
    graph = build_direct_rest_upsert_graph()
    created = create_pipeline("R11-S6-1 Compile direct", graph)
    pid = created["pipeline_id"]
    try:
        result = compile_preview(pid)
        assert result["compile_status"] == "SUCCESS", result
        art = result["compiled_artifact"]
        assert art["metadata"]["pattern"] == "REST_UPSERT_DIRECT"
        assert art["metadata"]["has_transform"] is False
        assert art["schedule"] is None
        types = [s["type"] for s in art["steps"]]
        assert types == ["source", "load"], types
        assert art["steps"][1]["inputs"][0]["data_type"] == "RAW_ROWS"
        print("  [ok] REST→Upsert direct SUCCESS")
    finally:
        archive_pipeline(pid)


def test_strict_validation_fail() -> None:
    graph = mutate_node_config(
        build_valid_visual_pipeline_graph_with_config(),
        "n-rest",
        {"operation_name": None},
    )
    created = create_pipeline("R11-S6-1 Compile validation fail", graph)
    pid = created["pipeline_id"]
    try:
        result = compile_preview(pid)
        assert result["compile_status"] == "FAILED"
        assert "COMPILE_VALIDATION_FAILED" in codes(result)
        assert result["compiled_artifact"] is None
        assert str(result.get("graph_version_hash") or "").startswith("sha256:")
        print("  [ok] STRICT validation fail → FAILED + COMPILE_VALIDATION_FAILED")
    finally:
        archive_pipeline(pid)


def test_unsupported_shape() -> None:
    graph = build_direct_rest_upsert_graph()
    # Duplicate REST source
    extra = _deep_copy(graph["nodes"][0])
    extra["id"] = "n-rest-2"
    extra["position"] = {"x": 220, "y": 40}
    graph["nodes"].append(extra)
    graph["edges"].append(
        {
            "id": "e-extra",
            "source": "n-rest-2",
            "target": "n-load",
            "sourceHandle": "output:raw_rows",
            "targetHandle": "input:input_rows",
            "data": {
                "source_port": "raw_rows",
                "target_port": "input_rows",
                "data_type": "RAW_ROWS",
            },
        }
    )
    created = create_pipeline("R11-S6-1 Compile shape fail", graph)
    pid = created["pipeline_id"]
    try:
        result = compile_preview(pid)
        assert result["compile_status"] == "FAILED", result
        assert "COMPILE_GRAPH_UNSUPPORTED_SHAPE" in codes(result)
        assert result["compiled_artifact"] is None
        print("  [ok] unsupported shape → COMPILE_GRAPH_UNSUPPORTED_SHAPE")
    finally:
        archive_pipeline(pid)


def test_unsupported_transform() -> None:
    graph = mutate_node_config(
        build_valid_visual_pipeline_graph_with_config(),
        "n-xform",
        {"transform_type": "NOT_A_REAL_TRANSFORM"},
    )
    created = create_pipeline("R11-S6-1 Compile transform fail", graph)
    pid = created["pipeline_id"]
    try:
        result = compile_preview(pid)
        assert result["compile_status"] == "FAILED", result
        assert "COMPILE_TRANSFORM_UNSUPPORTED" in codes(result)
        assert result["compiled_artifact"] is None
        print("  [ok] unsupported transform → COMPILE_TRANSFORM_UNSUPPORTED")
    finally:
        archive_pipeline(pid)


def test_hash_idempotency() -> None:
    from app.services.visual_pipeline.compile_preview_service import (
        calculate_config_hash,
        calculate_graph_version_hash,
    )

    base = build_valid_visual_pipeline_graph_with_config()
    h1 = calculate_graph_version_hash(base)
    h1b = calculate_graph_version_hash(_deep_copy(base))
    assert h1 == h1b

    with_validation = _deep_copy(base)
    for node in with_validation["nodes"]:
        cfg = node["data"]["config"]
        cfg["validation"] = {"status": "INVALID", "last_validated_at": "2026-01-01T00:00:00Z", "issue_count": 9}
    assert calculate_graph_version_hash(with_validation) == h1

    cosmetic = _deep_copy(base)
    cosmetic["viewport"] = {"x": 99, "y": -3, "zoom": 2.5}
    for node in cosmetic["nodes"]:
        node["position"] = {"x": node["position"]["x"] + 10, "y": node["position"]["y"] + 5}
        node["data"]["label"] = f"{node['data']['label']}-renamed"
    assert calculate_graph_version_hash(cosmetic) == h1

    changed = mutate_node_config(base, "n-rest", {"operation_name": "op-changed"})
    assert calculate_graph_version_hash(changed) != h1
    assert calculate_config_hash(changed) != calculate_config_hash(base)
    print("  [ok] hash idempotency (validation/viewport/label ignored; values matter)")


def test_secret_handling() -> None:
    secret_value = "super-secret-token-value-XYZ"
    graph = mutate_node_config(
        build_valid_visual_pipeline_graph_with_config(),
        "n-rest",
        {"api_token": secret_value},
    )
    created = create_pipeline("R11-S6-1 Compile secret", graph)
    pid = created["pipeline_id"]
    try:
        result = compile_preview(pid)
        assert result["compile_status"] == "FAILED", result
        blob = json.dumps(result, ensure_ascii=False)
        assert secret_value not in blob, "secret value leaked into compile-preview response"
        assert (
            "COMPILE_SECRET_INLINE_FORBIDDEN" in codes(result)
            or "NODE_CONFIG_SECRET_INLINE_NOT_ALLOWED" in codes(result)
            or "COMPILE_VALIDATION_FAILED" in codes(result)
        )
        print("  [ok] secret value not present in compile-preview output")
    finally:
        archive_pipeline(pid)


def test_no_db_write_status_version() -> None:
    graph = build_valid_visual_pipeline_graph_with_config()
    created = create_pipeline("R11-S6-1 Compile no-write", graph)
    pid = created["pipeline_id"]
    before = snapshot_pipeline(pid)
    try:
        for _ in range(2):
            result = compile_preview(pid)
            assert result["compile_status"] == "SUCCESS"
            assert result["persisted"] is False
        after = snapshot_pipeline(pid)
        assert after["current_sync_status"] == before["current_sync_status"] == "NOT_COMPILED"
        assert after["version_count"] == before["version_count"]
        assert after["graph"] == before["graph"]
        print("  [ok] repeated preview leaves sync_status/version/graph unchanged")
    finally:
        archive_pipeline(pid)


def test_basic_level_rejected() -> None:
    graph = build_valid_visual_pipeline_graph_with_config()
    created = create_pipeline("R11-S6-1 Compile basic reject", graph)
    pid = created["pipeline_id"]
    try:
        err = api(
            "POST",
            f"/visual-pipelines/{pid}/compile-preview",
            {"validation_level": "BASIC"},
            expect_fail=True,
        )
        assert err.get("_http_status") == 400
        print("  [ok] BASIC validation_level → 400")
    finally:
        archive_pipeline(pid)


def test_missing_pipeline_404() -> None:
    err = api(
        "POST",
        "/visual-pipelines/PIPE-DOES-NOT-EXIST/compile-preview",
        {},
        expect_fail=True,
    )
    assert err.get("_http_status") == 404
    print("  [ok] missing pipeline → 404")


def main() -> None:
    print("R11-S6-1 Visual Pipeline Compile Preview tests")
    test_hash_idempotency()
    test_valid_four_node_success()
    test_rest_upsert_direct()
    test_strict_validation_fail()
    test_unsupported_shape()
    test_unsupported_transform()
    test_secret_handling()
    test_no_db_write_status_version()
    test_basic_level_rejected()
    test_missing_pipeline_404()
    print("All compile-preview tests passed.")


if __name__ == "__main__":
    main()
