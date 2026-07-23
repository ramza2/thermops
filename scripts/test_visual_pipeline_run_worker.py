#!/usr/bin/env python3
"""R11-S7-6 Visual Pipeline Run Worker PoC tests.

Uses sample-external/heat-demand self-call — no operational external APIs.
quick regression group: NOT included (real REST/write side effects).
"""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
import time
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

os.environ.setdefault("POSTGRES_HOST", "localhost")
os.environ.setdefault(
    "DATABASE_URL",
    os.environ.get(
        "DATABASE_URL",
        "postgresql+asyncpg://thermops:thermops@localhost:5432/thermops",
    ),
)

API_BASE = os.environ.get("THERMOOPS_API_BASE", "http://localhost:8000/api/v1")
INTERNAL_API = os.environ.get("THERMOOPS_INTERNAL_API_BASE", "http://127.0.0.1:8000/api/v1")

from test_fixtures import ensure_test_standard_datasets, psql_run, psql_scalar  # noqa: E402
from test_visual_pipeline_graph_validation import mutate_node_config  # noqa: E402
from test_visual_pipeline_manual_run import (  # noqa: E402
    build_run_graph,
    create_run_rest_source,
    ensure_mapping,
    get_run,
    poll_run_until,
)
from test_visual_pipeline_materialization import (  # noqa: E402
    archive_pipeline,
    compile_pipeline,
    count_table,
    create_pipeline,
    materialize,
    snapshot_side_effects,
)


def _psql(sql: str) -> str:
    return str(psql_scalar(sql) or "").strip()


def api(
    method: str,
    path: str,
    body: dict | None = None,
    *,
    expect_fail: bool = False,
    expect_status: int | None = None,
) -> dict | list:
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
            status = resp.status
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
    if expect_status is not None and status != expect_status:
        raise AssertionError(f"expected HTTP {expect_status}, got {status} for {method} {path}")
    if not payload.get("success"):
        raise RuntimeError(f"API failed {method} {path}: {payload}")
    data_out = payload["data"]
    if isinstance(data_out, dict):
        data_out = dict(data_out)
        data_out["_http_status"] = status
    return data_out


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
    }


async def _create_pending_via_service(pipeline_id: str, *, executor: str = "worker") -> dict:
    from app.core.config import get_settings
    from app.core.database import async_session, engine
    from app.services.visual_pipeline.manual_run_service import create_manual_run

    get_settings.cache_clear()
    try:
        async with async_session() as db:
            return await create_manual_run(db, pipeline_id, {"mode": "MANUAL"}, executor=executor)
    finally:
        await engine.dispose()


def _async_run(coro):
    """asyncio.run with engine dispose — Windows asyncpg + multiple runs safe."""

    async def _wrapped():
        from app.core.database import engine

        try:
            return await coro
        finally:
            await engine.dispose()

    return asyncio.run(_wrapped())


def test_migration_columns() -> None:
    for col in ("claimed_at", "claimed_by", "locked_until", "heartbeat_at", "attempt_count"):
        found = _psql(
            "SELECT COUNT(*) FROM information_schema.columns "
            f"WHERE table_name='tb_visual_pipeline_run' AND column_name='{col}'"
        )
        assert found == "1", f"missing column {col}"
    print("  [ok] claim/lock columns exist")


def test_migration_rerun() -> None:
    env = os.environ.copy()
    docker_ok = True
    try:
        subprocess.check_output(["docker", "version"], stderr=subprocess.DEVNULL)
    except (FileNotFoundError, subprocess.CalledProcessError, OSError):
        docker_ok = False
    if not docker_ok:
        # Already applied from host; column check covers schema. Avoid asyncpg DSN + psycopg2.
        print("  [ok] apply_dev_migrations.py re-run skipped (no docker in this process)")
        return
    proc = subprocess.run(
        [sys.executable, str(_ROOT / "scripts" / "apply_dev_migrations.py")],
        cwd=str(_ROOT),
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "PASSED" in (proc.stdout or "")
    print("  [ok] apply_dev_migrations.py re-run PASSED")


def test_worker_enqueue_only_no_immediate_write() -> None:
    fx = setup_compiled_materialized("R11-S7-6 enqueue only")
    pid = fx["pipeline_id"]
    before_load = count_table("tb_api_connector_load_run")
    before_target = count_table("tb_heat_demand_actual")
    try:
        accepted = _async_run(_create_pending_via_service(pid, executor="worker"))
        assert accepted["run_status"] == "PENDING"
        assert accepted["execution_mode"] == "BACKGROUND"
        assert accepted.get("executor") == "worker"
        assert accepted["visual_run_id"].startswith("VPR-")
        time.sleep(2.0)
        assert count_table("tb_api_connector_load_run") == before_load
        assert count_table("tb_heat_demand_actual") == before_target
        status = _psql(
            f"SELECT run_status FROM tb_visual_pipeline_run "
            f"WHERE visual_run_id='{accepted['visual_run_id']}'"
        )
        assert status == "PENDING", status
        print(f"  [ok] worker enqueue stays PENDING visual_run_id={accepted['visual_run_id']}")
        # Do not leave PENDING for later claim tests
        psql_run(
            f"UPDATE tb_visual_pipeline_run SET run_status='CANCELLED', finished_at=NOW(), "
            f"locked_until=NULL WHERE visual_run_id='{accepted['visual_run_id']}'"
        )
    finally:
        archive_pipeline(pid)


def test_worker_once_happy_path() -> None:
    fx = setup_compiled_materialized("R11-S7-6 worker once happy")
    pid = fx["pipeline_id"]
    before_load = count_table("tb_api_connector_load_run")
    before_target = count_table("tb_heat_demand_actual")
    try:
        accepted = _async_run(_create_pending_via_service(pid, executor="worker"))
        run_id = accepted["visual_run_id"]
        # Isolate claim target from leftover PENDING rows
        psql_run(
            f"UPDATE tb_visual_pipeline_run SET run_status='CANCELLED', finished_at=NOW(), "
            f"locked_until=NULL WHERE run_status='PENDING' AND visual_run_id <> '{run_id}'"
        )

        from app.services.visual_pipeline.run_worker_service import run_worker_once

        summary = _async_run(
            run_worker_once(worker_id="test-worker-happy", batch_size=1, lock_ttl_seconds=120)
        )
        assert summary["claimed"] == 1, summary
        assert summary["results"][0]["visual_run_id"] == run_id, summary
        assert summary["results"][0]["run_status"] == "SUCCESS", summary

        detail = get_run(pid, run_id)
        assert detail["run_status"] == "SUCCESS", detail
        assert detail["load_run_id"]
        assert count_table("tb_api_connector_load_run") > before_load
        assert count_table("tb_heat_demand_actual") >= before_target
        claimed_by = _psql(
            f"SELECT claimed_by FROM tb_visual_pipeline_run WHERE visual_run_id='{run_id}'"
        )
        assert claimed_by == "test-worker-happy"
        locked = _psql(
            f"SELECT locked_until IS NULL FROM tb_visual_pipeline_run WHERE visual_run_id='{run_id}'"
        )
        assert locked.lower() in {"t", "true", "1"}
        print(f"  [ok] worker once SUCCESS visual_run_id={run_id} load_run_id={detail['load_run_id']}")
    finally:
        archive_pipeline(pid)


def test_worker_once_no_pending() -> None:
    from app.services.visual_pipeline.run_worker_service import run_worker_once

    # Use unique worker; may claim unrelated PENDING — clean known PENDING first is hard.
    # Claim with batch_size=1 against empty queue by ensuring no PENDING for random claim:
    # If other tests left PENDING, claimed may be >0. Prefer count PENDING globally.
    pending = int(
        _psql("SELECT COUNT(*) FROM tb_visual_pipeline_run WHERE run_status='PENDING'") or "0"
    )
    summary = _async_run(
        run_worker_once(worker_id="test-worker-empty", batch_size=1, lock_ttl_seconds=120)
    )
    if pending == 0:
        assert summary["claimed"] == 0, summary
        assert summary["executed"] == 0, summary
        print("  [ok] worker once with no PENDING claimed=0")
    else:
        # Drain one leftover then assert empty path
        assert summary["claimed"] >= 1
        summary2 = _async_run(
            run_worker_once(worker_id="test-worker-empty-2", batch_size=1, lock_ttl_seconds=120)
        )
        pending2 = int(
            _psql("SELECT COUNT(*) FROM tb_visual_pipeline_run WHERE run_status='PENDING'") or "0"
        )
        if pending2 == 0:
            summary3 = _async_run(
                run_worker_once(worker_id="test-worker-empty-3", batch_size=1, lock_ttl_seconds=120)
            )
            assert summary3["claimed"] == 0
            print("  [ok] worker once no PENDING after drain")
        else:
            print(f"  [ok] worker once drained leftover claimed={summary['claimed']} (pending left={pending2})")


def test_concurrent_claim() -> None:
    fx = setup_compiled_materialized("R11-S7-6 concurrent claim")
    pid = fx["pipeline_id"]
    try:
        accepted = _async_run(_create_pending_via_service(pid, executor="worker"))
        run_id = accepted["visual_run_id"]
        psql_run(
            f"UPDATE tb_visual_pipeline_run SET run_status='CANCELLED', finished_at=NOW(), "
            f"locked_until=NULL WHERE run_status='PENDING' AND visual_run_id <> '{run_id}'"
        )

        from app.core.database import async_session
        from app.services.visual_pipeline.run_worker_service import claim_next_visual_pipeline_runs

        async def claim(wid: str) -> list[str]:
            async with async_session() as db:
                return await claim_next_visual_pipeline_runs(
                    db, worker_id=wid, lock_ttl_seconds=120, batch_size=1
                )

        first = _async_run(claim("worker-a"))
        assert first == [run_id], first
        second = _async_run(claim("worker-b"))
        assert second == [], second
        run_status = _psql(
            f"SELECT run_status FROM tb_visual_pipeline_run WHERE visual_run_id='{run_id}'"
        )
        claimed_by = _psql(
            f"SELECT claimed_by FROM tb_visual_pipeline_run WHERE visual_run_id='{run_id}'"
        )
        assert run_status == "RUNNING", run_status
        assert claimed_by == "worker-a", claimed_by
        # Finish run to avoid leaving RUNNING stuck for other tests
        from app.services.visual_pipeline.run_worker_service import execute_claimed_visual_pipeline_run

        async def finish() -> None:
            async with async_session() as db:
                await execute_claimed_visual_pipeline_run(db, run_id, worker_id="worker-a")

        _async_run(finish())
        print("  [ok] concurrent claim: second worker gets none")
    finally:
        archive_pipeline(pid)


def test_runtime_failure() -> None:
    fx = setup_compiled_materialized(
        "R11-S7-6 worker fail", endpoint_path="/sample-external/not-found-route"
    )
    pid = fx["pipeline_id"]
    try:
        accepted = _async_run(_create_pending_via_service(pid, executor="worker"))
        run_id = accepted["visual_run_id"]
        psql_run(
            f"UPDATE tb_visual_pipeline_run SET run_status='CANCELLED', finished_at=NOW(), "
            f"locked_until=NULL WHERE run_status='PENDING' AND visual_run_id <> '{run_id}'"
        )
        from app.services.visual_pipeline.run_worker_service import run_worker_once

        summary = _async_run(
            run_worker_once(worker_id="test-worker-fail", batch_size=1, lock_ttl_seconds=120)
        )
        assert summary["claimed"] == 1
        assert summary["results"][0]["visual_run_id"] == run_id
        assert summary["results"][0]["run_status"] == "FAILED", summary
        detail = get_run(pid, run_id)
        assert detail["run_status"] == "FAILED"
        assert detail["issues"]
        print(f"  [ok] worker once FAILED visual_run_id={run_id}")
    finally:
        archive_pipeline(pid)


def test_boundary_unchanged() -> None:
    fx = setup_compiled_materialized("R11-S7-6 worker boundary")
    pid = fx["pipeline_id"]
    sched_id = fx["materialization"]["objects"].get("schedule_id")
    before = snapshot_side_effects()
    sync_before = api("GET", f"/visual-pipelines/{pid}")["current_sync_status"]
    active_before = _psql(f"SELECT active_yn FROM tb_data_load_schedule WHERE schedule_id='{sched_id}'")
    try:
        accepted = _async_run(_create_pending_via_service(pid, executor="worker"))
        run_id = accepted["visual_run_id"]
        psql_run(
            f"UPDATE tb_visual_pipeline_run SET run_status='CANCELLED', finished_at=NOW(), "
            f"locked_until=NULL WHERE run_status='PENDING' AND visual_run_id <> '{run_id}'"
        )
        from app.services.visual_pipeline.run_worker_service import run_worker_once

        summary = _async_run(
            run_worker_once(worker_id="test-worker-boundary", batch_size=1, lock_ttl_seconds=120)
        )
        assert summary["results"][0]["visual_run_id"] == run_id
        assert summary["results"][0]["run_status"] == "SUCCESS", summary
        sync_after = api("GET", f"/visual-pipelines/{pid}")["current_sync_status"]
        assert sync_after == sync_before == "IN_SYNC"
        active_after = _psql(f"SELECT active_yn FROM tb_data_load_schedule WHERE schedule_id='{sched_id}'")
        assert active_after == active_before
        assert active_after.lower() in {"f", "false", "0", "n"}
        after = snapshot_side_effects()
        assert after["tb_data_load_schedule_run"] == before["tb_data_load_schedule_run"]
        assert after["tb_data_load_schedule_active"] == before["tb_data_load_schedule_active"]
        print("  [ok] sync/schedule/due boundary unchanged")
    finally:
        archive_pipeline(pid)


def test_background_tasks_http_regression() -> None:
    """Default API executor remains background_tasks (docker backend default)."""
    fx = setup_compiled_materialized("R11-S7-6 bg regression")
    pid = fx["pipeline_id"]
    try:
        accepted = api("POST", f"/visual-pipelines/{pid}/runs", {}, expect_status=202)
        assert accepted.get("_http_status") == 202
        assert accepted["execution_mode"] == "BACKGROUND"
        result = poll_run_until(pid, accepted["visual_run_id"])
        assert result["run_status"] == "SUCCESS", result
        print(f"  [ok] background_tasks HTTP regression SUCCESS {accepted['visual_run_id']}")
    finally:
        archive_pipeline(pid)


def test_resolve_executor_fallback() -> None:
    from app.core.config import get_settings
    from app.services.visual_pipeline.manual_run_service import (
        EXECUTOR_BACKGROUND_TASKS,
        resolve_vp_run_executor,
    )

    get_settings.cache_clear()
    assert resolve_vp_run_executor("worker") == "worker"
    assert resolve_vp_run_executor("background_tasks") == "background_tasks"
    assert resolve_vp_run_executor("nope") == EXECUTOR_BACKGROUND_TASKS
    print("  [ok] executor resolve + invalid fallback")


def main() -> None:
    print("=== R11-S7-6 Visual Pipeline Run Worker ===")
    test_migration_columns()
    test_migration_rerun()
    test_resolve_executor_fallback()
    test_worker_enqueue_only_no_immediate_write()
    test_worker_once_happy_path()
    test_worker_once_no_pending()
    test_concurrent_claim()
    test_runtime_failure()
    test_boundary_unchanged()
    test_background_tasks_http_regression()
    print("=== ALL PASSED ===")


if __name__ == "__main__":
    main()
