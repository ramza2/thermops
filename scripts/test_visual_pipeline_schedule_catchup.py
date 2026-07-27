#!/usr/bin/env python3
"""R11-S8-6 Visual Pipeline Schedule Catch-up — manual enqueue PoC tests.

Uses sample-external fixtures. Not in quick group by default.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
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


def _psql_exec(sql: str) -> None:
    psql_run(sql)


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
        raise RuntimeError(f"HTTP {exc.code} {method} {path}: {detail}") from None
    if expect_status is not None and status != expect_status:
        raise AssertionError(f"expected HTTP {expect_status}, got {status} for {method} {path}")
    if not payload.get("success"):
        raise RuntimeError(f"API failed {method} {path}: {payload}")
    data_out = payload["data"]
    if isinstance(data_out, dict):
        data_out = dict(data_out)
        data_out["_http_status"] = status
    return data_out


def _async_run(coro):
    async def _wrapped():
        from app.core.database import engine

        try:
            return await coro
        finally:
            await engine.dispose()

    return asyncio.run(_wrapped())


def _utc_naive_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None, microsecond=0)


def _deactivate(pipeline_id: str, activation_id: str) -> None:
    async def _inner():
        from app.core.database import async_session
        from app.services.visual_pipeline.schedule_activation_service import deactivate_schedule

        async with async_session() as db:
            try:
                await deactivate_schedule(db, pipeline_id, activation_id)
            except Exception:
                pass

    _async_run(_inner())


def _enable_activation() -> str | None:
    from app.core.config import get_settings

    prev = os.environ.get("THERMOOPS_VP_SCHEDULE_ACTIVATION_ENABLED")
    os.environ["THERMOOPS_VP_SCHEDULE_ACTIVATION_ENABLED"] = "true"
    os.environ.setdefault("THERMOOPS_VP_SCHEDULE_CATCHUP_ENABLED", "true")
    get_settings.cache_clear()
    return prev


def _restore_activation(prev: str | None) -> None:
    from app.core.config import get_settings

    if prev is None:
        os.environ.pop("THERMOOPS_VP_SCHEDULE_ACTIVATION_ENABLED", None)
    else:
        os.environ["THERMOOPS_VP_SCHEDULE_ACTIVATION_ENABLED"] = prev
    get_settings.cache_clear()


def _activate(pipeline_id: str) -> dict:
    async def _inner():
        from app.core.database import async_session
        from app.services.visual_pipeline.schedule_activation_service import activate_schedule

        async with async_session() as db:
            return await activate_schedule(db, pipeline_id, {})

    return _async_run(_inner())


def _seed_missed(
    activation_id: str,
    *,
    due_at: datetime,
    skip_reason: str = "ACTIVE_RUN_EXISTS",
    missed_count: int = 1,
) -> None:
    due_sql = due_at.replace(microsecond=0).isoformat(timespec="seconds")
    _psql_exec(
        "UPDATE tb_visual_pipeline_schedule_activation SET "
        f"last_due_at='{due_sql}'::timestamp, "
        f"last_skip_at='{due_sql}'::timestamp, "
        f"last_skip_reason='{skip_reason}', "
        f"missed_count={int(missed_count)} "
        f"WHERE activation_id='{activation_id}'"
    )


def test_migration_columns() -> None:
    print("== catch-up columns ==")
    for name in (
        "catchup_of_activation_id",
        "catchup_for_scheduled_at",
        "catchup_reason",
        "catchup_requested_by",
        "catchup_requested_at",
    ):
        col = _psql(
            "SELECT column_name FROM information_schema.columns "
            f"WHERE table_name='tb_visual_pipeline_run' AND column_name='{name}'"
        )
        assert col == name, name
    print("  PASS columns present")


def test_candidate_and_enqueue() -> None:
    print("== candidate + enqueue ==")
    prev = _enable_activation()
    fixture = setup_compiled_materialized(f"S86-CU-{uuid4().hex[:6]}")
    pid = fixture["pipeline_id"]
    aid = None
    try:
        act = _activate(pid)
        aid = act["activation_id"]
        next_due_before = _psql(
            f"SELECT COALESCE(next_due_at::text,'') FROM tb_visual_pipeline_schedule_activation "
            f"WHERE activation_id='{aid}'"
        )
        due = _utc_naive_now() - timedelta(hours=1)
        _seed_missed(aid, due_at=due, skip_reason="ACTIVE_RUN_EXISTS")

        cand = api(
            "GET",
            f"/visual-pipelines/{pid}/schedule-activations/{aid}/catch-up-candidates",
        )
        assert cand["eligible"] is True, cand
        assert cand.get("candidate_scheduled_at")
        assert cand.get("last_skip_reason") == "ACTIVE_RUN_EXISTS"

        bad_confirm = api(
            "POST",
            f"/visual-pipelines/{pid}/schedule-activations/{aid}/catch-up",
            {
                "candidate_scheduled_at": cand["candidate_scheduled_at"],
                "reason": "operator catch-up after active run skip",
                "confirm_activation_id": "VPA-WRONG",
            },
            expect_fail=True,
        )
        assert bad_confirm.get("detail") == "SCHEDULE_CATCHUP_CONFIRM_MISMATCH", bad_confirm

        short = api(
            "POST",
            f"/visual-pipelines/{pid}/schedule-activations/{aid}/catch-up",
            {
                "candidate_scheduled_at": cand["candidate_scheduled_at"],
                "reason": "abc",
                "confirm_activation_id": aid,
            },
            expect_fail=True,
        )
        assert short.get("_http_status") in {400, 422}, short
        detail = short.get("detail")
        if isinstance(detail, str):
            assert detail == "SCHEDULE_CATCHUP_REASON_REQUIRED", short
        # pydantic may reject with 422 before service validation

        enq = api(
            "POST",
            f"/visual-pipelines/{pid}/schedule-activations/{aid}/catch-up",
            {
                "candidate_scheduled_at": cand["candidate_scheduled_at"],
                "reason": "operator catch-up after active run skip",
                "confirm_activation_id": aid,
            },
            expect_status=202,
        )
        assert enq["run_status"] == "PENDING", enq
        rid = enq["catchup_visual_run_id"]
        assert rid.startswith("VPR-")
        assert enq.get("catchup_for_scheduled_at")

        row = api("GET", f"/visual-pipelines/{pid}/runs/{rid}")
        assert row["run_status"] == "PENDING"
        assert row.get("catchup_of_activation_id") == aid
        assert row.get("catchup_reason")
        assert str(row.get("dedup_key") or "").startswith("CATCHUP:")
        assert row.get("mode") == "SCHEDULED"

        next_due_after = _psql(
            f"SELECT COALESCE(next_due_at::text,'') FROM tb_visual_pipeline_schedule_activation "
            f"WHERE activation_id='{aid}'"
        )
        assert next_due_after == next_due_before, (next_due_before, next_due_after)

        # duplicate
        dup = api(
            "POST",
            f"/visual-pipelines/{pid}/schedule-activations/{aid}/catch-up",
            {
                "candidate_scheduled_at": cand["candidate_scheduled_at"],
                "reason": "duplicate should fail now",
                "confirm_activation_id": aid,
            },
            expect_fail=True,
        )
        assert dup.get("detail") in {
            "SCHEDULE_CATCHUP_DUPLICATE_RUN_EXISTS",
            "SCHEDULE_CATCHUP_ACTIVE_RUN_EXISTS",
            "SCHEDULE_CATCHUP_NOT_ELIGIBLE",
        }, dup

        audit_n = int(
            _psql(
                "SELECT COUNT(*)::text FROM tb_visual_pipeline_audit_log "
                f"WHERE pipeline_id='{pid}' AND event_type='SCHEDULE_CATCHUP_ENQUEUED' "
                f"AND visual_run_id='{rid}'"
            )
            or "0"
        )
        assert audit_n == 1
        events = _psql(
            "SELECT string_agg(event_type, ',' ORDER BY created_at, event_id) "
            f"FROM tb_visual_pipeline_run_event WHERE visual_run_id='{rid}'"
        )
        assert "RUN_CREATED" in events
        assert "SCHEDULE_CATCHUP_ENQUEUED" in events
        print(f"  PASS enqueue rid={rid}")
    finally:
        if aid:
            try:
                _deactivate(pid, aid)
            except Exception:
                pass
        archive_pipeline(pid)
        _restore_activation(prev)


def test_inactive_and_window() -> None:
    print("== inactive + window ==")
    prev = _enable_activation()
    fixture = setup_compiled_materialized(f"S86-WIN-{uuid4().hex[:6]}")
    pid = fixture["pipeline_id"]
    aid = None
    try:
        act = _activate(pid)
        aid = act["activation_id"]
        due = _utc_naive_now() - timedelta(hours=48)
        _seed_missed(aid, due_at=due, skip_reason="ACTIVE_RUN_EXISTS")
        cand = api(
            "GET",
            f"/visual-pipelines/{pid}/schedule-activations/{aid}/catch-up-candidates",
        )
        assert cand["eligible"] is True, cand
        win = api(
            "POST",
            f"/visual-pipelines/{pid}/schedule-activations/{aid}/catch-up",
            {
                "candidate_scheduled_at": cand["candidate_scheduled_at"],
                "reason": "should exceed catch-up window hours",
                "confirm_activation_id": aid,
            },
            expect_fail=True,
        )
        assert win.get("detail") == "SCHEDULE_CATCHUP_WINDOW_EXCEEDED", win

        # fresh due within window, then INACTIVE
        due2 = _utc_naive_now() - timedelta(hours=1)
        _seed_missed(aid, due_at=due2, skip_reason="STALE_OR_INVALID")
        _psql_exec(
            f"UPDATE tb_visual_pipeline_schedule_activation SET activation_status='INACTIVE' "
            f"WHERE activation_id='{aid}'"
        )
        cand2 = api(
            "GET",
            f"/visual-pipelines/{pid}/schedule-activations/{aid}/catch-up-candidates",
        )
        assert cand2["eligible"] is False, cand2
        print("  PASS window + inactive")
    finally:
        if aid:
            try:
                _deactivate(pid, aid)
            except Exception:
                pass
        archive_pipeline(pid)
        _restore_activation(prev)


def test_no_candidate() -> None:
    print("== no candidate ==")
    prev = _enable_activation()
    fixture = setup_compiled_materialized(f"S86-NO-{uuid4().hex[:6]}")
    pid = fixture["pipeline_id"]
    aid = None
    try:
        act = _activate(pid)
        aid = act["activation_id"]
        cand = api(
            "GET",
            f"/visual-pipelines/{pid}/schedule-activations/{aid}/catch-up-candidates",
        )
        assert cand["eligible"] is False, cand
        print("  PASS no candidate")
    finally:
        if aid:
            try:
                _deactivate(pid, aid)
            except Exception:
                pass
        archive_pipeline(pid)
        _restore_activation(prev)


def test_worker_can_execute_catchup() -> None:
    print("== worker executes catch-up run ==")
    prev = _enable_activation()
    os.environ["THERMOOPS_VP_RUN_WORKER_ENABLED"] = "true"
    from app.core.config import get_settings

    get_settings.cache_clear()
    fixture = setup_compiled_materialized(f"S86-WK-{uuid4().hex[:6]}")
    pid = fixture["pipeline_id"]
    aid = None
    try:
        act = _activate(pid)
        aid = act["activation_id"]
        due = _utc_naive_now() - timedelta(hours=1)
        _seed_missed(aid, due_at=due, skip_reason="ACTIVE_RUN_EXISTS")
        cand = api(
            "GET",
            f"/visual-pipelines/{pid}/schedule-activations/{aid}/catch-up-candidates",
        )
        enq = api(
            "POST",
            f"/visual-pipelines/{pid}/schedule-activations/{aid}/catch-up",
            {
                "candidate_scheduled_at": cand["candidate_scheduled_at"],
                "reason": "catch-up worker execution smoke",
                "confirm_activation_id": aid,
            },
            expect_status=202,
        )
        rid = enq["catchup_visual_run_id"]

        async def _claim_and_execute() -> dict:
            from sqlalchemy import text

            from app.core.database import async_session
            from app.services.visual_pipeline.run_worker_service import (
                execute_claimed_visual_pipeline_run,
            )

            wid = f"test-catchup-{uuid4().hex[:6]}"
            async with async_session() as db:
                result = await db.execute(
                    text(
                        """
                        UPDATE tb_visual_pipeline_run
                        SET run_status = 'RUNNING',
                            claimed_at = NOW(),
                            claimed_by = :worker_id,
                            locked_until = NOW() + make_interval(secs => 120),
                            heartbeat_at = NOW(),
                            attempt_count = COALESCE(attempt_count, 0) + 1,
                            started_at = COALESCE(started_at, NOW())
                        WHERE visual_run_id = :visual_run_id
                          AND run_status = 'PENDING'
                        RETURNING visual_run_id
                        """
                    ),
                    {"worker_id": wid, "visual_run_id": rid},
                )
                claimed = result.fetchone()
                await db.commit()
                if claimed is None:
                    raise AssertionError(f"failed to claim catch-up run {rid}")
            async with async_session() as db:
                return await execute_claimed_visual_pipeline_run(db, rid, worker_id=wid)

        _async_run(_claim_and_execute())
        status = _psql(
            f"SELECT run_status FROM tb_visual_pipeline_run WHERE visual_run_id='{rid}'"
        )
        assert status in {"SUCCESS", "PARTIAL", "FAILED", "CANCELLED"}, status
        print(f"  PASS worker executed status={status}")
    finally:
        if aid:
            try:
                _deactivate(pid, aid)
            except Exception:
                pass
        archive_pipeline(pid)
        _restore_activation(prev)
        os.environ.pop("THERMOOPS_VP_RUN_WORKER_ENABLED", None)
        get_settings.cache_clear()


def main() -> None:
    ensure_test_standard_datasets()
    test_migration_columns()
    test_no_candidate()
    test_candidate_and_enqueue()
    test_inactive_and_window()
    test_worker_can_execute_catchup()
    print("\nAll schedule catch-up tests PASSED")


if __name__ == "__main__":
    main()
