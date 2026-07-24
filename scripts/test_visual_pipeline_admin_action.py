#!/usr/bin/env python3
"""R11-S7-14 Visual Pipeline Admin mark-failed Action PoC tests.

Uses sample-external/heat-demand — no operational external APIs.
quick regression group: NOT included.

Note: THERMOOPS_VP_ADMIN_ACTIONS_ENABLED is read by the running backend process.
Flag-on Admin HTTP checks run only when the backend already has the flag enabled;
service-layer tests cover fail-close / eligibility with require_admin_flag=False.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path
from unittest.mock import AsyncMock, patch
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


def _detail(resp: dict) -> str:
    d = resp.get("detail")
    if isinstance(d, str):
        return d
    return str(d)


def _backend_admin_actions_enabled() -> bool:
    """Probe running backend (not this process env)."""
    summary = api("GET", "/visual-pipeline-ops/summary")
    return bool((summary.get("worker_config") or {}).get("admin_actions_enabled"))


def test_feature_flag_off_http() -> None:
    print("== feature flag off (HTTP) ==")
    if _backend_admin_actions_enabled():
        print("  SKIP backend already has admin actions enabled")
        return
    fixture = setup_compiled_materialized(f"S714-FLG-{uuid4().hex[:6]}")
    pid = fixture["pipeline_id"]
    try:
        rid = _create_pending(pid)["visual_run_id"]
        psql_run(
            f"UPDATE tb_visual_pipeline_run SET created_at = NOW() - INTERVAL '30 minutes' "
            f"WHERE visual_run_id='{rid}'"
        )
        resp = api(
            "POST",
            f"/visual-pipeline-ops/stuck-runs/{rid}/mark-failed",
            {
                "reason": "flag off test reason",
                "confirm_visual_run_id": rid,
            },
            expect_fail=True,
        )
        assert resp.get("_http_status") == 409
        assert _detail(resp) == "VP_ADMIN_ACTIONS_DISABLED"
        assert (
            _psql(f"SELECT run_status FROM tb_visual_pipeline_run WHERE visual_run_id='{rid}'")
            == "PENDING"
        )
        print("  PASS flag off 409")
    finally:
        archive_pipeline(pid)


def test_confirm_mismatch_and_eligibility() -> None:
    print("== confirm / eligibility (service) ==")
    fixture = setup_compiled_materialized(f"S714-ELG-{uuid4().hex[:6]}")
    pid = fixture["pipeline_id"]
    try:
        fresh = _create_pending(pid)["visual_run_id"]
        old = _clone_run(fresh)
        live_running = _clone_run(fresh)
        terminal = _clone_run(fresh)
        cancelled = _clone_run(fresh)

        psql_run(
            f"UPDATE tb_visual_pipeline_run SET created_at = NOW() - INTERVAL '30 minutes' "
            f"WHERE visual_run_id='{old}'"
        )
        psql_run(
            f"UPDATE tb_visual_pipeline_run SET run_status='RUNNING', started_at=NOW(), "
            f"claimed_by='ops', locked_until=NOW() + INTERVAL '10 minutes' "
            f"WHERE visual_run_id='{live_running}'"
        )
        psql_run(
            f"UPDATE tb_visual_pipeline_run SET run_status='SUCCESS', finished_at=NOW() "
            f"WHERE visual_run_id='{terminal}'"
        )
        psql_run(
            f"UPDATE tb_visual_pipeline_run SET run_status='CANCELLED', finished_at=NOW() "
            f"WHERE visual_run_id='{cancelled}'"
        )

        async def _cases():
            from app.core.database import async_session
            from app.services.visual_pipeline.ops_service import (
                MarkFailedError,
                mark_single_stuck_run_failed,
            )

            async with async_session() as db:
                try:
                    await mark_single_stuck_run_failed(
                        db,
                        old,
                        reason="confirm mismatch reason",
                        confirm_visual_run_id="VPR-WRONG",
                        require_admin_flag=False,
                    )
                    raise AssertionError("expected confirm mismatch")
                except MarkFailedError as exc:
                    assert exc.code == "RUN_MARK_FAILED_CONFIRM_MISMATCH"

            for rid, label in (
                (fresh, "fresh PENDING"),
                (live_running, "live RUNNING"),
                (terminal, "terminal SUCCESS"),
                (cancelled, "CANCELLED"),
            ):
                async with async_session() as db:
                    try:
                        await mark_single_stuck_run_failed(
                            db,
                            rid,
                            reason=f"not eligible {label}",
                            confirm_visual_run_id=rid,
                            require_admin_flag=False,
                        )
                        raise AssertionError(f"expected not eligible: {label}")
                    except MarkFailedError as exc:
                        assert exc.code == "RUN_MARK_FAILED_NOT_ELIGIBLE", label

        _async_run(_cases())
        assert (
            _psql(f"SELECT run_status FROM tb_visual_pipeline_run WHERE visual_run_id='{fresh}'")
            == "PENDING"
        )
        assert (
            _psql(
                f"SELECT run_status FROM tb_visual_pipeline_run WHERE visual_run_id='{live_running}'"
            )
            == "RUNNING"
        )
        assert (
            _psql(f"SELECT run_status FROM tb_visual_pipeline_run WHERE visual_run_id='{terminal}'")
            == "SUCCESS"
        )
        assert (
            _psql(f"SELECT run_status FROM tb_visual_pipeline_run WHERE visual_run_id='{cancelled}'")
            == "CANCELLED"
        )
        print("  PASS confirm mismatch + non-eligible unchanged")
    finally:
        archive_pipeline(pid)


def test_eligible_mark_failed_and_audit() -> None:
    print("== eligible PENDING/RUNNING mark-failed ==")
    from app.core.config import get_settings

    prev_act = os.environ.get("THERMOOPS_VP_SCHEDULE_ACTIVATION_ENABLED")
    os.environ["THERMOOPS_VP_SCHEDULE_ACTIVATION_ENABLED"] = "true"
    get_settings.cache_clear()

    fixture = setup_compiled_materialized(f"S714-OK-{uuid4().hex[:6]}")
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

        pending = _create_pending(pid)["visual_run_id"]
        expired = _clone_run(pending)
        psql_run(
            f"UPDATE tb_visual_pipeline_run SET created_at = NOW() - INTERVAL '30 minutes' "
            f"WHERE visual_run_id='{pending}'"
        )
        psql_run(
            f"UPDATE tb_visual_pipeline_run SET run_status='RUNNING', started_at=NOW(), "
            f"claimed_by='ops', locked_until=NOW() - INTERVAL '5 minutes', attempt_count=2 "
            f"WHERE visual_run_id='{expired}'"
        )

        async def _mark(rid: str, reason: str):
            from app.core.database import async_session
            from app.services.visual_pipeline.ops_service import mark_single_stuck_run_failed

            async with async_session() as db:
                return await mark_single_stuck_run_failed(
                    db,
                    rid,
                    reason=reason,
                    confirm_visual_run_id=rid,
                    require_admin_flag=False,
                )

        r1 = _async_run(_mark(pending, "admin pending cleanup"))
        assert r1["changed"] is True
        assert r1["run_status"] == "FAILED"
        assert r1.get("audit_id")
        assert (
            _psql(f"SELECT run_status FROM tb_visual_pipeline_run WHERE visual_run_id='{pending}'")
            == "FAILED"
        )

        r2 = _async_run(_mark(expired, "admin expired running cleanup"))
        assert r2["changed"] is True
        assert r2["run_status"] == "FAILED"

        detail = api("GET", f"/visual-pipeline-ops/audit-logs/{r1['audit_id']}")
        assert detail["event_type"] == "RUN_MARK_FAILED_BY_OPS"
        assert detail["event_source"] == "API"
        assert detail["actor_type"] == "USER"
        assert detail["actor_id"] == "mock_admin"
        assert detail["before_json"]["run_status"] == "PENDING"
        assert detail["after_json"]["run_status"] == "FAILED"
        assert detail["metadata_json"]["trigger"] == "admin_api"
        assert "password" not in json.dumps(detail).lower() or "***REDACTED***" in json.dumps(
            detail
        )

        listed = api(
            "GET",
            f"/visual-pipeline-ops/audit-logs?event_type=RUN_MARK_FAILED_BY_OPS&visual_run_id={pending}",
        )
        assert listed["total"] >= 1

        stuck = api("GET", "/visual-pipeline-ops/stuck-runs?pending_age_seconds=600&limit=50")
        stuck_ids = {i["visual_run_id"] for i in stuck["items"]}
        assert pending not in stuck_ids
        assert expired not in stuck_ids

        assert (
            _psql(
                f"SELECT activation_status FROM tb_visual_pipeline_schedule_activation "
                f"WHERE activation_id='{act_id}'"
            )
            == "ACTIVE"
        )
        assert (
            _psql(
                f"SELECT next_due_at FROM tb_visual_pipeline_schedule_activation "
                f"WHERE activation_id='{act_id}'"
            )
            == due_before
        )
        assert (
            _psql(f"SELECT current_sync_status FROM tb_pipeline_definition WHERE pipeline_id='{pid}'")
            == sync_before
        )
        assert (
            _psql(
                f"SELECT materialization_status, activation FROM tb_visual_pipeline_materialization_result "
                f"WHERE materialization_result_id='{act['materialization_result_id']}'"
            )
            == mat_before
        )

        if _backend_admin_actions_enabled():
            pending2 = _create_pending(pid)["visual_run_id"]
            psql_run(
                f"UPDATE tb_visual_pipeline_run SET created_at = NOW() - INTERVAL '30 minutes' "
                f"WHERE visual_run_id='{pending2}'"
            )
            http_res = api(
                "POST",
                f"/visual-pipeline-ops/stuck-runs/{pending2}/mark-failed",
                {
                    "reason": "http admin mark failed",
                    "confirm_visual_run_id": pending2,
                },
            )
            assert http_res["changed"] is True
            print("  PASS eligible mark-failed + audit + HTTP path")
        else:
            print("  PASS eligible mark-failed + audit (HTTP flag-on skipped)")
    finally:
        if prev_act is None:
            os.environ.pop("THERMOOPS_VP_SCHEDULE_ACTIVATION_ENABLED", None)
        else:
            os.environ["THERMOOPS_VP_SCHEDULE_ACTIVATION_ENABLED"] = prev_act
        get_settings.cache_clear()
        archive_pipeline(pid)


def test_audit_fail_close() -> None:
    print("== audit fail-close ==")
    fixture = setup_compiled_materialized(f"S714-FC-{uuid4().hex[:6]}")
    pid = fixture["pipeline_id"]
    try:
        rid = _create_pending(pid)["visual_run_id"]
        psql_run(
            f"UPDATE tb_visual_pipeline_run SET created_at = NOW() - INTERVAL '30 minutes' "
            f"WHERE visual_run_id='{rid}'"
        )

        async def _fail_close():
            from app.core.database import async_session
            from app.services.visual_pipeline import ops_service

            async with async_session() as db:
                with patch(
                    "app.services.visual_pipeline.ops_service.record_ops_mark_failed_run_event",
                    new_callable=AsyncMock,
                    side_effect=RuntimeError("forced audit failure"),
                ):
                    try:
                        await ops_service.mark_single_stuck_run_failed(
                            db,
                            rid,
                            reason="fail close reason",
                            confirm_visual_run_id=rid,
                            require_admin_flag=False,
                        )
                        raise AssertionError("expected MarkFailedError")
                    except ops_service.MarkFailedError as exc:
                        assert exc.code == "RUN_MARK_FAILED_AUDIT_REQUIRED_FAILED"

        _async_run(_fail_close())
        assert (
            _psql(f"SELECT run_status FROM tb_visual_pipeline_run WHERE visual_run_id='{rid}'")
            == "PENDING"
        )
        audit_count = int(
            _psql(
                f"SELECT COUNT(*) FROM tb_visual_pipeline_audit_log "
                f"WHERE visual_run_id='{rid}' AND event_type='RUN_MARK_FAILED_BY_OPS'"
            )
            or "0"
        )
        assert audit_count == 0
        print("  PASS audit failure leaves run unchanged")
    finally:
        archive_pipeline(pid)


def test_cli_dry_run_and_apply_fail_close() -> None:
    print("== CLI dry-run / apply fail-close ==")
    fixture = setup_compiled_materialized(f"S714-CLI-{uuid4().hex[:6]}")
    pid = fixture["pipeline_id"]
    try:
        rid = _create_pending(pid)["visual_run_id"]
        psql_run(
            f"UPDATE tb_visual_pipeline_run SET created_at = NOW() - INTERVAL '30 minutes' "
            f"WHERE visual_run_id='{rid}'"
        )

        async def _dry():
            from app.core.database import async_session
            from app.services.visual_pipeline.ops_service import mark_stuck_runs_failed

            async with async_session() as db:
                return await mark_stuck_runs_failed(
                    db, apply=False, pending_age_seconds=600, reason="cli dry reason xx"
                )

        dry = _async_run(_dry())
        assert dry["dry_run"] is True
        assert dry["updated_count"] == 0
        assert (
            _psql(f"SELECT run_status FROM tb_visual_pipeline_run WHERE visual_run_id='{rid}'")
            == "PENDING"
        )

        async def _apply_ok():
            from app.core.database import async_session
            from app.services.visual_pipeline.ops_service import mark_stuck_runs_failed

            async with async_session() as db:
                return await mark_stuck_runs_failed(
                    db, apply=True, pending_age_seconds=600, reason="cli apply reason xx"
                )

        applied = _async_run(_apply_ok())
        assert applied["updated_count"] >= 1
        assert applied.get("audit_failed_count", 0) == 0
        assert (
            _psql(f"SELECT run_status FROM tb_visual_pipeline_run WHERE visual_run_id='{rid}'")
            == "FAILED"
        )

        rid2 = _create_pending(pid)["visual_run_id"]
        psql_run(
            f"UPDATE tb_visual_pipeline_run SET created_at = NOW() - INTERVAL '30 minutes' "
            f"WHERE visual_run_id='{rid2}'"
        )

        async def _apply_fail_audit():
            from app.core.database import async_session
            from app.services.visual_pipeline.ops_service import mark_stuck_runs_failed

            async with async_session() as db:
                with patch(
                    "app.services.visual_pipeline.ops_service.record_ops_mark_failed_run_event",
                    new_callable=AsyncMock,
                    side_effect=RuntimeError("cli audit fail"),
                ):
                    return await mark_stuck_runs_failed(
                        db,
                        apply=True,
                        pending_age_seconds=600,
                        reason="cli audit fail reason",
                    )

        failed = _async_run(_apply_fail_audit())
        assert failed["audit_failed_count"] >= 1
        assert rid2 in (failed.get("failed_ids") or [])
        assert (
            _psql(f"SELECT run_status FROM tb_visual_pipeline_run WHERE visual_run_id='{rid2}'")
            == "PENDING"
        )
        print("  PASS CLI dry-run + apply + audit fail-close summary")
    finally:
        archive_pipeline(pid)


def main() -> int:
    ensure_test_standard_datasets()
    test_feature_flag_off_http()
    test_confirm_mismatch_and_eligibility()
    test_eligible_mark_failed_and_audit()
    test_audit_fail_close()
    test_cli_dry_run_and_apply_fail_close()
    print("\nAll visual pipeline admin action tests PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
