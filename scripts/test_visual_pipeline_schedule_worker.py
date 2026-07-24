#!/usr/bin/env python3
"""R11-S7-8 Visual Pipeline schedule-worker enqueue + scheduled run execution tests.

Uses sample-external/heat-demand — no operational external APIs.
quick regression group: NOT included.
"""

from __future__ import annotations

import asyncio
import os
import sys
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

from test_fixtures import ensure_test_standard_datasets, psql_run, psql_scalar  # noqa: E402
from test_visual_pipeline_run_worker import setup_compiled_materialized  # noqa: E402
from test_visual_pipeline_materialization import archive_pipeline, snapshot_side_effects  # noqa: E402


def _psql(sql: str) -> str:
    return str(psql_scalar(sql) or "").strip()


def _async_run(coro):
    async def _wrapped():
        from app.core.database import engine

        try:
            return await coro
        finally:
            await engine.dispose()

    return asyncio.run(_wrapped())


def _enable_flags() -> tuple[str | None, str | None]:
    from app.core.config import get_settings

    prev_a = os.environ.get("THERMOOPS_VP_SCHEDULE_ACTIVATION_ENABLED")
    prev_w = os.environ.get("THERMOOPS_VP_SCHEDULE_WORKER_ENABLED")
    os.environ["THERMOOPS_VP_SCHEDULE_ACTIVATION_ENABLED"] = "true"
    os.environ["THERMOOPS_VP_SCHEDULE_WORKER_ENABLED"] = "true"
    get_settings.cache_clear()
    return prev_a, prev_w


def _restore_flags(prev_a: str | None, prev_w: str | None) -> None:
    from app.core.config import get_settings

    if prev_a is None:
        os.environ.pop("THERMOOPS_VP_SCHEDULE_ACTIVATION_ENABLED", None)
    else:
        os.environ["THERMOOPS_VP_SCHEDULE_ACTIVATION_ENABLED"] = prev_a
    if prev_w is None:
        os.environ.pop("THERMOOPS_VP_SCHEDULE_WORKER_ENABLED", None)
    else:
        os.environ["THERMOOPS_VP_SCHEDULE_WORKER_ENABLED"] = prev_w
    get_settings.cache_clear()


def test_no_due_enqueues_zero() -> None:
    print("== schedule worker no due ==")
    prev = _enable_flags()
    fixture = setup_compiled_materialized(f"S78-NODUE-{uuid4().hex[:6]}")
    pid = fixture["pipeline_id"]
    try:

        async def _run():
            from app.core.database import async_session
            from app.services.visual_pipeline.schedule_activation_service import activate_schedule
            from app.services.visual_pipeline.schedule_worker_service import (
                build_schedule_worker_id,
                run_schedule_worker_once,
            )

            async with async_session() as db:
                act = await activate_schedule(db, pid, {})
            # next_due_at is in the future — once should enqueue 0
            summary = await run_schedule_worker_once(
                worker_id=build_schedule_worker_id("test-nodue"),
                batch_size=10,
            )
            return act, summary

        act, summary = _async_run(_run())
        assert summary["enqueued"] == 0, summary
        runs = int(
            _psql(
                f"SELECT COUNT(*) FROM tb_visual_pipeline_run WHERE pipeline_id='{pid}' "
                f"AND mode='SCHEDULED'"
            )
            or "0"
        )
        assert runs == 0
        print(f"  PASS no-due enqueued=0 activation={act['activation_id']}")
    finally:
        _restore_flags(*prev)
        archive_pipeline(pid)


def test_due_enqueue_dedup_and_execute() -> None:
    print("== due enqueue + dedup + vp-run-worker ==")
    prev = _enable_flags()
    fixture = setup_compiled_materialized(f"S78-DUE-{uuid4().hex[:6]}")
    pid = fixture["pipeline_id"]
    mat = fixture["materialization"]
    sync_before = _psql(
        f"SELECT current_sync_status FROM tb_pipeline_definition WHERE pipeline_id='{pid}'"
    )
    mat_status_before = _psql(
        "SELECT materialization_status FROM tb_visual_pipeline_materialization_result "
        f"WHERE materialization_result_id='{mat['materialization_result_id']}'"
    )
    before = snapshot_side_effects()
    try:

        async def _activate_and_force_due():
            from app.core.database import async_session
            from app.services.visual_pipeline.schedule_activation_service import activate_schedule

            async with async_session() as db:
                act = await activate_schedule(db, pid, {})
            act_id = act["activation_id"]
            # Force due in the past
            psql_run(
                "UPDATE tb_visual_pipeline_schedule_activation "
                "SET next_due_at = NOW() - INTERVAL '1 minute', updated_at = NOW() "
                f"WHERE activation_id='{act_id}'"
            )
            return act

        act = _async_run(_activate_and_force_due())
        act_id = act["activation_id"]

        async def _enqueue():
            from app.services.visual_pipeline.schedule_worker_service import (
                build_schedule_worker_id,
                run_schedule_worker_once,
            )

            return await run_schedule_worker_once(
                worker_id=build_schedule_worker_id("test-due"),
                batch_size=10,
            )

        summary = _async_run(_enqueue())
        assert summary["enqueued"] >= 1, summary
        run_id = _psql(
            "SELECT visual_run_id FROM tb_visual_pipeline_run "
            f"WHERE pipeline_id='{pid}' AND mode='SCHEDULED' ORDER BY created_at DESC LIMIT 1"
        )
        assert run_id.startswith("VPR-"), run_id
        mode = _psql(f"SELECT mode FROM tb_visual_pipeline_run WHERE visual_run_id='{run_id}'")
        assert mode == "SCHEDULED"
        activation_id = _psql(
            f"SELECT activation_id FROM tb_visual_pipeline_run WHERE visual_run_id='{run_id}'"
        )
        assert activation_id == act_id
        r10 = _psql(
            f"SELECT r10_schedule_id FROM tb_visual_pipeline_run WHERE visual_run_id='{run_id}'"
        )
        assert r10 == act["r10_schedule_id"]
        scheduled_for = _psql(
            f"SELECT COALESCE(to_char(scheduled_for, 'YYYY-MM-DD\"T\"HH24:MI:SS'), '') "
            f"FROM tb_visual_pipeline_run WHERE visual_run_id='{run_id}'"
        )
        assert scheduled_for, f"expected scheduled_for set, got {scheduled_for!r}"
        dedup = _psql(f"SELECT dedup_key FROM tb_visual_pipeline_run WHERE visual_run_id='{run_id}'")
        assert dedup.startswith("VP-SCHEDULED:"), dedup
        status = _psql(f"SELECT run_status FROM tb_visual_pipeline_run WHERE visual_run_id='{run_id}'")
        assert status == "PENDING", status

        # Force same due again → duplicate skip (next_due already advanced; force again)
        psql_run(
            "UPDATE tb_visual_pipeline_schedule_activation "
            "SET next_due_at = ("
            f"  SELECT scheduled_for FROM tb_visual_pipeline_run WHERE visual_run_id='{run_id}'"
            "), updated_at = NOW() "
            f"WHERE activation_id='{act_id}'"
        )
        summary2 = _async_run(_enqueue())
        # either skipped duplicate or not_due depending on next_due advance race — must not create 2nd run
        runs = int(
            _psql(
                f"SELECT COUNT(*) FROM tb_visual_pipeline_run WHERE pipeline_id='{pid}' AND mode='SCHEDULED'"
            )
            or "0"
        )
        assert runs == 1, f"expected 1 scheduled run after duplicate, got {runs}; summary2={summary2}"

        async def _execute():
            from app.services.visual_pipeline.run_worker_service import (
                build_worker_id,
                run_worker_once,
            )

            return await run_worker_once(
                worker_id=build_worker_id("test-sched-run"),
                batch_size=5,
                lock_ttl_seconds=120,
            )

        exec_summary = _async_run(_execute())
        assert exec_summary.get("claimed", 0) >= 1 or exec_summary.get("success", 0) >= 1, exec_summary
        final_status = _psql(
            f"SELECT run_status FROM tb_visual_pipeline_run WHERE visual_run_id='{run_id}'"
        )
        assert final_status in {"SUCCESS", "PARTIAL", "FAILED"}, final_status

        sync_after = _psql(
            f"SELECT current_sync_status FROM tb_pipeline_definition WHERE pipeline_id='{pid}'"
        )
        mat_status_after = _psql(
            "SELECT materialization_status FROM tb_visual_pipeline_materialization_result "
            f"WHERE materialization_result_id='{mat['materialization_result_id']}'"
        )
        assert sync_after == sync_before
        assert mat_status_after == mat_status_before
        active_yn = _psql(
            "SELECT active_yn::text FROM tb_data_load_schedule "
            f"WHERE schedule_id='{act['r10_schedule_id']}'"
        )
        assert active_yn == "false"
        after = snapshot_side_effects()
        assert after["tb_api_connector_load_run"] >= before["tb_api_connector_load_run"]
        print(f"  PASS scheduled run {run_id} status={final_status} dedup={dedup}")
    finally:
        _restore_flags(*prev)
        archive_pipeline(pid)


def test_skip_when_active_run() -> None:
    print("== skip enqueue when PENDING exists ==")
    prev = _enable_flags()
    fixture = setup_compiled_materialized(f"S78-SKIP-{uuid4().hex[:6]}")
    pid = fixture["pipeline_id"]
    try:

        async def _setup():
            from app.core.database import async_session
            from app.services.visual_pipeline.manual_run_service import create_manual_run
            from app.services.visual_pipeline.schedule_activation_service import activate_schedule

            async with async_session() as db:
                act = await activate_schedule(db, pid, {})
                pending = await create_manual_run(db, pid, {"mode": "MANUAL"}, executor="worker")
            return act, pending

        act, pending = _async_run(_setup())
        assert pending["run_status"] == "PENDING"
        psql_run(
            "UPDATE tb_visual_pipeline_schedule_activation "
            "SET next_due_at = NOW() - INTERVAL '1 minute', updated_at = NOW() "
            f"WHERE activation_id='{act['activation_id']}'"
        )

        async def _enqueue():
            from app.services.visual_pipeline.schedule_worker_service import (
                build_schedule_worker_id,
                run_schedule_worker_once,
            )

            return await run_schedule_worker_once(
                worker_id=build_schedule_worker_id("test-skip"),
                batch_size=10,
            )

        summary = _async_run(_enqueue())
        reasons = [i.get("reason") for i in summary.get("items") or []]
        assert "skipped_active_run" in reasons or summary["enqueued"] == 0, summary
        scheduled = int(
            _psql(
                f"SELECT COUNT(*) FROM tb_visual_pipeline_run WHERE pipeline_id='{pid}' AND mode='SCHEDULED'"
            )
            or "0"
        )
        assert scheduled == 0
        # cleanup pending so archive is clean
        psql_run(
            f"DELETE FROM tb_visual_pipeline_run WHERE visual_run_id='{pending['visual_run_id']}'"
        )
        print("  PASS skipped_active_run")
    finally:
        _restore_flags(*prev)
        archive_pipeline(pid)


def main() -> int:
    ensure_test_standard_datasets()
    test_no_due_enqueues_zero()
    test_due_enqueue_dedup_and_execute()
    test_skip_when_active_run()
    print("\nAll schedule worker tests PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
