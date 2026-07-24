#!/usr/bin/env python3
"""R11-S7-10 Visual Pipeline ops summary / stuck / mark-failed tests.

Uses sample-external/heat-demand — no operational external APIs.
quick regression group: NOT included.
"""

from __future__ import annotations

import asyncio
import json
import os
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

os.environ.setdefault("POSTGRES_HOST", "localhost")
os.environ.setdefault(
    "DATABASE_URL",
    os.environ.get(
        "DATABASE_URL",
        "postgresql+asyncpg://thermops:thermops@localhost:5432/thermops",
    ),
)

API_BASE = os.environ.get("THERMOOPS_API_BASE", "http://localhost:8000/api/v1")

from test_fixtures import ensure_test_standard_datasets, psql_run, psql_scalar  # noqa: E402
from test_visual_pipeline_materialization import archive_pipeline  # noqa: E402
from test_visual_pipeline_run_worker import setup_compiled_materialized  # noqa: E402


def _psql(sql: str) -> str:
    return str(psql_scalar(sql) or "").strip()


def api(method: str, path: str, body: dict | None = None) -> dict | list:
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
        raise RuntimeError(f"HTTP {exc.code} {method} {path}: {detail}") from exc
    if not payload.get("success"):
        raise RuntimeError(f"API failed {method} {path}: {payload}")
    return payload["data"]


def _async_run(coro):
    async def _wrapped():
        from app.core.database import engine

        try:
            return await coro
        finally:
            await engine.dispose()

    return asyncio.run(_wrapped())


def _create_pending(pipeline_id: str) -> dict:
    async def _run():
        from app.core.database import async_session
        from app.services.visual_pipeline.manual_run_service import create_manual_run

        async with async_session() as db:
            return await create_manual_run(
                db, pipeline_id, {"mode": "MANUAL"}, executor="worker"
            )

    return _async_run(_run())


def _clone_run(source_run_id: str, *, run_status: str = "PENDING") -> str:
    """Insert another run row for the same pipeline (bypasses concurrent-run guard)."""
    new_id = f"VPR-{uuid4().hex[:8].upper()}"
    psql_run(
        f"""
        INSERT INTO tb_visual_pipeline_run (
            visual_run_id, pipeline_id, compile_result_id, materialization_result_id,
            graph_version_hash, mode, execution_mode, run_status,
            request_json, result_json, issues_json, attempt_count, created_at
        )
        SELECT
            '{new_id}', pipeline_id, compile_result_id, materialization_result_id,
            graph_version_hash, mode, execution_mode, '{run_status}',
            COALESCE(request_json, '{{}}'::jsonb), '{{}}'::jsonb, '[]'::jsonb, 0, NOW()
        FROM tb_visual_pipeline_run
        WHERE visual_run_id='{source_run_id}'
        """
    )
    return new_id


def test_ops_summary_api() -> None:
    print("== ops summary API ==")
    data = api("GET", "/visual-pipeline-ops/summary")
    assert "run_status_counts" in data
    assert "PENDING" in data["run_status_counts"]
    assert "activation_status_counts" in data
    assert "ACTIVE" in data["activation_status_counts"]
    cfg = data["worker_config"]
    assert "run_executor" in cfg
    assert "schedule_activation_enabled" in cfg
    assert "run_worker_lock_ttl_seconds" in cfg
    assert "stuck_summary" in data
    assert "pending_older_than_threshold" in data["stuck_summary"]
    assert "running_lock_expired" in data["stuck_summary"]
    assert "activity_hints" in data
    assert isinstance(data.get("recent_failures"), list)
    print("  PASS summary counts + worker_config")


def test_stuck_runs_detection() -> None:
    print("== stuck-runs detection ==")
    fixture = setup_compiled_materialized(f"S710-STUCK-{uuid4().hex[:6]}")
    pid = fixture["pipeline_id"]
    try:
        seed = _create_pending(pid)
        old_pending_id = seed["visual_run_id"]
        fresh_pending_id = _clone_run(old_pending_id)
        expired_running_id = _clone_run(old_pending_id)
        live_running_id = _clone_run(old_pending_id)
        terminal_id = _clone_run(old_pending_id)

        psql_run(
            f"UPDATE tb_visual_pipeline_run SET created_at = NOW() - INTERVAL '20 minutes' "
            f"WHERE visual_run_id='{old_pending_id}'"
        )
        psql_run(
            f"UPDATE tb_visual_pipeline_run SET run_status='RUNNING', started_at=NOW(), "
            f"claimed_by='ops-test', claimed_at=NOW() - INTERVAL '15 minutes', "
            f"locked_until=NOW() - INTERVAL '10 minutes', "
            f"heartbeat_at=NOW() - INTERVAL '10 minutes' "
            f"WHERE visual_run_id='{expired_running_id}'"
        )
        psql_run(
            f"UPDATE tb_visual_pipeline_run SET run_status='RUNNING', started_at=NOW(), "
            f"claimed_by='ops-test', claimed_at=NOW(), "
            f"locked_until=NOW() + INTERVAL '10 minutes', heartbeat_at=NOW() "
            f"WHERE visual_run_id='{live_running_id}'"
        )
        psql_run(
            f"UPDATE tb_visual_pipeline_run SET run_status='SUCCESS', finished_at=NOW() "
            f"WHERE visual_run_id='{terminal_id}'"
        )

        data = api(
            "GET",
            "/visual-pipeline-ops/stuck-runs?pending_age_seconds=600&running_lock_grace_seconds=0&limit=100",
        )
        ids = {i["visual_run_id"]: i for i in data["items"]}
        assert old_pending_id in ids
        assert ids[old_pending_id]["reason"] == "PENDING_TOO_OLD"
        assert expired_running_id in ids
        assert ids[expired_running_id]["reason"] == "RUNNING_LOCK_EXPIRED"
        assert fresh_pending_id not in ids
        assert live_running_id not in ids
        assert terminal_id not in ids

        # terminal variants should not appear
        for status in ("FAILED", "PARTIAL", "CANCELLED"):
            psql_run(
                f"UPDATE tb_visual_pipeline_run SET run_status='{status}', finished_at=NOW() "
                f"WHERE visual_run_id='{terminal_id}'"
            )
            data2 = api(
                "GET",
                "/visual-pipeline-ops/stuck-runs?pending_age_seconds=600&limit=100",
            )
            assert terminal_id not in {i["visual_run_id"] for i in data2["items"]}
        print("  PASS stuck PENDING/expired RUNNING; terminals excluded")
    finally:
        archive_pipeline(pid)


def test_mark_failed_dry_run_and_apply() -> None:
    print("== mark-failed dry-run / apply ==")
    prev = os.environ.get("THERMOOPS_VP_SCHEDULE_ACTIVATION_ENABLED")
    os.environ["THERMOOPS_VP_SCHEDULE_ACTIVATION_ENABLED"] = "true"
    from app.core.config import get_settings

    get_settings.cache_clear()

    fixture = setup_compiled_materialized(f"S710-MARK-{uuid4().hex[:6]}")
    pid = fixture["pipeline_id"]
    try:

        async def _activate():
            from app.core.database import async_session
            from app.services.visual_pipeline.schedule_activation_service import (
                activate_schedule,
            )

            async with async_session() as db:
                return await activate_schedule(db, pid, {})

        act = _async_run(_activate())
        act_id = act["activation_id"]
        sync_before = _psql(
            f"SELECT current_sync_status FROM tb_pipeline_definition WHERE pipeline_id='{pid}'"
        )
        mat_before = _psql(
            f"SELECT materialization_status, activation FROM tb_visual_pipeline_materialization_result "
            f"WHERE materialization_result_id='{act['materialization_result_id']}'"
        )
        due_before = _psql(
            f"SELECT next_due_at FROM tb_visual_pipeline_schedule_activation "
            f"WHERE activation_id='{act_id}'"
        )

        old_pending_id = _create_pending(pid)["visual_run_id"]
        expired_running_id = _clone_run(old_pending_id)
        live_running_id = _clone_run(old_pending_id)
        terminal_id = _clone_run(old_pending_id)

        psql_run(
            f"UPDATE tb_visual_pipeline_run SET created_at = NOW() - INTERVAL '30 minutes' "
            f"WHERE visual_run_id='{old_pending_id}'"
        )
        psql_run(
            f"UPDATE tb_visual_pipeline_run SET run_status='RUNNING', started_at=NOW(), "
            f"claimed_by='ops-test', locked_until=NOW() - INTERVAL '5 minutes' "
            f"WHERE visual_run_id='{expired_running_id}'"
        )
        psql_run(
            f"UPDATE tb_visual_pipeline_run SET run_status='RUNNING', started_at=NOW(), "
            f"claimed_by='ops-test', locked_until=NOW() + INTERVAL '10 minutes' "
            f"WHERE visual_run_id='{live_running_id}'"
        )
        psql_run(
            f"UPDATE tb_visual_pipeline_run SET run_status='SUCCESS', finished_at=NOW() "
            f"WHERE visual_run_id='{terminal_id}'"
        )

        async def _dry():
            from app.core.database import async_session
            from app.services.visual_pipeline.ops_service import mark_stuck_runs_failed

            async with async_session() as db:
                return await mark_stuck_runs_failed(
                    db,
                    apply=False,
                    pending_age_seconds=600,
                    running_lock_grace_seconds=0,
                    limit=50,
                    reason="test dry-run",
                )

        dry = _async_run(_dry())
        assert dry["dry_run"] is True
        assert dry["updated_count"] == 0
        assert _psql(
            f"SELECT run_status FROM tb_visual_pipeline_run WHERE visual_run_id='{old_pending_id}'"
        ) == "PENDING"
        assert _psql(
            f"SELECT run_status FROM tb_visual_pipeline_run WHERE visual_run_id='{expired_running_id}'"
        ) == "RUNNING"

        async def _apply():
            from app.core.database import async_session
            from app.services.visual_pipeline.ops_service import mark_stuck_runs_failed

            async with async_session() as db:
                return await mark_stuck_runs_failed(
                    db,
                    apply=True,
                    pending_age_seconds=600,
                    running_lock_grace_seconds=0,
                    limit=50,
                    reason="test apply cleanup",
                )

        applied = _async_run(_apply())
        assert applied["apply"] is True
        updated_ids = {u["visual_run_id"] for u in applied["updated"]}
        assert old_pending_id in updated_ids
        assert expired_running_id in updated_ids
        assert live_running_id not in updated_ids
        assert terminal_id not in updated_ids

        assert (
            _psql(
                f"SELECT run_status FROM tb_visual_pipeline_run WHERE visual_run_id='{old_pending_id}'"
            )
            == "FAILED"
        )
        assert (
            _psql(
                f"SELECT run_status FROM tb_visual_pipeline_run WHERE visual_run_id='{expired_running_id}'"
            )
            == "FAILED"
        )
        assert (
            _psql(
                f"SELECT run_status FROM tb_visual_pipeline_run WHERE visual_run_id='{live_running_id}'"
            )
            == "RUNNING"
        )
        assert (
            _psql(
                f"SELECT run_status FROM tb_visual_pipeline_run WHERE visual_run_id='{terminal_id}'"
            )
            == "SUCCESS"
        )

        err = _psql(
            f"SELECT error_message FROM tb_visual_pipeline_run WHERE visual_run_id='{old_pending_id}'"
        )
        assert "Marked failed by ops cleanup" in err
        finished_at = _psql(
            f"SELECT finished_at FROM tb_visual_pipeline_run WHERE visual_run_id='{old_pending_id}'"
        )
        assert finished_at, finished_at
        locked_until = _psql(
            f"SELECT locked_until FROM tb_visual_pipeline_run WHERE visual_run_id='{expired_running_id}'"
        )
        assert locked_until in {"", "None", "null"} or locked_until is None or not locked_until
        issues = _psql(
            f"SELECT issues_json::text FROM tb_visual_pipeline_run WHERE visual_run_id='{old_pending_id}'"
        )
        assert "OPS_CLEANUP_MARKED_FAILED" in issues

        act_status = _psql(
            f"SELECT activation_status FROM tb_visual_pipeline_schedule_activation WHERE activation_id='{act_id}'"
        )
        assert act_status == "ACTIVE"
        due_after = _psql(
            f"SELECT next_due_at FROM tb_visual_pipeline_schedule_activation WHERE activation_id='{act_id}'"
        )
        assert due_after == due_before
        sync_after = _psql(
            f"SELECT current_sync_status FROM tb_pipeline_definition WHERE pipeline_id='{pid}'"
        )
        assert sync_after == sync_before
        mat_after = _psql(
            f"SELECT materialization_status, activation FROM tb_visual_pipeline_materialization_result "
            f"WHERE materialization_result_id='{act['materialization_result_id']}'"
        )
        assert mat_after == mat_before
        print("  PASS dry-run noop + apply eligible only + activation untouched")
    finally:
        if prev is None:
            os.environ.pop("THERMOOPS_VP_SCHEDULE_ACTIVATION_ENABLED", None)
        else:
            os.environ["THERMOOPS_VP_SCHEDULE_ACTIVATION_ENABLED"] = prev
        get_settings.cache_clear()
        archive_pipeline(pid)


def main() -> int:
    ensure_test_standard_datasets()
    test_ops_summary_api()
    test_stuck_runs_detection()
    test_mark_failed_dry_run_and_apply()
    print("\nAll visual pipeline ops tests PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
