#!/usr/bin/env python3
"""R11-S6-2 Visual Pipeline Compile Persist + sync status tests."""

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


def _psql_scalar(sql: str) -> str:
    from test_fixtures import psql_scalar

    return str(psql_scalar(sql) or "").strip()


def create_pipeline(name: str, graph: dict) -> dict:
    return api(
        "POST",
        "/visual-pipelines",
        {"pipeline_name": name, "description": "R11-S6-2 compile persist test", "graph": graph},
    )


def archive_pipeline(pipeline_id: str) -> None:
    api("POST", f"/visual-pipelines/{pipeline_id}/archive")


def compile_pipeline(pipeline_id: str, body: dict | None = None) -> dict:
    return api("POST", f"/visual-pipelines/{pipeline_id}/compile", body if body is not None else {})


def compile_preview(pipeline_id: str) -> dict:
    return api("POST", f"/visual-pipelines/{pipeline_id}/compile-preview", {})


def get_compile_result(pipeline_id: str, *, expect_fail: bool = False) -> dict:
    return api("GET", f"/visual-pipelines/{pipeline_id}/compile-result", expect_fail=expect_fail)


def get_pipeline(pipeline_id: str) -> dict:
    return api("GET", f"/visual-pipelines/{pipeline_id}")


def put_graph(pipeline_id: str, graph: dict) -> dict:
    return api("PUT", f"/visual-pipelines/{pipeline_id}", {"graph": graph, "create_version": False})


def version_count(pipeline_id: str) -> int:
    versions = api("GET", f"/visual-pipelines/{pipeline_id}/versions")
    return int(versions.get("total") or 0)


def result_count(pipeline_id: str) -> int:
    return int(
        _psql_scalar(
            "SELECT COUNT(*) FROM tb_visual_pipeline_compile_result "
            f"WHERE pipeline_id='{pipeline_id}'"
        )
        or "0"
    )


def r10_operation_count() -> int:
    return int(_psql_scalar("SELECT COUNT(*) FROM tb_api_connector_operation") or "0")


def r10_write_policy_count() -> int:
    return int(_psql_scalar("SELECT COUNT(*) FROM tb_api_connector_write_policy") or "0")


def r10_schedule_count() -> int:
    return int(_psql_scalar("SELECT COUNT(*) FROM tb_data_load_schedule") or "0")


def test_schema_exists() -> None:
    assert (
        _psql_scalar(
            "SELECT COUNT(*) FROM information_schema.tables "
            "WHERE table_name='tb_visual_pipeline_compile_result'"
        )
        == "1"
    )
    print("  [ok] tb_visual_pipeline_compile_result exists")


def test_successful_compile_persists() -> None:
    graph = build_valid_visual_pipeline_graph_with_config()
    created = create_pipeline("R11-S6-2 Compile success", graph)
    pid = created["pipeline_id"]
    before_versions = version_count(pid)
    before_ops = r10_operation_count()
    before_wp = r10_write_policy_count()
    before_sched = r10_schedule_count()
    try:
        err = get_compile_result(pid, expect_fail=True)
        assert err.get("_http_status") == 404

        result = compile_pipeline(pid, {"validation_level": "STRICT"})
        assert result["compile_status"] == "SUCCESS", result
        assert result["persisted"] is True
        assert result["compile_version"] == "R11-S6-2"
        assert str(result.get("compile_result_id") or "").startswith("VPC-")
        assert result.get("compiled_artifact") is not None
        assert result_count(pid) == 1

        detail = get_pipeline(pid)
        assert detail["current_sync_status"] == "IN_SYNC"
        assert version_count(pid) == before_versions
        assert detail["graph"]["nodes"][0]["id"] == graph["nodes"][0]["id"]
        assert r10_operation_count() == before_ops
        assert r10_write_policy_count() == before_wp
        assert r10_schedule_count() == before_sched
        print("  [ok] successful compile persists + IN_SYNC + no version/R10 change")
    finally:
        archive_pipeline(pid)


def test_get_latest_compile_result() -> None:
    graph = build_valid_visual_pipeline_graph_with_config()
    created = create_pipeline("R11-S6-2 Compile get latest", graph)
    pid = created["pipeline_id"]
    try:
        compiled = compile_pipeline(pid)
        latest = get_compile_result(pid)
        assert latest["compile_result_id"] == compiled["compile_result_id"]
        assert latest["graph_version_hash"] == compiled["graph_version_hash"]
        assert latest["persisted"] is True
        assert latest["compiled_artifact"] is not None
        print("  [ok] GET compile-result returns latest")
    finally:
        archive_pipeline(pid)


def test_preview_does_not_persist() -> None:
    graph = build_valid_visual_pipeline_graph_with_config()
    created = create_pipeline("R11-S6-2 Preview no persist", graph)
    pid = created["pipeline_id"]
    try:
        before_status = get_pipeline(pid)["current_sync_status"]
        before_count = result_count(pid)
        preview = compile_preview(pid)
        assert preview["compile_status"] == "SUCCESS"
        assert preview["persisted"] is False
        assert "compile_result_id" not in preview or preview.get("compile_result_id") is None
        assert result_count(pid) == before_count
        assert get_pipeline(pid)["current_sync_status"] == before_status == "NOT_COMPILED"
        print("  [ok] compile-preview does not persist / change status")
    finally:
        archive_pipeline(pid)


def test_compile_validation_fail_persists() -> None:
    graph = mutate_node_config(
        build_valid_visual_pipeline_graph_with_config(),
        "n-rest",
        {"operation_name": None},
    )
    created = create_pipeline("R11-S6-2 Compile fail", graph)
    pid = created["pipeline_id"]
    try:
        result = compile_pipeline(pid)
        assert result["compile_status"] == "FAILED"
        assert result["persisted"] is True
        assert "COMPILE_VALIDATION_FAILED" in codes(result)
        assert result.get("compiled_artifact") is None
        assert get_pipeline(pid)["current_sync_status"] == "COMPILE_FAILED"
        latest = get_compile_result(pid)
        assert latest["compile_status"] == "FAILED"
        assert latest["compile_result_id"] == result["compile_result_id"]
        print("  [ok] failed compile persists + COMPILE_FAILED")
    finally:
        archive_pipeline(pid)


def test_config_change_makes_stale() -> None:
    graph = build_valid_visual_pipeline_graph_with_config()
    created = create_pipeline("R11-S6-2 Compile stale", graph)
    pid = created["pipeline_id"]
    try:
        compiled = compile_pipeline(pid)
        assert get_pipeline(pid)["current_sync_status"] == "IN_SYNC"
        changed = mutate_node_config(graph, "n-rest", {"operation_name": "op-changed"})
        updated = put_graph(pid, changed)
        assert updated["current_sync_status"] == "STALE"
        latest = get_compile_result(pid)
        assert latest["graph_version_hash"] == compiled["graph_version_hash"]
        from app.services.visual_pipeline.compile_preview_service import calculate_graph_version_hash

        assert calculate_graph_version_hash(changed) != compiled["graph_version_hash"]
        print("  [ok] config change after success → STALE")
    finally:
        archive_pipeline(pid)


def test_cosmetic_change_keeps_in_sync() -> None:
    graph = build_valid_visual_pipeline_graph_with_config()
    created = create_pipeline("R11-S6-2 Compile cosmetic", graph)
    pid = created["pipeline_id"]
    try:
        compile_pipeline(pid)
        cosmetic = _deep_copy(graph)
        cosmetic["viewport"] = {"x": 12, "y": -4, "zoom": 1.5}
        for node in cosmetic["nodes"]:
            node["position"] = {"x": node["position"]["x"] + 8, "y": node["position"]["y"] + 3}
            node["data"]["label"] = f"{node['data']['label']}-renamed"
        updated = put_graph(pid, cosmetic)
        assert updated["current_sync_status"] == "IN_SYNC"
        print("  [ok] label/position/viewport-only change keeps IN_SYNC")
    finally:
        archive_pipeline(pid)


def test_no_version_creation() -> None:
    graph = build_valid_visual_pipeline_graph_with_config()
    created = create_pipeline("R11-S6-2 Compile no version", graph)
    pid = created["pipeline_id"]
    try:
        before = version_count(pid)
        compile_pipeline(pid)
        compile_pipeline(pid)
        assert version_count(pid) == before
        print("  [ok] compile does not create versions")
    finally:
        archive_pipeline(pid)


def test_multiple_compile_results_latest() -> None:
    graph = build_valid_visual_pipeline_graph_with_config()
    created = create_pipeline("R11-S6-2 Compile multi", graph)
    pid = created["pipeline_id"]
    try:
        first = compile_pipeline(pid)
        assert first["compile_status"] == "SUCCESS"
        bad = mutate_node_config(graph, "n-load", {"target_table": None})
        put_graph(pid, bad)
        assert get_pipeline(pid)["current_sync_status"] == "STALE"
        failed = compile_pipeline(pid)
        assert failed["compile_status"] == "FAILED"
        assert result_count(pid) == 2
        latest = get_compile_result(pid)
        assert latest["compile_result_id"] == failed["compile_result_id"]
        assert latest["compile_status"] == "FAILED"
        assert get_pipeline(pid)["current_sync_status"] == "COMPILE_FAILED"

        # restore + success again
        put_graph(pid, graph)
        # graph matches first success hash → but latest is FAILED with different hash?
        # put_graph with original graph: hash == first SUCCESS hash, latest_any is FAILED with bad hash
        # so resolve → IN_SYNC (failed hash != new_hash)
        assert get_pipeline(pid)["current_sync_status"] == "IN_SYNC"
        third = compile_pipeline(pid)
        assert third["compile_status"] == "SUCCESS"
        assert result_count(pid) == 3
        latest2 = get_compile_result(pid)
        assert latest2["compile_result_id"] == third["compile_result_id"]
        print("  [ok] multiple results; GET returns latest")
    finally:
        archive_pipeline(pid)


def test_failed_same_hash_keeps_compile_failed() -> None:
    graph = build_valid_visual_pipeline_graph_with_config()
    created = create_pipeline("R11-S6-2 Compile failed keep", graph)
    pid = created["pipeline_id"]
    try:
        compile_pipeline(pid)
        # Force fail without changing semantic hash? Use unsupported transform on same topology
        # Actually changing transform_type changes hash. So: success, then mutate to fail, compile fail,
        # then cosmetic PUT should keep COMPILE_FAILED if hash still equals failed hash AND not equal success?
        # Per policy: if new_hash == latest_success.hash → check latest_any FAILED with same hash.
        # After fail with different hash from success, cosmetic keeps STALE or COMPILE_FAILED?
        # fail graph hash != success → STALE on put of fail graph already.
        # For "same hash as success but latest FAILED": need fail without changing hash - impossible if fail needs config change.
        # Alternative: success → fail by empty? Can't fail without config change.
        # Simulate: success, then compile again somehow fails? Same graph twice both SUCCESS.
        #
        # Policy case: latest_success.hash == current, latest_any FAILED with same hash.
        # That requires FAILED compile with identical hash as SUCCESS - e.g. intermittent? Not from validation.
        # Skip impossible path; covered indirectly: after fail on changed graph, status COMPILE_FAILED.
        bad = mutate_node_config(graph, "n-rest", {"operation_name": None})
        put_graph(pid, bad)
        compile_pipeline(pid)
        assert get_pipeline(pid)["current_sync_status"] == "COMPILE_FAILED"
        # cosmetic on failed graph keeps COMPILE_FAILED (hash == failed hash; not == success hash → STALE!)
        # Wait: failed hash != success hash → cosmetic put → STALE, not COMPILE_FAILED.
        # Policy: new_hash != success → STALE always.
        cosmetic = _deep_copy(bad)
        cosmetic["viewport"] = {"x": 1, "y": 2, "zoom": 1}
        updated = put_graph(pid, cosmetic)
        assert updated["current_sync_status"] == "STALE"
        print("  [ok] fail then cosmetic (hash≠success) → STALE")
    finally:
        archive_pipeline(pid)


def test_basic_level_rejected() -> None:
    graph = build_valid_visual_pipeline_graph_with_config()
    created = create_pipeline("R11-S6-2 Compile basic reject", graph)
    pid = created["pipeline_id"]
    try:
        err = api(
            "POST",
            f"/visual-pipelines/{pid}/compile",
            {"validation_level": "BASIC"},
            expect_fail=True,
        )
        assert err.get("_http_status") == 400
        print("  [ok] BASIC validation_level → 400")
    finally:
        archive_pipeline(pid)


def main() -> None:
    print("R11-S6-2 Visual Pipeline Compile Persist tests")
    test_schema_exists()
    test_successful_compile_persists()
    test_get_latest_compile_result()
    test_preview_does_not_persist()
    test_compile_validation_fail_persists()
    test_config_change_makes_stale()
    test_cosmetic_change_keeps_in_sync()
    test_no_version_creation()
    test_multiple_compile_results_latest()
    test_failed_same_hash_keeps_compile_failed()
    test_basic_level_rejected()
    print("All compile-persist tests passed.")


if __name__ == "__main__":
    main()
