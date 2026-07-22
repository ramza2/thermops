#!/usr/bin/env python3
"""R11-S7-1 Visual Pipeline Manual Run PoC tests.

Uses backend sample-external/heat-demand self-call — no operational external APIs.
quick regression group: NOT included (real REST/write side effects).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path
from uuid import uuid4

_SCRIPTS = Path(__file__).resolve().parent
_ROOT = _SCRIPTS.parent
_BACKEND = _ROOT / "backend"
for p in (str(_SCRIPTS), str(_BACKEND)):
    if p not in sys.path:
        sys.path.insert(0, p)

API_BASE = os.environ.get("THERMOOPS_API_BASE", "http://localhost:8000/api/v1")
INTERNAL_API = os.environ.get("THERMOOPS_INTERNAL_API_BASE", "http://127.0.0.1:8000/api/v1")

from test_fixtures import ensure_test_standard_datasets, psql_scalar  # noqa: E402
from test_visual_pipeline_graph_validation import (  # noqa: E402
    build_valid_visual_pipeline_graph_with_config,
    mutate_node_config,
)
from test_visual_pipeline_materialization import (  # noqa: E402
    SECRET_MARKERS,
    archive_pipeline,
    assert_no_secret_leak,
    build_direct_upsert_graph,
    build_materialize_graph,
    compile_pipeline,
    count_table,
    create_pipeline,
    get_pipeline,
    http_detail,
    materialize,
    put_graph,
    snapshot_side_effects,
)

SECRET_MARKERS_RUN = SECRET_MARKERS


def api(method: str, path: str, body: dict | None = None, *, expect_fail: bool = False) -> dict | list:
    url = f"{API_BASE}{path}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={"Content-Type": "application/json"} if data else {},
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
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


def _psql(sql: str) -> str:
    return str(psql_scalar(sql) or "").strip()


def create_run_rest_source() -> str:
    tag = uuid4().hex[:8]
    created = api(
        "POST",
        "/data-sources",
        {
            "source_name": f"R11-S7-1 REST {tag}",
            "source_type": "REST_API",
            "data_domain": "HEAT_DEMAND",
            "connection_info": {
                "base_url": INTERNAL_API,
                "timeout_seconds": 30,
            },
            "active_yn": True,
        },
    )
    return created["source_id"]


def ensure_mapping(source_id: str) -> str:
    for m in api("GET", "/mappings?page=1&size=100")["items"]:
        if m["source_id"] == source_id and m.get("target_table") == "heat_demand_actual":
            return m["mapping_id"]
    api(
        "POST",
        "/mappings",
        {
            "source_id": source_id,
            "mapping_name": f"R11-S7-1 mapping {uuid4().hex[:6]}",
            "target_table": "heat_demand_actual",
            "columns": [
                {"source_column": "site_id", "target_column": "site_id", "required_yn": True},
                {"source_column": "measured_at", "target_column": "measured_at", "required_yn": True},
                {"source_column": "heat_demand", "target_column": "heat_demand", "required_yn": True},
                {"source_column": "supply_temp", "target_column": "supply_temp", "required_yn": False},
            ],
        },
    )
    for m in api("GET", "/mappings?page=1&size=100")["items"]:
        if m["source_id"] == source_id and m.get("target_table") == "heat_demand_actual":
            return m["mapping_id"]
    raise RuntimeError("mapping create failed")


def build_run_graph(data_source_id: str, *, endpoint_path: str = "/sample-external/heat-demand") -> dict:
    graph = build_materialize_graph(data_source_id, schedule_active=False)
    graph = mutate_node_config(
        graph,
        "n-rest",
        {
            "endpoint_path": endpoint_path,
            "response_item_path": "data.items",
            "http_method": "GET",
        },
    )
    return graph


def setup_compiled_materialized(name: str, *, endpoint_path: str = "/sample-external/heat-demand") -> dict:
    ensure_test_standard_datasets()
    source_id = create_run_rest_source()
    ensure_mapping(source_id)
    graph = build_run_graph(source_id, endpoint_path=endpoint_path)
    created = create_pipeline(name, graph)
    pid = created["pipeline_id"]
    compiled = compile_pipeline(pid)
    assert compiled["compile_status"] == "SUCCESS"
    mat = materialize(pid, {"compile_result_id": compiled["compile_result_id"]})
    assert mat["materialization_status"] == "SUCCESS", mat
    return {
        "pipeline_id": pid,
        "compile": compiled,
        "materialization": mat,
        "source_id": source_id,
        "graph": graph,
    }


def run_manual(pipeline_id: str, body: dict | None = None, *, expect_fail: bool = False) -> dict:
    return api("POST", f"/visual-pipelines/{pipeline_id}/runs", body or {}, expect_fail=expect_fail)


def list_runs(pipeline_id: str) -> dict:
    return api("GET", f"/visual-pipelines/{pipeline_id}/runs")


def get_run(pipeline_id: str, run_id: str, *, expect_fail: bool = False) -> dict:
    return api("GET", f"/visual-pipelines/{pipeline_id}/runs/{run_id}", expect_fail=expect_fail)


def test_schema_exists() -> None:
    assert (
        _psql(
            "SELECT COUNT(*) FROM information_schema.tables "
            "WHERE table_name='tb_visual_pipeline_run'"
        )
        == "1"
    )
    print("  [ok] tb_visual_pipeline_run exists")


def test_happy_path() -> None:
    fx = setup_compiled_materialized("R11-S7-1 happy path")
    pid = fx["pipeline_id"]
    before_load = count_table("tb_api_connector_load_run")
    before_target = count_table("tb_heat_demand_actual")
    try:
        result = run_manual(pid)
        assert result["run_status"] == "SUCCESS", result
        assert result["visual_run_id"].startswith("VPR-")
        assert result["load_run_id"]
        assert result["schedule_active_changed"] is False
        assert result["current_sync_status_changed"] is False
        assert result["result"]["operation_id"]
        assert result["result"]["write_policy_id"]
        assert result["result"]["target_table"] == "heat_demand_actual"
        assert count_table("tb_api_connector_load_run") > before_load
        assert count_table("tb_heat_demand_actual") >= before_target

        listed = list_runs(pid)
        ids = [r["visual_run_id"] for r in listed["items"]]
        assert result["visual_run_id"] in ids

        detail = get_run(pid, result["visual_run_id"])
        assert detail["run_status"] == "SUCCESS"
        assert detail["load_run_id"] == result["load_run_id"]
        assert_no_secret_leak(detail)
        print(f"  [ok] happy path visual_run_id={result['visual_run_id']} load_run_id={result['load_run_id']}")
    finally:
        archive_pipeline(pid)


def test_preconditions_no_materialize() -> None:
    ensure_test_standard_datasets()
    source_id = create_run_rest_source()
    graph = build_run_graph(source_id)
    created = create_pipeline("R11-S7-1 no mat", graph)
    pid = created["pipeline_id"]
    before = snapshot_side_effects()
    try:
        compile_pipeline(pid)
        err = run_manual(pid, expect_fail=True)
        assert err.get("_http_status") == 409
        assert http_detail(err) == "RUN_MATERIALIZATION_REQUIRED"
        assert_side_effects_unchanged(before, label="no materialize precondition")
        print("  [ok] no materialization -> 409, no side effects")
    finally:
        archive_pipeline(pid)


def test_preconditions_no_compile() -> None:
    ensure_test_standard_datasets()
    source_id = create_run_rest_source()
    graph = build_run_graph(source_id)
    created = create_pipeline("R11-S7-1 no compile", graph)
    pid = created["pipeline_id"]
    before = snapshot_side_effects()
    try:
        err = run_manual(pid, expect_fail=True)
        assert err.get("_http_status") == 409
        assert http_detail(err) in {"RUN_COMPILE_REQUIRED", "RUN_MATERIALIZATION_REQUIRED", "RUN_COMPILE_STALE"}
        assert_side_effects_unchanged(before, label="no compile precondition")
        print("  [ok] no compile -> 409, no side effects")
    finally:
        archive_pipeline(pid)


def test_precondition_compile_stale() -> None:
    fx = setup_compiled_materialized("R11-S7-1 stale compile")
    pid = fx["pipeline_id"]
    before = snapshot_side_effects()
    try:
        graph = fx["graph"]
        graph = mutate_node_config(graph, "n-rest", {"operation_name": f"stale-{uuid4().hex[:4]}"})
        put_graph(pid, graph)
        assert get_pipeline(pid)["current_sync_status"] == "STALE"
        err = run_manual(pid, expect_fail=True)
        assert err.get("_http_status") == 409
        assert http_detail(err) == "RUN_COMPILE_STALE"
        assert_side_effects_unchanged(before, label="stale compile precondition")
        print("  [ok] compile stale -> 409")
    finally:
        archive_pipeline(pid)


def test_precondition_failed_materialization() -> None:
    ensure_test_standard_datasets()
    graph = build_materialize_graph("DS-DOES-NOT-EXIST")
    created = create_pipeline("R11-S7-1 failed mat", graph)
    pid = created["pipeline_id"]
    before = snapshot_side_effects()
    try:
        compile_pipeline(pid)
        mat = materialize(pid)
        assert mat["materialization_status"] == "FAILED"
        err = run_manual(pid, expect_fail=True)
        assert err.get("_http_status") == 409
        assert http_detail(err) == "RUN_MATERIALIZATION_NOT_SUCCESS"
        assert_side_effects_unchanged(before, label="failed materialization precondition")
        print("  [ok] failed materialization -> 409")
    finally:
        archive_pipeline(pid)


def test_concurrent_running() -> None:
    fx = setup_compiled_materialized("R11-S7-1 concurrent")
    pid = fx["pipeline_id"]
    compile_id = fx["compile"]["compile_result_id"]
    mat_id = fx["materialization"]["materialization_result_id"]
    fake_id = f"VPR-TEST{uuid4().hex[:4].upper()}"
    before = snapshot_side_effects()
    try:
        _psql(
            f"""
            INSERT INTO tb_visual_pipeline_run (
                visual_run_id, pipeline_id, compile_result_id, materialization_result_id,
                run_status, mode, execution_mode, created_at, started_at
            ) VALUES (
                '{fake_id}', '{pid}', '{compile_id}', '{mat_id}',
                'RUNNING', 'MANUAL', 'SYNC', NOW(), NOW()
            )
            """
        )
        err = run_manual(pid, expect_fail=True)
        assert err.get("_http_status") == 409
        assert http_detail(err) == "RUN_CONCURRENT_RUN_EXISTS"
        assert_side_effects_unchanged(before, label="concurrent precondition")
        print("  [ok] concurrent RUNNING fixture -> 409")
    finally:
        _psql(f"DELETE FROM tb_visual_pipeline_run WHERE visual_run_id='{fake_id}'")
        archive_pipeline(pid)


def test_runtime_failure() -> None:
    fx = setup_compiled_materialized("R11-S7-1 runtime fail", endpoint_path="/sample-external/not-found-route")
    pid = fx["pipeline_id"]
    try:
        result = run_manual(pid)
        assert result["run_status"] == "FAILED", result
        assert result["visual_run_id"].startswith("VPR-")
        assert result["issues"]
        codes = {i.get("code") for i in result["issues"]}
        assert codes & {"RUN_REST_CALL_FAILED", "RUN_RESPONSE_EXTRACTION_FAILED", "RUN_WRITE_POLICY_FAILED"}
        assert_no_secret_leak(result)
        print(f"  [ok] runtime failure run_status=FAILED codes={codes}")
    finally:
        archive_pipeline(pid)


def test_direct_rest_upsert() -> None:
    ensure_test_standard_datasets()
    source_id = create_run_rest_source()
    ensure_mapping(source_id)
    graph = build_direct_upsert_graph(source_id)
    graph = mutate_node_config(
        graph,
        "n-rest",
        {
            "endpoint_path": "/sample-external/heat-demand",
            "response_item_path": "data.items",
        },
    )
    created = create_pipeline("R11-S7-1 direct upsert", graph)
    pid = created["pipeline_id"]
    try:
        compile_pipeline(pid)
        mat = materialize(pid)
        assert mat["materialization_status"] == "SUCCESS"
        assert mat["objects"].get("operation_id")
        assert not mat["objects"].get("transform_config_id")
        result = run_manual(pid)
        assert result["run_status"] == "SUCCESS", result
        print("  [ok] REST->Upsert direct run SUCCESS")
    finally:
        archive_pipeline(pid)


def test_secret_override_rejected() -> None:
    fx = setup_compiled_materialized("R11-S7-1 secret override")
    pid = fx["pipeline_id"]
    try:
        err = run_manual(
            pid,
            {"params": {"request_params_override": {"api_key": "sk-live-test"}}},
            expect_fail=True,
        )
        assert err.get("_http_status") == 400
        assert http_detail(err) == "RUN_SECRET_INLINE_FORBIDDEN"
        print("  [ok] secret override -> 400")
    finally:
        archive_pipeline(pid)


def test_boundary_sync_and_schedule_unchanged() -> None:
    fx = setup_compiled_materialized("R11-S7-1 boundary")
    pid = fx["pipeline_id"]
    sched_id = fx["materialization"]["objects"].get("schedule_id")
    before = snapshot_side_effects()
    sync_before = get_pipeline(pid)["current_sync_status"]
    active_before = _psql(f"SELECT active_yn FROM tb_data_load_schedule WHERE schedule_id='{sched_id}'")
    try:
        result = run_manual(pid)
        assert result["run_status"] == "SUCCESS"
        assert get_pipeline(pid)["current_sync_status"] == sync_before == "IN_SYNC"
        active_after = _psql(f"SELECT active_yn FROM tb_data_load_schedule WHERE schedule_id='{sched_id}'")
        assert active_after == active_before
        assert active_after.lower() in {"f", "false", "0"}
        after = snapshot_side_effects()
        assert after["tb_data_load_schedule_run"] == before["tb_data_load_schedule_run"]
        print("  [ok] sync unchanged + schedule inactive + no schedule_run")
    finally:
        archive_pipeline(pid)


def test_repeat_run_new_visual_run_id() -> None:
    fx = setup_compiled_materialized("R11-S7-1 repeat run")
    pid = fx["pipeline_id"]
    try:
        first = run_manual(pid)
        second = run_manual(pid)
        assert first["run_status"] == "SUCCESS"
        assert second["run_status"] == "SUCCESS"
        assert first["visual_run_id"] != second["visual_run_id"]
        print("  [ok] repeated manual run creates new visual_run_id")
    finally:
        archive_pipeline(pid)


def test_dry_run_rejected() -> None:
    fx = setup_compiled_materialized("R11-S7-1 dry run")
    pid = fx["pipeline_id"]
    try:
        err = run_manual(pid, {"dry_run": True}, expect_fail=True)
        assert err.get("_http_status") == 400
        assert http_detail(err) == "RUN_DRY_RUN_NOT_SUPPORTED"
        print("  [ok] dry_run=true -> 400")
    finally:
        archive_pipeline(pid)


def assert_side_effects_unchanged(before: dict[str, int], *, label: str) -> None:
    after = snapshot_side_effects()
    for key, prev in before.items():
        assert after[key] == prev, f"{label}: {key} {prev} -> {after[key]}"
    print(f"  [side-effects ok] {label}")


def test_migration_rerun() -> None:
    root = Path(__file__).resolve().parent.parent
    proc = subprocess.run(
        [sys.executable, "scripts/apply_dev_migrations.py"],
        cwd=root,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr or proc.stdout
    print("  [ok] apply_dev_migrations.py re-run PASSED")


def main() -> None:
    print("=== R11-S7-1 Visual Pipeline Manual Run ===")
    test_schema_exists()
    test_happy_path()
    test_preconditions_no_materialize()
    test_preconditions_no_compile()
    test_precondition_compile_stale()
    test_precondition_failed_materialization()
    test_concurrent_running()
    test_runtime_failure()
    test_direct_rest_upsert()
    test_secret_override_rejected()
    test_boundary_sync_and_schedule_unchanged()
    test_repeat_run_new_visual_run_id()
    test_dry_run_rejected()
    test_migration_rerun()
    print("=== ALL PASSED ===")


if __name__ == "__main__":
    main()
