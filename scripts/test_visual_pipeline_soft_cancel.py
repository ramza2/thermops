#!/usr/bin/env python3
"""R11-S8-5 Visual Pipeline soft-cancel — PENDING immediate + RUNNING cooperative.

Uses sample-external fixtures. Not in quick group by default.
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


def _psql_exec(sql: str) -> None:
    psql_run(sql)


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
        raise RuntimeError(f"HTTP {exc.code} {method} {path}: {detail}") from None
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


def _create_pending(pipeline_id: str) -> str:
    async def _inner():
        from app.core.database import async_session
        from app.services.visual_pipeline.manual_run_service import create_manual_run

        async with async_session() as db:
            row = await create_manual_run(
                db, pipeline_id, {"mode": "MANUAL"}, executor="worker"
            )
            return row["visual_run_id"]

    return _async_run(_inner())


def _force_running(visual_run_id: str) -> None:
    _psql_exec(
        f"UPDATE tb_visual_pipeline_run SET run_status='RUNNING', "
        f"started_at=NOW(), cancel_requested_at=NULL, cancel_requested_by=NULL, "
        f"cancel_reason=NULL, cancel_acknowledged_at=NULL "
        f"WHERE visual_run_id='{visual_run_id}'"
    )


def _audit_count(event_type: str, *, pipeline_id: str, visual_run_id: str | None = None) -> int:
    extra = f" AND visual_run_id='{visual_run_id}'" if visual_run_id else ""
    return int(
        _psql(
            "SELECT COUNT(*)::text FROM tb_visual_pipeline_audit_log "
            f"WHERE pipeline_id='{pipeline_id}' AND event_type='{event_type}'{extra}"
        )
        or "0"
    )


def _event_types(visual_run_id: str) -> list[str]:
    raw = _psql(
        "SELECT string_agg(event_type, ',' ORDER BY created_at, event_id) "
        f"FROM tb_visual_pipeline_run_event WHERE visual_run_id='{visual_run_id}'"
    )
    return [x for x in raw.split(",") if x] if raw else []


def test_migration_columns() -> None:
    print("== soft-cancel columns ==")
    cols = {
        _psql(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name='tb_visual_pipeline_run' "
            f"AND column_name='{name}'"
        )
        for name in (
            "cancel_requested_at",
            "cancel_requested_by",
            "cancel_reason",
            "cancel_acknowledged_at",
        )
    }
    assert cols == {
        "cancel_requested_at",
        "cancel_requested_by",
        "cancel_reason",
        "cancel_acknowledged_at",
    }, cols
    print("  PASS columns present")


def test_pending_immediate_cancel() -> None:
    print("== PENDING immediate cancel ==")
    os.environ["THERMOOPS_VP_RUN_EXECUTOR"] = "worker"
    from app.core.config import get_settings

    get_settings.cache_clear()
    fixture = setup_compiled_materialized(f"S85-PEND-{uuid4().hex[:6]}")
    pid = fixture["pipeline_id"]
    try:
        rid = _create_pending(pid)
        out = api("POST", f"/visual-pipelines/{pid}/runs/{rid}/cancel", {})
        assert out["run_status"] == "CANCELLED", out
        assert out.get("cancel_requested") is True
        assert out.get("cancel_acknowledged_at")
        detail = api("GET", f"/visual-pipelines/{pid}/runs/{rid}")
        assert detail["run_status"] == "CANCELLED"
        assert detail.get("cancel_requested_at")
        assert detail.get("cancel_acknowledged_at")
        assert _audit_count("RUN_CANCELLED", pipeline_id=pid, visual_run_id=rid) == 1
        assert "RUN_CANCELLED" in _event_types(rid)
        # idempotent
        out2 = api("POST", f"/visual-pipelines/{pid}/runs/{rid}/cancel", {})
        assert out2["run_status"] == "CANCELLED"
        assert out2.get("already_requested") is True
        assert _audit_count("RUN_CANCELLED", pipeline_id=pid, visual_run_id=rid) == 1
        print(f"  PASS PENDING cancel rid={rid}")
    finally:
        archive_pipeline(pid)


def test_running_soft_cancel_request() -> None:
    print("== RUNNING soft-cancel request ==")
    fixture = setup_compiled_materialized(f"S85-RUN-{uuid4().hex[:6]}")
    pid = fixture["pipeline_id"]
    try:
        rid = _create_pending(pid)
        _force_running(rid)
        bad_confirm = api(
            "POST",
            f"/visual-pipelines/{pid}/runs/{rid}/cancel",
            {"reason": "wrong confirm id here", "confirm_visual_run_id": "VPR-WRONG"},
            expect_fail=True,
        )
        assert bad_confirm.get("detail") == "RUN_CANCEL_CONFIRM_MISMATCH", bad_confirm
        short = api(
            "POST",
            f"/visual-pipelines/{pid}/runs/{rid}/cancel",
            {"reason": "abc", "confirm_visual_run_id": rid},
            expect_fail=True,
        )
        assert short.get("detail") == "RUN_CANCEL_REASON_REQUIRED", short

        first = api(
            "POST",
            f"/visual-pipelines/{pid}/runs/{rid}/cancel",
            {
                "reason": "operator soft-cancel first request",
                "confirm_visual_run_id": rid,
            },
        )
        assert first["run_status"] == "RUNNING", first
        assert first.get("cancel_requested") is True
        assert first.get("already_requested") is False
        reason1 = _psql(
            f"SELECT cancel_reason FROM tb_visual_pipeline_run WHERE visual_run_id='{rid}'"
        )
        assert reason1 == "operator soft-cancel first request"
        assert _audit_count("RUN_CANCEL_REQUESTED", pipeline_id=pid, visual_run_id=rid) == 1
        assert "RUN_CANCEL_REQUESTED" in _event_types(rid)

        dup = api(
            "POST",
            f"/visual-pipelines/{pid}/runs/{rid}/cancel",
            {
                "reason": "should not overwrite reason value",
                "confirm_visual_run_id": rid,
            },
        )
        assert dup.get("already_requested") is True
        reason2 = _psql(
            f"SELECT cancel_reason FROM tb_visual_pipeline_run WHERE visual_run_id='{rid}'"
        )
        assert reason2 == reason1
        assert _audit_count("RUN_CANCEL_REQUESTED", pipeline_id=pid, visual_run_id=rid) == 1

        progress = api("GET", f"/visual-pipelines/{pid}/runs/{rid}/progress")
        assert progress.get("cancel_requested") is True
        assert progress.get("cancel_reason") == reason1
        assert progress["run_status"] == "RUNNING"

        # no auto retry after cancel request
        retry_count = int(
            _psql(
                "SELECT COUNT(*)::text FROM tb_visual_pipeline_run "
                f"WHERE retry_of_run_id='{rid}'"
            )
            or "0"
        )
        assert retry_count == 0
        print(f"  PASS RUNNING soft-cancel request rid={rid}")
    finally:
        archive_pipeline(pid)


def test_terminal_cancel_rejected() -> None:
    print("== terminal cancel rejected ==")
    fixture = setup_compiled_materialized(f"S85-TERM-{uuid4().hex[:6]}")
    pid = fixture["pipeline_id"]
    try:
        rid = _create_pending(pid)
        for terminal in ("SUCCESS", "FAILED", "PARTIAL"):
            _psql_exec(
                f"UPDATE tb_visual_pipeline_run SET run_status='{terminal}', "
                f"finished_at=NOW() WHERE visual_run_id='{rid}'"
            )
            fail = api(
                "POST",
                f"/visual-pipelines/{pid}/runs/{rid}/cancel",
                {"reason": "should fail for terminal", "confirm_visual_run_id": rid},
                expect_fail=True,
            )
            assert fail.get("detail") == "RUN_CANCEL_NOT_ALLOWED_STATUS", (terminal, fail)
        print("  PASS terminal reject")
    finally:
        archive_pipeline(pid)


def test_boundary_acknowledge() -> None:
    print("== boundary acknowledge CANCELLED ==")
    fixture = setup_compiled_materialized(f"S85-ACK-{uuid4().hex[:6]}")
    pid = fixture["pipeline_id"]
    try:
        rid = _create_pending(pid)
        _force_running(rid)
        api(
            "POST",
            f"/visual-pipelines/{pid}/runs/{rid}/cancel",
            {
                "reason": "boundary acknowledge soft cancel",
                "confirm_visual_run_id": rid,
            },
        )

        async def _ack():
            from app.core.database import async_session
            from app.models.entities import VisualPipelineRun
            from app.services.visual_pipeline.run_cancel_service import (
                VisualPipelineCancelRequested,
                apply_cancel_acknowledged,
                raise_if_visual_run_cancel_requested,
            )
            from sqlalchemy import select

            async with async_session() as db:
                raised = False
                try:
                    await raise_if_visual_run_cancel_requested(db, rid)
                except VisualPipelineCancelRequested:
                    raised = True
                assert raised, "expected VisualPipelineCancelRequested"
                row = (
                    await db.execute(
                        select(VisualPipelineRun).where(VisualPipelineRun.visual_run_id == rid)
                    )
                ).scalar_one()
                await apply_cancel_acknowledged(db, row)
                await db.commit()

        _async_run(_ack())
        status = _psql(
            f"SELECT run_status FROM tb_visual_pipeline_run WHERE visual_run_id='{rid}'"
        )
        assert status == "CANCELLED", status
        ack = _psql(
            f"SELECT cancel_acknowledged_at IS NOT NULL FROM tb_visual_pipeline_run "
            f"WHERE visual_run_id='{rid}'"
        )
        assert ack.lower() in {"t", "true", "1"}
        assert "RUN_CANCELLED" in _event_types(rid)
        detail = api("GET", f"/visual-pipelines/{pid}/runs/{rid}")
        assert detail["run_status"] == "CANCELLED"
        assert detail.get("cancel_acknowledged_at")
        print(f"  PASS boundary acknowledge rid={rid}")
    finally:
        archive_pipeline(pid)


def test_run_load_cancel_checker_default_none() -> None:
    print("== run_load cancel_checker default ==")
    import inspect

    from app.services.api_connector_service import run_load

    sig = inspect.signature(run_load)
    assert "cancel_checker" in sig.parameters
    assert sig.parameters["cancel_checker"].default is None
    print("  PASS cancel_checker default None")


def main() -> None:
    ensure_test_standard_datasets()
    test_migration_columns()
    test_pending_immediate_cancel()
    test_running_soft_cancel_request()
    test_terminal_cancel_rejected()
    test_boundary_acknowledge()
    test_run_load_cancel_checker_default_none()
    print("\nAll soft-cancel tests PASSED")


if __name__ == "__main__":
    main()
