#!/usr/bin/env python3
"""R11-S7-8 Visual Pipeline Schedule Activation PoC tests.

Uses sample-external/heat-demand — no operational external APIs.
quick regression group: NOT included.
"""

from __future__ import annotations

import asyncio
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
from test_visual_pipeline_run_worker import setup_compiled_materialized  # noqa: E402
from test_visual_pipeline_materialization import archive_pipeline, snapshot_side_effects  # noqa: E402


def _psql(sql: str) -> str:
    return str(psql_scalar(sql) or "").strip()


def api(
    method: str,
    path: str,
    body: dict | None = None,
    *,
    expect_fail: bool = False,
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


def _async_run(coro):
    async def _wrapped():
        from app.core.database import engine

        try:
            return await coro
        finally:
            await engine.dispose()

    return asyncio.run(_wrapped())


def _with_activation_enabled(enabled: bool = True):
    from app.core.config import get_settings

    prev = os.environ.get("THERMOOPS_VP_SCHEDULE_ACTIVATION_ENABLED")
    os.environ["THERMOOPS_VP_SCHEDULE_ACTIVATION_ENABLED"] = "true" if enabled else "false"
    get_settings.cache_clear()
    return prev


def _restore_activation_enabled(prev: str | None) -> None:
    from app.core.config import get_settings

    if prev is None:
        os.environ.pop("THERMOOPS_VP_SCHEDULE_ACTIVATION_ENABLED", None)
    else:
        os.environ["THERMOOPS_VP_SCHEDULE_ACTIVATION_ENABLED"] = prev
    get_settings.cache_clear()


def test_migration_idempotent() -> None:
    print("== migration re-run ==")
    r1 = subprocess.run(
        [sys.executable, str(_SCRIPTS / "apply_dev_migrations.py")],
        cwd=str(_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert r1.returncode == 0, r1.stderr
    r2 = subprocess.run(
        [sys.executable, str(_SCRIPTS / "apply_dev_migrations.py")],
        cwd=str(_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert r2.returncode == 0, r2.stderr
    assert _psql(
        "SELECT COUNT(*) FROM information_schema.tables "
        "WHERE table_name='tb_visual_pipeline_schedule_activation'"
    ) == "1"
    for col in ("activation_id", "r10_schedule_id", "scheduled_for", "triggered_at", "dedup_key"):
        assert (
            _psql(
                "SELECT COUNT(*) FROM information_schema.columns "
                f"WHERE table_name='tb_visual_pipeline_run' AND column_name='{col}'"
            )
            == "1"
        ), col
    assert (
        _psql(
            "SELECT COUNT(*) FROM pg_indexes WHERE indexname='ux_vp_run_dedup_key'"
        )
        == "1"
    )
    assert (
        _psql(
            "SELECT COUNT(*) FROM pg_indexes WHERE indexname='ux_vp_schedule_activation_pipeline_active'"
        )
        == "1"
    )
    print("  PASS migration + columns/indexes")


def test_disabled_flag() -> None:
    print("== activation disabled ==")
    prev = _with_activation_enabled(False)
    try:
        from app.services.visual_pipeline.schedule_activation_service import (
            ActivationPreconditionError,
            assert_schedule_activation_enabled,
        )

        try:
            assert_schedule_activation_enabled()
            raise AssertionError("expected SCHEDULE_ACTIVATION_DISABLED")
        except ActivationPreconditionError as exc:
            assert exc.code == "SCHEDULE_ACTIVATION_DISABLED"
        print("  PASS disabled flag")
    finally:
        _restore_activation_enabled(prev)


def test_activate_deactivate_success() -> None:
    print("== activate / deactivate ==")
    prev = _with_activation_enabled(True)
    fixture = setup_compiled_materialized(f"S78-ACT-{uuid4().hex[:6]}")
    pid = fixture["pipeline_id"]
    mat = fixture["materialization"]
    schedule_id = str((mat.get("objects") or {}).get("schedule_id") or "")
    assert schedule_id, "expected materialized schedule_id"
    before = snapshot_side_effects()
    try:

        async def _run():
            from app.core.database import async_session
            from app.services.visual_pipeline.schedule_activation_service import (
                ActivationPreconditionError,
                activate_schedule,
                deactivate_schedule,
                get_current_activation,
            )

            async with async_session() as db:
                act = await activate_schedule(db, pid, {})
                assert act["activation_status"] == "ACTIVE"
                assert act["r10_schedule_id"] == schedule_id
                assert act["next_due_at"]
                assert act["trigger_count"] == 0
                act_id = act["activation_id"]

                # already active
                try:
                    await activate_schedule(db, pid, {})
                    raise AssertionError("expected ACTIVE_ACTIVATION_EXISTS")
                except ActivationPreconditionError as exc:
                    assert exc.code == "ACTIVE_ACTIVATION_EXISTS"

                cur = await get_current_activation(db, pid)
                assert cur and cur["activation_id"] == act_id

                deact = await deactivate_schedule(db, pid, act_id)
                assert deact["activation_status"] == "INACTIVE"
                # idempotent
                deact2 = await deactivate_schedule(db, pid, act_id)
                assert deact2["activation_status"] == "INACTIVE"
                return act_id

        act_id = _async_run(_run())

        mirror = _psql(
            "SELECT activation FROM tb_visual_pipeline_materialization_result "
            f"WHERE materialization_result_id='{mat['materialization_result_id']}'"
        )
        assert mirror == "INACTIVE", mirror
        active_yn = _psql(
            f"SELECT active_yn::text FROM tb_data_load_schedule WHERE schedule_id='{schedule_id}'"
        )
        assert active_yn == "false", active_yn
        runs = int(
            _psql(
                f"SELECT COUNT(*) FROM tb_visual_pipeline_run WHERE pipeline_id='{pid}'"
            )
            or "0"
        )
        assert runs == 0, "activation must not create run rows"
        after = snapshot_side_effects()
        # call_log / load_run should not grow from activation alone
        assert after["tb_api_connector_call_log"] == before["tb_api_connector_call_log"]
        assert after["tb_api_connector_load_run"] == before["tb_api_connector_load_run"]
        print(f"  PASS activate/deactivate activation_id={act_id}")
    finally:
        _restore_activation_enabled(prev)
        archive_pipeline(pid)


def test_precondition_stale() -> None:
    print("== precondition stale ==")
    prev = _with_activation_enabled(True)
    fixture = setup_compiled_materialized(f"S78-STALE-{uuid4().hex[:6]}")
    pid = fixture["pipeline_id"]
    try:
        # Force STALE by changing sync status
        psql_run(
            f"UPDATE tb_pipeline_definition SET current_sync_status='STALE' "
            f"WHERE pipeline_id='{pid}'"
        )

        async def _run():
            from app.core.database import async_session
            from app.services.visual_pipeline.schedule_activation_service import (
                ActivationPreconditionError,
                activate_schedule,
            )

            async with async_session() as db:
                try:
                    await activate_schedule(db, pid, {})
                    raise AssertionError("expected PIPELINE_STALE")
                except ActivationPreconditionError as exc:
                    assert exc.code == "PIPELINE_STALE"

        _async_run(_run())
        print("  PASS PIPELINE_STALE")
    finally:
        _restore_activation_enabled(prev)
        archive_pipeline(pid)


def test_manual_run_does_not_change_activation() -> None:
    print("== manual run leaves activation ==")
    prev = _with_activation_enabled(True)
    # Prefer background_tasks so Manual Run completes without separate worker.
    os.environ["THERMOOPS_VP_RUN_EXECUTOR"] = "background_tasks"
    from app.core.config import get_settings

    get_settings.cache_clear()
    fixture = setup_compiled_materialized(f"S78-MAN-{uuid4().hex[:6]}")
    pid = fixture["pipeline_id"]
    try:

        async def _activate():
            from app.core.database import async_session
            from app.services.visual_pipeline.schedule_activation_service import activate_schedule

            async with async_session() as db:
                return await activate_schedule(db, pid, {})

        act = _async_run(_activate())
        run = api("POST", f"/visual-pipelines/{pid}/runs", {"mode": "MANUAL"})
        assert run.get("mode") == "MANUAL"
        # poll briefly
        import time

        terminal = {"SUCCESS", "FAILED", "PARTIAL"}
        status = run.get("run_status")
        rid = run["visual_run_id"]
        for _ in range(60):
            if status in terminal:
                break
            time.sleep(1)
            detail = api("GET", f"/visual-pipelines/{pid}/runs/{rid}")
            status = detail.get("run_status")
        assert status in terminal, status
        cur = api("GET", f"/visual-pipelines/{pid}/schedule-activations/current")
        assert cur and cur.get("activation_status") == "ACTIVE"
        assert cur.get("activation_id") == act["activation_id"]
        print("  PASS manual run does not deactivate")
    finally:
        _restore_activation_enabled(prev)
        archive_pipeline(pid)


def main() -> int:
    ensure_test_standard_datasets()
    test_migration_idempotent()
    test_disabled_flag()
    test_activate_deactivate_success()
    test_precondition_stale()
    test_manual_run_does_not_change_activation()
    print("\nAll schedule activation tests PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
