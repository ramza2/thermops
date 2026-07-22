#!/usr/bin/env python3
"""R11-S6-4/S6-5 Visual Pipeline R10 materialization tests (no run/activation).

Boundary (S6-5):
- materialize upserts R10 config rows only
- schedule always inactive; activation=NOT_REQUESTED; run_created=false
- current_sync_status unchanged by materialize success/failure
- materialization_result is attempt history (+1 per call); R10 objects stay idempotent
- no load/call/schedule_run/dedup/target-table side effects
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

from test_fixtures import ensure_test_standard_datasets, psql_scalar  # noqa: E402
from test_visual_pipeline_graph_validation import (  # noqa: E402
    build_valid_visual_pipeline_graph_with_config,
    mutate_node_config,
)

SECRET_MARKERS = ("password", "api_key", "authorization", "secret_token", "bearer ")


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


def _psql(sql: str) -> str:
    return str(psql_scalar(sql) or "").strip()


def create_rest_source() -> str:
    tag = uuid4().hex[:8]
    created = api(
        "POST",
        "/data-sources",
        {
            "source_name": f"R11-S6-5 REST {tag}",
            "source_type": "REST_API",
            "data_domain": "HEAT_DEMAND",
            "connection_info": {
                "base_url": "https://example.invalid/api",
                "timeout_seconds": 10,
            },
            "active_yn": True,
        },
    )
    return created["source_id"]


def build_materialize_graph(data_source_id: str, *, schedule_active: bool = False) -> dict:
    graph = build_valid_visual_pipeline_graph_with_config()
    graph = mutate_node_config(
        graph,
        "n-rest",
        {
            "data_source_id": data_source_id,
            "operation_name": "vp-materialize-op",
            "endpoint_path": "/heat/demand",
            "http_method": "GET",
            "credential_ref": "CRED-REF-1",
        },
    )
    graph = mutate_node_config(
        graph,
        "n-load",
        {
            "standard_dataset_id": "TEST-DST-HEAT",
            "target_table": "heat_demand_actual",
            "write_mode": "UPSERT",
            "conflict_key_columns_json": ["site_id", "measured_at"],
        },
    )
    graph = mutate_node_config(
        graph,
        "n-cron",
        {
            "schedule_type": "CRON",
            "cron_expression": "0 6 * * *",
            "timezone": "Asia/Seoul",
            "active_yn": schedule_active,
        },
    )
    return graph


def build_direct_upsert_graph(data_source_id: str) -> dict:
    """REST → Upsert (no Transform)."""
    graph = build_materialize_graph(data_source_id)
    graph["nodes"] = [n for n in graph["nodes"] if n["id"] != "n-xform"]
    graph["edges"] = [e for e in graph["edges"] if e["id"] == "e1"]
    graph["edges"].append(
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
    )
    return graph


def create_pipeline(name: str, graph: dict) -> dict:
    return api(
        "POST",
        "/visual-pipelines",
        {"pipeline_name": name, "description": "R11-S6-5 materialization boundary test", "graph": graph},
    )


def archive_pipeline(pipeline_id: str) -> None:
    api("POST", f"/visual-pipelines/{pipeline_id}/archive")


def compile_pipeline(pipeline_id: str) -> dict:
    return api("POST", f"/visual-pipelines/{pipeline_id}/compile", {"validation_level": "STRICT"})


def materialize(pipeline_id: str, body: dict | None = None, *, expect_fail: bool = False) -> dict:
    return api(
        "POST",
        f"/visual-pipelines/{pipeline_id}/materialize",
        body if body is not None else {},
        expect_fail=expect_fail,
    )


def get_materialization_result(pipeline_id: str, *, expect_fail: bool = False) -> dict:
    return api(
        "GET",
        f"/visual-pipelines/{pipeline_id}/materialization-result",
        expect_fail=expect_fail,
    )


def get_pipeline(pipeline_id: str) -> dict:
    return api("GET", f"/visual-pipelines/{pipeline_id}")


def put_graph(pipeline_id: str, graph: dict) -> dict:
    return api("PUT", f"/visual-pipelines/{pipeline_id}", {"graph": graph, "create_version": False})


def count_table(table: str, where: str = "1=1") -> int:
    return int(_psql(f"SELECT COUNT(*) FROM {table} WHERE {where}") or "0")


def materialization_result_count(pipeline_id: str | None = None) -> int:
    where = "1=1" if not pipeline_id else f"pipeline_id='{pipeline_id}'"
    return count_table("tb_visual_pipeline_materialization_result", where)


def r10_origin_ops(pipeline_id: str) -> int:
    return count_table(
        "tb_api_connector_operation",
        f"metadata_json->'visual_pipeline_origin'->>'pipeline_id'='{pipeline_id}'",
    )


def r10_origin_schedules(pipeline_id: str) -> int:
    return count_table(
        "tb_data_load_schedule",
        f"metadata_json->'visual_pipeline_origin'->>'pipeline_id'='{pipeline_id}'",
    )


def snapshot_side_effects() -> dict[str, int]:
    checked = {
        "tb_api_connector_load_run": count_table("tb_api_connector_load_run"),
        "tb_data_load_schedule_run": count_table("tb_data_load_schedule_run"),
        "tb_api_connector_call_log": count_table("tb_api_connector_call_log"),
        "tb_api_connector_load_dedup_summary": count_table("tb_api_connector_load_dedup_summary"),
        "tb_heat_demand_actual": count_table("tb_heat_demand_actual"),
        "tb_data_load_schedule_active": count_table("tb_data_load_schedule", "active_yn IS TRUE"),
    }
    return checked


def assert_side_effects_unchanged(before: dict[str, int], *, label: str) -> None:
    after = snapshot_side_effects()
    for key, prev in before.items():
        assert after[key] == prev, f"{label}: {key} {prev} -> {after[key]}"
    print(f"  [side-effects ok] {label}: {', '.join(before.keys())}")


def assert_no_secret_leak(payload: dict) -> None:
    blob = json.dumps(payload, ensure_ascii=False).lower()
    for marker in SECRET_MARKERS:
        # credential_ref is allowed; reject raw secret-like values only when paired as values
        if marker in ("password", "api_key", "authorization") and f'"{marker}":' in blob:
            # allow credential_ref; fail if literal secret fields appear
            if '"credential_ref"' in blob and marker == "authorization":
                continue
            raise AssertionError(f"secret-like field leaked in response: {marker}")
    forbidden_values = ("sk-live-", "super-secret-", "Bearer ey")
    for val in forbidden_values:
        assert val.lower() not in blob, f"secret value leaked: {val}"


def http_detail(err: dict) -> str:
    detail = err.get("detail")
    if isinstance(detail, dict):
        return str(detail.get("code") or detail)
    return str(detail or "")


def test_schema_exists() -> None:
    assert (
        _psql(
            "SELECT COUNT(*) FROM information_schema.tables "
            "WHERE table_name='tb_visual_pipeline_materialization_result'"
        )
        == "1"
    )
    print("  [ok] tb_visual_pipeline_materialization_result exists")


def test_materialize_success_sync_inactive_norun() -> None:
    """SUCCESS materialize: IN_SYNC unchanged, schedule inactive, no run side effects."""
    ensure_test_standard_datasets()
    source_id = create_rest_source()
    graph = build_materialize_graph(source_id, schedule_active=True)
    created = create_pipeline("R11-S6-5 success inactive", graph)
    pid = created["pipeline_id"]
    before_fx = snapshot_side_effects()
    try:
        assert get_materialization_result(pid, expect_fail=True).get("_http_status") == 404
        compiled = compile_pipeline(pid)
        assert compiled["compile_status"] == "SUCCESS"
        sync_before = get_pipeline(pid)["current_sync_status"]
        assert sync_before == "IN_SYNC"

        result = materialize(pid, {"compile_result_id": compiled["compile_result_id"]})
        assert result["materialization_status"] == "SUCCESS", result
        assert result["materialization_version"] == "R11-S6-4"
        assert result["activation"] == "NOT_REQUESTED"
        assert result["run_created"] is False
        assert result["compile_result_id"] == compiled["compile_result_id"]
        objects = result["objects"]
        assert objects.get("operation_id")
        assert objects.get("transform_config_id")
        assert objects.get("write_policy_id")
        assert objects.get("schedule_id")

        sched_id = objects["schedule_id"]
        active = _psql(f"SELECT active_yn FROM tb_data_load_schedule WHERE schedule_id='{sched_id}'")
        assert active.lower() in {"f", "false", "0"}, active
        assert get_pipeline(pid)["current_sync_status"] == "IN_SYNC"
        assert_side_effects_unchanged(before_fx, label="after success materialize")
        assert_no_secret_leak(result)
        print("  [ok] SUCCESS + sync unchanged + forced inactive schedule + no-run")
    finally:
        archive_pipeline(pid)


def test_idempotency_r10_stable_result_history_grows() -> None:
    """R10 object ids stable; materialization_result attempt history may +1."""
    ensure_test_standard_datasets()
    source_id = create_rest_source()
    graph = build_materialize_graph(source_id, schedule_active=True)
    created = create_pipeline("R11-S6-5 idempotency", graph)
    pid = created["pipeline_id"]
    try:
        compile_pipeline(pid)
        first = materialize(pid)
        assert first["materialization_status"] == "SUCCESS", first
        objs = first["objects"]
        before_results = materialization_result_count(pid)
        before_ops = r10_origin_ops(pid)
        before_sched = r10_origin_schedules(pid)
        assert before_ops == 1
        assert before_sched == 1

        second = materialize(pid, {"compile_result_id": first["compile_result_id"]})
        assert second["materialization_status"] == "SUCCESS", second
        assert second["objects"]["operation_id"] == objs["operation_id"]
        assert second["objects"]["transform_config_id"] == objs["transform_config_id"]
        assert second["objects"]["write_policy_id"] == objs["write_policy_id"]
        assert second["objects"]["schedule_id"] == objs["schedule_id"]
        assert r10_origin_ops(pid) == before_ops == 1
        assert r10_origin_schedules(pid) == before_sched == 1
        # Expected: attempt history grows; R10 objects do not.
        assert materialization_result_count(pid) == before_results + 1
        assert second["materialization_result_id"] != first["materialization_result_id"]
        latest = get_materialization_result(pid)
        assert latest["materialization_result_id"] == second["materialization_result_id"]
        print("  [ok] idempotent R10 ids; materialization_result history +1")
    finally:
        archive_pipeline(pid)


def test_failed_materialize_does_not_change_sync() -> None:
    ensure_test_standard_datasets()
    graph = build_materialize_graph("DS-DOES-NOT-EXIST")
    created = create_pipeline("R11-S6-5 sync isolation fail", graph)
    pid = created["pipeline_id"]
    before_fx = snapshot_side_effects()
    try:
        compile_pipeline(pid)
        sync_before = get_pipeline(pid)["current_sync_status"]
        assert sync_before == "IN_SYNC"
        before_ops = count_table("tb_api_connector_operation")
        result = materialize(pid)
        assert result["materialization_status"] == "FAILED", result
        assert result["activation"] == "NOT_REQUESTED"
        assert result["run_created"] is False
        sync_after = get_pipeline(pid)["current_sync_status"]
        assert sync_after == sync_before == "IN_SYNC"
        assert sync_after != "COMPILE_FAILED"
        assert count_table("tb_api_connector_operation") == before_ops
        assert_side_effects_unchanged(before_fx, label="after failed materialize")
        print("  [ok] FAILED materialize keeps IN_SYNC (not COMPILE_FAILED)")
    finally:
        archive_pipeline(pid)


def test_stale_rejects_previous_compile_result() -> None:
    ensure_test_standard_datasets()
    source_id = create_rest_source()
    graph = build_materialize_graph(source_id)
    created = create_pipeline("R11-S6-5 stale", graph)
    pid = created["pipeline_id"]
    try:
        compiled = compile_pipeline(pid)
        first = materialize(pid, {"compile_result_id": compiled["compile_result_id"]})
        assert first["materialization_status"] == "SUCCESS", first
        objs = dict(first["objects"])
        before_ops = r10_origin_ops(pid)
        before_sched = r10_origin_schedules(pid)
        before_results = materialization_result_count(pid)

        stale_graph = mutate_node_config(graph, "n-rest", {"endpoint_path": "/changed"})
        put_graph(pid, stale_graph)
        assert get_pipeline(pid)["current_sync_status"] == "STALE"

        err = materialize(
            pid,
            {"compile_result_id": compiled["compile_result_id"]},
            expect_fail=True,
        )
        assert err.get("_http_status") == 409
        assert "STALE" in http_detail(err)
        assert r10_origin_ops(pid) == before_ops
        assert r10_origin_schedules(pid) == before_sched
        assert materialization_result_count(pid) == before_results
        # existing objects unchanged
        op_endpoint = _psql(
            "SELECT endpoint_path FROM tb_api_connector_operation "
            f"WHERE operation_id='{objs['operation_id']}'"
        )
        assert op_endpoint == "/heat/demand"
        print("  [ok] STALE rejects prior compile_result_id; R10 unchanged")
    finally:
        archive_pipeline(pid)


def test_no_compile_and_failed_compile_rejected() -> None:
    ensure_test_standard_datasets()
    source_id = create_rest_source()
    graph = build_materialize_graph(source_id)
    created = create_pipeline("R11-S6-5 preconditions", graph)
    pid = created["pipeline_id"]
    before_ops = count_table("tb_api_connector_operation")
    try:
        no_compile = materialize(pid, expect_fail=True)
        assert no_compile.get("_http_status") == 409
        assert "COMPILE_REQUIRED" in http_detail(no_compile)

        bad = mutate_node_config(graph, "n-rest", {"operation_name": None})
        put_graph(pid, bad)
        failed = compile_pipeline(pid)
        assert failed["compile_status"] == "FAILED"
        failed_id = failed["compile_result_id"]
        err = materialize(pid, {"compile_result_id": failed_id}, expect_fail=True)
        assert err.get("_http_status") == 409
        assert count_table("tb_api_connector_operation") == before_ops

        bad_mode = materialize(pid, {"mode": "CREATE"}, expect_fail=True)
        # may be 409 (no success compile) or 400 (bad mode) depending on check order
        assert bad_mode.get("_http_status") in {400, 409}

        put_graph(pid, graph)
        compile_pipeline(pid)
        bad_mode2 = materialize(pid, {"mode": "CREATE"}, expect_fail=True)
        assert bad_mode2.get("_http_status") == 400
        print("  [ok] no/failed compile → 409; bad mode → 400; no R10 create")
    finally:
        archive_pipeline(pid)


def test_direct_upsert_skips_transform() -> None:
    ensure_test_standard_datasets()
    source_id = create_rest_source()
    graph = build_direct_upsert_graph(source_id)
    created = create_pipeline("R11-S6-5 direct upsert", graph)
    pid = created["pipeline_id"]
    try:
        compile_pipeline(pid)
        result = materialize(pid)
        assert result["materialization_status"] == "SUCCESS", result
        assert "transform_config_id" not in (result.get("objects") or {})
        assert "transform_config" in (result.get("skipped") or [])
        assert result["objects"].get("operation_id")
        assert result["objects"].get("write_policy_id")
        print("  [ok] REST→Upsert skips transform_config; op/write_policy present")
    finally:
        archive_pipeline(pid)


def test_secret_safety_on_materialize_response() -> None:
    ensure_test_standard_datasets()
    source_id = create_rest_source()
    graph = build_materialize_graph(source_id)
    # credential_ref only — no inline secrets in graph values
    created = create_pipeline("R11-S6-5 secret safety", graph)
    pid = created["pipeline_id"]
    try:
        compile_pipeline(pid)
        result = materialize(pid)
        assert result["materialization_status"] == "SUCCESS", result
        assert_no_secret_leak(result)
        latest = get_materialization_result(pid)
        assert_no_secret_leak(latest)
        meta = _psql(
            "SELECT metadata_json::text FROM tb_api_connector_operation "
            f"WHERE operation_id='{result['objects']['operation_id']}'"
        ).lower()
        for forbidden in ("sk-live-", "super-secret-", "bearer ey"):
            assert forbidden not in meta
        print("  [ok] secret safety on materialize response/objects/metadata")
    finally:
        archive_pipeline(pid)


def test_migration_idempotent_rerun() -> None:
    test_schema_exists()
    env = os.environ.copy()
    env.setdefault("THERMOOPS_USE_DOCKER", "1")
    proc = subprocess.run(
        [sys.executable, str(_SCRIPTS / "apply_dev_migrations.py")],
        cwd=str(_ROOT),
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    assert proc.returncode == 0, proc.stdout + "\n" + proc.stderr
    assert "R11-S6-4 visual pipeline materialization result" in (proc.stdout or "")
    test_schema_exists()
    print("  [ok] apply_dev_migrations.py re-run PASSED")


def main() -> None:
    print("=== R11-S6-5 Visual Pipeline Materialization Boundary ===")
    test_schema_exists()
    test_materialize_success_sync_inactive_norun()
    test_idempotency_r10_stable_result_history_grows()
    test_failed_materialize_does_not_change_sync()
    test_stale_rejects_previous_compile_result()
    test_no_compile_and_failed_compile_rejected()
    test_direct_upsert_skips_transform()
    test_secret_safety_on_materialize_response()
    test_migration_idempotent_rerun()
    print("=== ALL PASSED ===")


if __name__ == "__main__":
    main()
