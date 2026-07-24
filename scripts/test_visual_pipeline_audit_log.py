#!/usr/bin/env python3
"""R11-S7-13 Visual Pipeline Audit Log PoC tests.

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


def _count_event(event_type: str, *, pipeline_id: str | None = None) -> int:
    where = f"event_type='{event_type}'"
    if pipeline_id:
        where += f" AND pipeline_id='{pipeline_id}'"
    return int(_psql(f"SELECT COUNT(*) FROM tb_visual_pipeline_audit_log WHERE {where}") or "0")


def test_sanitize_audit_payload() -> None:
    print("== sanitize_audit_payload ==")
    from app.services.visual_pipeline.audit_service import sanitize_audit_payload

    raw = {
        "ok": 1,
        "password": "secret-value",
        "nested": {"api_key": "k", "token": "t", "safe": "v"},
        "list": [{"authorization": "Bearer x"}, "plain"],
        "credential_blob": "c",
    }
    out = sanitize_audit_payload(raw)
    assert out["ok"] == 1
    assert out["password"] == "***REDACTED***"
    assert out["nested"]["api_key"] == "***REDACTED***"
    assert out["nested"]["token"] == "***REDACTED***"
    assert out["nested"]["safe"] == "v"
    assert out["list"][0]["authorization"] == "***REDACTED***"
    assert out["list"][1] == "plain"
    assert out["credential_blob"] == "***REDACTED***"
    print("  PASS secret keys redacted recursively")


def test_activation_and_cancel_audit() -> None:
    print("== activation / cancel audit ==")
    from app.core.config import get_settings

    prev = os.environ.get("THERMOOPS_VP_SCHEDULE_ACTIVATION_ENABLED")
    os.environ["THERMOOPS_VP_SCHEDULE_ACTIVATION_ENABLED"] = "true"
    get_settings.cache_clear()

    fixture = setup_compiled_materialized(f"S713-AUD-{uuid4().hex[:6]}")
    pid = fixture["pipeline_id"]
    try:

        async def _activate():
            from app.core.database import async_session
            from app.services.visual_pipeline.schedule_activation_service import (
                activate_schedule,
                deactivate_schedule,
                pause_schedule,
                resume_schedule,
            )

            async with async_session() as db:
                act = await activate_schedule(db, pid, {})
                act_id = act["activation_id"]
                await pause_schedule(db, pid, act_id)
                await pause_schedule(db, pid, act_id)  # idempotent — no audit
                await resume_schedule(db, pid, act_id)
                await resume_schedule(db, pid, act_id)  # idempotent — no audit
                await deactivate_schedule(db, pid, act_id)
                await deactivate_schedule(db, pid, act_id)  # idempotent — no audit
                return act_id

        act_id = _async_run(_activate())
        assert _count_event("SCHEDULE_ACTIVATE", pipeline_id=pid) == 1
        assert _count_event("SCHEDULE_PAUSE", pipeline_id=pid) == 1
        assert _count_event("SCHEDULE_RESUME", pipeline_id=pid) == 1
        assert _count_event("SCHEDULE_DEACTIVATE", pipeline_id=pid) == 1

        async def _cancel_flow():
            from app.core.database import async_session
            from app.services.visual_pipeline.manual_run_service import (
                cancel_visual_pipeline_run,
                create_manual_run,
            )

            async with async_session() as db:
                run = await create_manual_run(db, pid, {"mode": "MANUAL"}, executor="worker")
                rid = run["visual_run_id"]
                await cancel_visual_pipeline_run(db, pid, rid)
                await cancel_visual_pipeline_run(db, pid, rid)  # idempotent
                return rid

        rid = _async_run(_cancel_flow())
        assert _count_event("RUN_CANCELLED", pipeline_id=pid) == 1
        assert (
            _psql(
                f"SELECT run_status FROM tb_visual_pipeline_run WHERE visual_run_id='{rid}'"
            )
            == "CANCELLED"
        )

        # list API minimized payload
        listed = api("GET", f"/visual-pipeline-ops/audit-logs?pipeline_id={pid}&limit=20")
        assert listed["total"] >= 5
        item = listed["items"][0]
        assert "audit_id" in item
        assert "event_type" in item
        assert "before_json" not in item
        assert "after_json" not in item
        assert "metadata_json" not in item

        detail = api("GET", f"/visual-pipeline-ops/audit-logs/{item['audit_id']}")
        assert "before_json" in detail or detail.get("before_json") is None
        assert "after_json" in detail or detail.get("after_json") is None
        assert detail["audit_id"] == item["audit_id"]

        missing = api(
            "GET",
            "/visual-pipeline-ops/audit-logs/VPAU-NOTEXIST",
            expect_fail=True,
        )
        assert missing.get("_http_status") == 404

        actor = _psql(
            f"SELECT actor_type || '/' || actor_id FROM tb_visual_pipeline_audit_log "
            f"WHERE pipeline_id='{pid}' AND event_type='SCHEDULE_ACTIVATE' LIMIT 1"
        )
        assert actor == "USER/mock_admin"
        print(f"  PASS activation/cancel audits act={act_id} run={rid}")
    finally:
        if prev is None:
            os.environ.pop("THERMOOPS_VP_SCHEDULE_ACTIVATION_ENABLED", None)
        else:
            os.environ["THERMOOPS_VP_SCHEDULE_ACTIVATION_ENABLED"] = prev
        get_settings.cache_clear()
        archive_pipeline(pid)


def test_ops_mark_failed_audit() -> None:
    print("== ops mark-failed audit (dry-run + apply) ==")
    from app.core.config import get_settings

    prev = os.environ.get("THERMOOPS_VP_SCHEDULE_ACTIVATION_ENABLED")
    os.environ["THERMOOPS_VP_SCHEDULE_ACTIVATION_ENABLED"] = "true"
    get_settings.cache_clear()

    fixture = setup_compiled_materialized(f"S713-OPS-{uuid4().hex[:6]}")
    pid = fixture["pipeline_id"]
    try:

        async def _pending():
            from app.core.database import async_session
            from app.services.visual_pipeline.manual_run_service import create_manual_run

            async with async_session() as db:
                return await create_manual_run(
                    db, pid, {"mode": "MANUAL"}, executor="worker"
                )

        pending = _async_run(_pending())
        rid = pending["visual_run_id"]
        psql_run(
            f"UPDATE tb_visual_pipeline_run SET created_at = NOW() - INTERVAL '30 minutes' "
            f"WHERE visual_run_id='{rid}'"
        )

        dry_before = _count_event("OPS_MARK_FAILED_DRY_RUN")
        apply_before = _count_event("OPS_MARK_FAILED_APPLY")
        run_before = _count_event("RUN_MARK_FAILED_BY_OPS", pipeline_id=pid)

        async def _dry():
            from app.core.database import async_session
            from app.services.visual_pipeline.ops_service import mark_stuck_runs_failed

            async with async_session() as db:
                return await mark_stuck_runs_failed(
                    db,
                    apply=False,
                    pending_age_seconds=600,
                    reason="audit dry-run",
                )

        dry = _async_run(_dry())
        assert dry["dry_run"] is True
        assert _psql(
            f"SELECT run_status FROM tb_visual_pipeline_run WHERE visual_run_id='{rid}'"
        ) == "PENDING"
        assert _count_event("OPS_MARK_FAILED_DRY_RUN") == dry_before + 1

        async def _apply():
            from app.core.database import async_session
            from app.services.visual_pipeline.ops_service import mark_stuck_runs_failed

            async with async_session() as db:
                return await mark_stuck_runs_failed(
                    db,
                    apply=True,
                    pending_age_seconds=600,
                    reason="audit apply",
                )

        applied = _async_run(_apply())
        assert applied["updated_count"] >= 1
        assert _psql(
            f"SELECT run_status FROM tb_visual_pipeline_run WHERE visual_run_id='{rid}'"
        ) == "FAILED"
        assert _count_event("OPS_MARK_FAILED_APPLY") == apply_before + 1
        assert _count_event("RUN_MARK_FAILED_BY_OPS", pipeline_id=pid) >= run_before + 1

        cli_actor = _psql(
            "SELECT actor_type || '/' || actor_id FROM tb_visual_pipeline_audit_log "
            "WHERE event_type='OPS_MARK_FAILED_DRY_RUN' ORDER BY created_at DESC LIMIT 1"
        )
        assert cli_actor == "CLI/cli"
        print("  PASS dry-run + apply audit rows")
    finally:
        if prev is None:
            os.environ.pop("THERMOOPS_VP_SCHEDULE_ACTIVATION_ENABLED", None)
        else:
            os.environ["THERMOOPS_VP_SCHEDULE_ACTIVATION_ENABLED"] = prev
        get_settings.cache_clear()
        archive_pipeline(pid)


def test_worker_active_run_skip_audit() -> None:
    print("== worker ACTIVE_RUN_EXISTS skip audit ==")
    from app.core.config import get_settings

    prev_act = os.environ.get("THERMOOPS_VP_SCHEDULE_ACTIVATION_ENABLED")
    prev_sw = os.environ.get("THERMOOPS_VP_SCHEDULE_WORKER_ENABLED")
    os.environ["THERMOOPS_VP_SCHEDULE_ACTIVATION_ENABLED"] = "true"
    os.environ["THERMOOPS_VP_SCHEDULE_WORKER_ENABLED"] = "true"
    get_settings.cache_clear()

    fixture = setup_compiled_materialized(f"S713-SKP-{uuid4().hex[:6]}")
    pid = fixture["pipeline_id"]
    try:

        async def _setup():
            from app.core.database import async_session
            from app.services.visual_pipeline.manual_run_service import create_manual_run
            from app.services.visual_pipeline.schedule_activation_service import (
                activate_schedule,
            )
            from app.models.entities import VisualPipelineScheduleActivation
            from sqlalchemy import select
            from app.core.time import utc_now
            from datetime import timedelta

            async with async_session() as db:
                act = await activate_schedule(db, pid, {})
                await create_manual_run(db, pid, {"mode": "MANUAL"}, executor="worker")
                row = (
                    await db.execute(
                        select(VisualPipelineScheduleActivation).where(
                            VisualPipelineScheduleActivation.activation_id
                            == act["activation_id"]
                        )
                    )
                ).scalar_one()
                row.next_due_at = utc_now() - timedelta(minutes=1)
                await db.commit()
                return act["activation_id"]

        act_id = _async_run(_setup())
        before = _count_event("SCHEDULE_WORKER_SKIPPED_ACTIVE_RUN", pipeline_id=pid)

        async def _enqueue():
            from app.core.database import async_session
            from app.services.visual_pipeline.schedule_worker_service import (
                enqueue_due_activation,
            )
            from app.models.entities import VisualPipelineScheduleActivation
            from sqlalchemy import select

            async with async_session() as db:
                row = (
                    await db.execute(
                        select(VisualPipelineScheduleActivation).where(
                            VisualPipelineScheduleActivation.activation_id == act_id
                        )
                    )
                ).scalar_one()
                return await enqueue_due_activation(db, row, worker_id="audit-test-worker")

        result = _async_run(_enqueue())
        assert result["reason"] == "skipped_active_run"
        assert _count_event("SCHEDULE_WORKER_SKIPPED_ACTIVE_RUN", pipeline_id=pid) == before + 1
        actor = _psql(
            f"SELECT actor_type || '/' || actor_id FROM tb_visual_pipeline_audit_log "
            f"WHERE pipeline_id='{pid}' AND event_type='SCHEDULE_WORKER_SKIPPED_ACTIVE_RUN' "
            f"ORDER BY created_at DESC LIMIT 1"
        )
        assert actor == "WORKER/audit-test-worker"
        print("  PASS ACTIVE_RUN_EXISTS worker audit")
    finally:
        if prev_act is None:
            os.environ.pop("THERMOOPS_VP_SCHEDULE_ACTIVATION_ENABLED", None)
        else:
            os.environ["THERMOOPS_VP_SCHEDULE_ACTIVATION_ENABLED"] = prev_act
        if prev_sw is None:
            os.environ.pop("THERMOOPS_VP_SCHEDULE_WORKER_ENABLED", None)
        else:
            os.environ["THERMOOPS_VP_SCHEDULE_WORKER_ENABLED"] = prev_sw
        get_settings.cache_clear()
        archive_pipeline(pid)


def main() -> int:
    ensure_test_standard_datasets()
    test_sanitize_audit_payload()
    test_activation_and_cancel_audit()
    test_ops_mark_failed_audit()
    test_worker_active_run_skip_audit()
    print("\nAll visual pipeline audit log tests PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
