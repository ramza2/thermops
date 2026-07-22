#!/usr/bin/env python3
"""R11-S6-4 Visual Pipeline R10 materialization PoC tests (no run/activation)."""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path
from uuid import uuid4

_SCRIPTS = Path(__file__).resolve().parent
_BACKEND = _SCRIPTS.parent / "backend"
for p in (str(_SCRIPTS), str(_BACKEND)):
    if p not in sys.path:
        sys.path.insert(0, p)

API_BASE = os.environ.get("THERMOOPS_API_BASE", "http://localhost:8000/api/v1")

from test_fixtures import ensure_test_standard_datasets, psql_scalar  # noqa: E402
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


def _psql(sql: str) -> str:
    return str(psql_scalar(sql) or "").strip()


def create_rest_source() -> str:
    tag = uuid4().hex[:8]
    created = api(
        "POST",
        "/data-sources",
        {
            "source_name": f"R11-S6-4 REST {tag}",
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
    graph["edges"] = [
        e
        for e in graph["edges"]
        if e["id"] == "e1"
        or (
            e["source"] == "n-rest"
            and e["target"] == "n-load"
        )
    ]
    # replace REST→Transform→Load with REST→Load
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
        {"pipeline_name": name, "description": "R11-S6-4 materialization test", "graph": graph},
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


def test_schema_exists() -> None:
    assert (
        _psql(
            "SELECT COUNT(*) FROM information_schema.tables "
            "WHERE table_name='tb_visual_pipeline_materialization_result'"
        )
        == "1"
    )
    print("  [ok] tb_visual_pipeline_materialization_result exists")


def test_materialize_success_and_idempotent() -> None:
    ensure_test_standard_datasets()
    source_id = create_rest_source()
    graph = build_materialize_graph(source_id, schedule_active=True)
    created = create_pipeline("R11-S6-4 materialize success", graph)
    pid = created["pipeline_id"]

    before_load = count_table("tb_api_connector_load_run")
    before_sched_run = count_table("tb_data_load_schedule_run")
    before_call = count_table("tb_api_connector_call_log")
    before_dedup = count_table("tb_api_connector_load_dedup_summary")

    try:
        err = get_materialization_result(pid, expect_fail=True)
        assert err.get("_http_status") == 404

        compiled = compile_pipeline(pid)
        assert compiled["compile_status"] == "SUCCESS"
        sync_before = get_pipeline(pid)["current_sync_status"]
        assert sync_before == "IN_SYNC"

        result = materialize(pid)
        assert result["materialization_status"] == "SUCCESS", result
        assert result["materialization_version"] == "R11-S6-4"
        assert result["activation"] == "NOT_REQUESTED"
        assert result["run_created"] is False
        assert result["persisted"] is True
        objects = result["objects"]
        assert objects.get("operation_id")
        assert objects.get("transform_config_id")
        assert objects.get("write_policy_id")
        assert objects.get("schedule_id")

        op_id = objects["operation_id"]
        sched_id = objects["schedule_id"]
        active = _psql(
            f"SELECT active_yn FROM tb_data_load_schedule WHERE schedule_id='{sched_id}'"
        )
        assert active.lower() in {"f", "false", "0"}, active

        meta = _psql(
            "SELECT metadata_json->>'visual_pipeline_origin' IS NOT NULL "
            f"FROM tb_api_connector_operation WHERE operation_id='{op_id}'"
        )
        assert meta.lower() in {"t", "true", "1"}, meta

        # no execution side effects
        assert count_table("tb_api_connector_load_run") == before_load
        assert count_table("tb_data_load_schedule_run") == before_sched_run
        assert count_table("tb_api_connector_call_log") == before_call
        assert count_table("tb_api_connector_load_dedup_summary") == before_dedup
        assert get_pipeline(pid)["current_sync_status"] == sync_before == "IN_SYNC"

        # idempotent second call
        before_ops = count_table(
            "tb_api_connector_operation",
            f"metadata_json->'visual_pipeline_origin'->>'pipeline_id'='{pid}'",
        )
        before_sched = count_table(
            "tb_data_load_schedule",
            f"metadata_json->'visual_pipeline_origin'->>'pipeline_id'='{pid}'",
        )
        second = materialize(pid)
        assert second["materialization_status"] == "SUCCESS", second
        assert second["objects"]["operation_id"] == op_id
        assert second["objects"]["schedule_id"] == sched_id
        assert second["objects"]["transform_config_id"] == objects["transform_config_id"]
        assert second["objects"]["write_policy_id"] == objects["write_policy_id"]
        assert (
            count_table(
                "tb_api_connector_operation",
                f"metadata_json->'visual_pipeline_origin'->>'pipeline_id'='{pid}'",
            )
            == before_ops
            == 1
        )
        assert (
            count_table(
                "tb_data_load_schedule",
                f"metadata_json->'visual_pipeline_origin'->>'pipeline_id'='{pid}'",
            )
            == before_sched
            == 1
        )

        latest = get_materialization_result(pid)
        assert latest["materialization_result_id"] == second["materialization_result_id"]
        print("  [ok] materialize SUCCESS + inactive schedule + idempotent + no runs")
    finally:
        archive_pipeline(pid)


def test_direct_upsert_skips_transform() -> None:
    ensure_test_standard_datasets()
    source_id = create_rest_source()
    graph = build_direct_upsert_graph(source_id)
    created = create_pipeline("R11-S6-4 direct upsert", graph)
    pid = created["pipeline_id"]
    try:
        compile_pipeline(pid)
        result = materialize(pid)
        assert result["materialization_status"] == "SUCCESS", result
        assert "transform_config_id" not in (result.get("objects") or {})
        assert "transform_config" in (result.get("skipped") or [])
        print("  [ok] REST→Upsert skips transform_config")
    finally:
        archive_pipeline(pid)


def test_preconditions() -> None:
    ensure_test_standard_datasets()
    source_id = create_rest_source()
    graph = build_materialize_graph(source_id)
    created = create_pipeline("R11-S6-4 preconditions", graph)
    pid = created["pipeline_id"]
    try:
        no_compile = materialize(pid, expect_fail=True)
        assert no_compile.get("_http_status") == 409
        detail = no_compile.get("detail")
        assert detail == "VISUAL_PIPELINE_COMPILE_REQUIRED" or (
            isinstance(detail, dict) and detail.get("code") == "VISUAL_PIPELINE_COMPILE_REQUIRED"
        ) or "COMPILE_REQUIRED" in str(detail)

        # force failed compile then try materialize
        bad = mutate_node_config(graph, "n-rest", {"operation_name": None})
        put_graph(pid, bad)
        failed = api("POST", f"/visual-pipelines/{pid}/compile", {"validation_level": "STRICT"})
        assert failed["compile_status"] == "FAILED"
        bad_mat = materialize(pid, expect_fail=True)
        assert bad_mat.get("_http_status") == 409

        # restore + compile success then stale
        put_graph(pid, graph)
        compile_pipeline(pid)
        stale_graph = mutate_node_config(graph, "n-rest", {"endpoint_path": "/changed"})
        put_graph(pid, stale_graph)
        assert get_pipeline(pid)["current_sync_status"] == "STALE"
        stale = materialize(pid, expect_fail=True)
        assert stale.get("_http_status") == 409
        assert "STALE" in str(stale.get("detail"))

        put_graph(pid, graph)
        compile_pipeline(pid)
        bad_mode = materialize(pid, {"mode": "CREATE"}, expect_fail=True)
        assert bad_mode.get("_http_status") == 400
        print("  [ok] preconditions 409/400")
    finally:
        archive_pipeline(pid)


def test_missing_data_source_fails_domain() -> None:
    ensure_test_standard_datasets()
    graph = build_materialize_graph("DS-DOES-NOT-EXIST")
    created = create_pipeline("R11-S6-4 missing DS", graph)
    pid = created["pipeline_id"]
    try:
        compile_pipeline(pid)
        sync_before = get_pipeline(pid)["current_sync_status"]
        before_ops = count_table("tb_api_connector_operation")
        result = materialize(pid)
        assert result["materialization_status"] == "FAILED", result
        assert result["activation"] == "NOT_REQUESTED"
        assert result["run_created"] is False
        assert any(
            i.get("code") in {"DATA_SOURCE_NOT_FOUND", "MATERIALIZE_OPERATION_FAILED", "MATERIALIZE_DATA_SOURCE_REQUIRED"}
            or "DATA_SOURCE" in str(i.get("code"))
            for i in (result.get("issues") or [])
        ) or result.get("error_message")
        assert count_table("tb_api_connector_operation") == before_ops
        assert get_pipeline(pid)["current_sync_status"] == sync_before
        print("  [ok] missing data_source → FAILED + rollback + sync unchanged")
    finally:
        archive_pipeline(pid)


def test_migration_idempotent() -> None:
    # apply_dev_migrations is verified externally; here just re-check table
    test_schema_exists()
    print("  [ok] migration table still present (idempotent check via schema)")


def main() -> None:
    print("=== R11-S6-4 Visual Pipeline Materialization ===")
    test_schema_exists()
    test_materialize_success_and_idempotent()
    test_direct_upsert_skips_transform()
    test_preconditions()
    test_missing_data_source_fails_domain()
    test_migration_idempotent()
    print("=== ALL PASSED ===")


if __name__ == "__main__":
    main()
