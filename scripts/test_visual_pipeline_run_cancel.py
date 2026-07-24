#!/usr/bin/env python3
"""R11-S7-9 Visual Pipeline PENDING run cancel tests.

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
from test_visual_pipeline_run_worker import setup_compiled_materialized  # noqa: E402
from test_visual_pipeline_materialization import archive_pipeline  # noqa: E402


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


def test_cancel_pending_idempotent() -> None:
    print("== cancel PENDING ==")
    # Keep run PENDING: create via worker executor path without claiming.
    os.environ["THERMOOPS_VP_RUN_EXECUTOR"] = "worker"
    from app.core.config import get_settings

    get_settings.cache_clear()
    fixture = setup_compiled_materialized(f"S79-CANCEL-{uuid4().hex[:6]}")
    pid = fixture["pipeline_id"]
    try:

        async def _create_pending():
            from app.core.database import async_session
            from app.services.visual_pipeline.manual_run_service import create_manual_run

            async with async_session() as db:
                return await create_manual_run(
                    db, pid, {"mode": "MANUAL"}, executor="worker"
                )

        pending = _async_run(_create_pending())
        rid = pending["visual_run_id"]
        assert pending["run_status"] == "PENDING"

        cancelled = api("POST", f"/visual-pipelines/{pid}/runs/{rid}/cancel")
        assert cancelled["run_status"] == "CANCELLED"
        cancelled2 = api("POST", f"/visual-pipelines/{pid}/runs/{rid}/cancel")
        assert cancelled2["run_status"] == "CANCELLED"
        print(f"  PASS PENDING→CANCELLED + idempotent run={rid}")
    finally:
        archive_pipeline(pid)


def test_cancel_running_rejected() -> None:
    print("== cancel RUNNING rejected ==")
    fixture = setup_compiled_materialized(f"S79-CANRUN-{uuid4().hex[:6]}")
    pid = fixture["pipeline_id"]
    try:
        # Force a RUNNING row without executing
        async def _create_running():
            from app.core.database import async_session
            from app.services.visual_pipeline.manual_run_service import create_manual_run

            async with async_session() as db:
                row = await create_manual_run(
                    db, pid, {"mode": "MANUAL"}, executor="worker"
                )
                rid = row["visual_run_id"]
            return rid

        rid = _async_run(_create_running())
        psql_run(
            f"UPDATE tb_visual_pipeline_run SET run_status='RUNNING', "
            f"started_at=NOW() WHERE visual_run_id='{rid}'"
        )
        status_before = _psql(
            f"SELECT run_status FROM tb_visual_pipeline_run WHERE visual_run_id='{rid}'"
        )
        assert status_before == "RUNNING", status_before
        fail = api(
            "POST",
            f"/visual-pipelines/{pid}/runs/{rid}/cancel",
            expect_fail=True,
        )
        assert fail.get("_http_status") == 409, fail
        assert fail.get("detail") == "RUN_CANCEL_RUNNING_NOT_SUPPORTED", fail
        status = _psql(
            f"SELECT run_status FROM tb_visual_pipeline_run WHERE visual_run_id='{rid}'"
        )
        assert status == "RUNNING"
        print("  PASS RUNNING cancel 409")
    finally:
        archive_pipeline(pid)


def test_cancel_terminal_rejected() -> None:
    print("== cancel terminal rejected ==")
    fixture = setup_compiled_materialized(f"S79-CANTERM-{uuid4().hex[:6]}")
    pid = fixture["pipeline_id"]
    try:

        async def _create_pending():
            from app.core.database import async_session
            from app.services.visual_pipeline.manual_run_service import create_manual_run

            async with async_session() as db:
                return await create_manual_run(
                    db, pid, {"mode": "MANUAL"}, executor="worker"
                )

        pending = _async_run(_create_pending())
        rid = pending["visual_run_id"]
        for terminal in ("SUCCESS", "FAILED", "PARTIAL"):
            psql_run(
                f"UPDATE tb_visual_pipeline_run SET run_status='{terminal}', "
                f"finished_at=NOW() WHERE visual_run_id='{rid}'"
            )
            fail = api(
                "POST",
                f"/visual-pipelines/{pid}/runs/{rid}/cancel",
                expect_fail=True,
            )
            assert fail.get("_http_status") == 409, (terminal, fail)
            assert fail.get("detail") == "RUN_ALREADY_TERMINAL", (terminal, fail)
        print("  PASS SUCCESS/FAILED/PARTIAL cancel 409")
    finally:
        archive_pipeline(pid)


def test_cancel_does_not_touch_activation() -> None:
    print("== cancel leaves activation untouched ==")
    prev = os.environ.get("THERMOOPS_VP_SCHEDULE_ACTIVATION_ENABLED")
    os.environ["THERMOOPS_VP_SCHEDULE_ACTIVATION_ENABLED"] = "true"
    from app.core.config import get_settings

    get_settings.cache_clear()
    fixture = setup_compiled_materialized(f"S79-CANACT-{uuid4().hex[:6]}")
    pid = fixture["pipeline_id"]
    try:

        async def _setup():
            from app.core.database import async_session
            from app.services.visual_pipeline.manual_run_service import create_manual_run
            from app.services.visual_pipeline.schedule_activation_service import (
                activate_schedule,
            )

            async with async_session() as db:
                act = await activate_schedule(db, pid, {})
                pending = await create_manual_run(
                    db, pid, {"mode": "MANUAL"}, executor="worker"
                )
            return act, pending

        act, pending = _async_run(_setup())
        before_status = act["activation_status"]
        before_due = act.get("next_due_at")
        sync_before = _psql(
            f"SELECT current_sync_status FROM tb_pipeline_definition WHERE pipeline_id='{pid}'"
        )
        mat_before = _psql(
            f"SELECT materialization_status FROM tb_visual_pipeline_materialization_result "
            f"WHERE materialization_result_id='{act['materialization_result_id']}'"
        )

        cancelled = api(
            "POST",
            f"/visual-pipelines/{pid}/runs/{pending['visual_run_id']}/cancel",
        )
        assert cancelled["run_status"] == "CANCELLED"

        after_status = _psql(
            f"SELECT activation_status FROM tb_visual_pipeline_schedule_activation "
            f"WHERE activation_id='{act['activation_id']}'"
        )
        after_due = _psql(
            f"SELECT next_due_at FROM tb_visual_pipeline_schedule_activation "
            f"WHERE activation_id='{act['activation_id']}'"
        )
        sync_after = _psql(
            f"SELECT current_sync_status FROM tb_pipeline_definition WHERE pipeline_id='{pid}'"
        )
        mat_after = _psql(
            f"SELECT materialization_status FROM tb_visual_pipeline_materialization_result "
            f"WHERE materialization_result_id='{act['materialization_result_id']}'"
        )
        assert after_status == before_status == "ACTIVE"
        assert sync_after == sync_before
        assert mat_after == mat_before
        # next_due_at string compare via ISO-ish presence
        assert after_due
        assert before_due
        print("  PASS cancel does not mutate activation/sync/materialization")
    finally:
        if prev is None:
            os.environ.pop("THERMOOPS_VP_SCHEDULE_ACTIVATION_ENABLED", None)
        else:
            os.environ["THERMOOPS_VP_SCHEDULE_ACTIVATION_ENABLED"] = prev
        get_settings.cache_clear()
        archive_pipeline(pid)


def main() -> int:
    ensure_test_standard_datasets()
    test_cancel_pending_idempotent()
    test_cancel_running_rejected()
    test_cancel_terminal_rejected()
    test_cancel_does_not_touch_activation()
    print("\nAll run cancel tests PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
