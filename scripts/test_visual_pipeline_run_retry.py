#!/usr/bin/env python3
"""R11-S8-4 Visual Pipeline Run Retry — lineage + API + audit fail-close tests.

Uses sample-external fixtures. Not in quick group by default.
"""

from __future__ import annotations

import json
import os
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

from test_fixtures import ensure_test_standard_datasets, psql_run, psql_scalar  # noqa: E402
from test_visual_pipeline_materialization import archive_pipeline  # noqa: E402
from test_visual_pipeline_run_worker import setup_compiled_materialized  # noqa: E402

TERMINAL = frozenset({"SUCCESS", "FAILED", "PARTIAL", "CANCELLED"})


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


def _poll_run(pipeline_id: str, visual_run_id: str, *, timeout_s: int = 120) -> dict:
    deadline = time.time() + timeout_s
    last = None
    while time.time() < deadline:
        last = api("GET", f"/visual-pipelines/{pipeline_id}/runs/{visual_run_id}")
        if str(last.get("run_status") or "").upper() in TERMINAL:
            return last
        time.sleep(1.5)
    raise TimeoutError(f"run {visual_run_id} did not reach terminal within {timeout_s}s (last={last})")


def _snapshot_run(visual_run_id: str) -> dict[str, str]:
    raw = _psql(
        "SELECT run_status || '|' || COALESCE(finished_at::text,'') || '|' || "
        "COALESCE(error_message,'') || '|' || COALESCE(result_json::text,'') || '|' || "
        "COALESCE(request_json::text,'') || '|' || COALESCE(issues_json::text,'') || '|' || "
        "COALESCE(load_run_id,'') || '|' || COALESCE(retry_of_run_id,'') || '|' || "
        "COALESCE(retry_attempt::text,'0') "
        f"FROM tb_visual_pipeline_run WHERE visual_run_id='{visual_run_id}'"
    )
    parts = raw.split("|", 8)
    while len(parts) < 9:
        parts.append("")
    keys = (
        "run_status",
        "finished_at",
        "error_message",
        "result_json",
        "request_json",
        "issues_json",
        "load_run_id",
        "retry_of_run_id",
        "retry_attempt",
    )
    return dict(zip(keys, parts, strict=True))


def _seed_terminal_run(
    pipeline_id: str,
    *,
    status: str,
    compile_result_id: str,
    materialization_result_id: str,
    graph_version_hash: str | None = None,
    mode: str = "MANUAL",
) -> str:
    vid = f"VPR-RTY{uuid4().hex[:8].upper()}"
    hash_sql = f"'{graph_version_hash}'" if graph_version_hash else "NULL"
    _psql_exec(
        "INSERT INTO tb_visual_pipeline_run ("
        "visual_run_id, pipeline_id, compile_result_id, materialization_result_id, "
        "graph_version_hash, mode, execution_mode, run_status, request_json, result_json, "
        "issues_json, error_message, attempt_count, retry_attempt, created_at, started_at, finished_at"
        ") VALUES ("
        f"'{vid}', '{pipeline_id}', '{compile_result_id}', '{materialization_result_id}', "
        f"{hash_sql}, '{mode}', 'BACKGROUND', '{status}', "
        "'{\"mode\":\"MANUAL\",\"params\":{}}'::jsonb, "
        "'{\"summary\":{\"failed_count\":1}}'::jsonb, "
        "'[{\"severity\":\"ERROR\",\"code\":\"RETRY_SEED\",\"message\":\"seed\"}]'::jsonb, "
        f"'seed {status}', 0, 0, NOW(), NOW(), NOW()"
        ")"
    )
    return vid


def _detail_code(resp: dict) -> str:
    detail = resp.get("detail")
    if isinstance(detail, str):
        return detail
    return str(detail)


def main() -> None:
    ensure_test_standard_datasets()
    pipeline_id = None
    try:
        # 1) migration columns
        cols = _psql(
            "SELECT COUNT(*) FROM information_schema.columns "
            "WHERE table_name='tb_visual_pipeline_run' "
            "AND column_name IN ('retry_of_run_id','retry_attempt','retry_reason','retry_mode')"
        )
        if cols != "4":
            raise AssertionError(f"retry columns missing (found {cols}); run apply_dev_migrations.py")
        print("  [ok] retry lineage columns exist")

        setup = setup_compiled_materialized(f"S84-RTY-{uuid4().hex[:6]}")
        pipeline_id = setup["pipeline_id"]
        compile_id = setup["compile"]["compile_result_id"]
        mat_id = setup["materialization"]["materialization_result_id"]
        graph_hash = (
            setup["compile"].get("graph_version_hash")
            or setup["materialization"].get("graph_version_hash")
        )
        print(f"  [ok] fixture pipeline={pipeline_id}")

        failed_id = _seed_terminal_run(
            pipeline_id,
            status="FAILED",
            compile_result_id=compile_id,
            materialization_result_id=mat_id,
            graph_version_hash=graph_hash,
        )
        before = _snapshot_run(failed_id)

        # 2) FAILED retry → PENDING
        retry_resp = api(
            "POST",
            f"/visual-pipelines/{pipeline_id}/runs/{failed_id}/retry",
            {
                "reason": "transient API failure",
                "confirm_visual_run_id": failed_id,
                "retry_mode": "SAME_SNAPSHOT",
            },
            expect_status=202,
        )
        retry_id = str(retry_resp.get("retry_visual_run_id") or "")
        if not retry_id or retry_id == failed_id:
            raise AssertionError(f"expected new retry_visual_run_id, got {retry_resp}")
        if retry_resp.get("run_status") != "PENDING":
            raise AssertionError(f"expected PENDING, got {retry_resp}")
        if int(retry_resp.get("retry_attempt") or 0) != 1:
            raise AssertionError(f"expected retry_attempt=1, got {retry_resp}")
        print(f"  [ok] FAILED retry created {retry_id}")

        # 3) original unchanged
        after = _snapshot_run(failed_id)
        if before != after:
            raise AssertionError(f"original run mutated:\n before={before}\n after={after}")
        print("  [ok] original run unchanged")

        # 4) new run fields
        row = api("GET", f"/visual-pipelines/{pipeline_id}/runs/{retry_id}")
        if row.get("run_status") != "PENDING":
            raise AssertionError(row)
        if row.get("retry_of_run_id") != failed_id:
            raise AssertionError(row)
        if int(row.get("retry_attempt") or 0) != 1:
            raise AssertionError(row)
        if row.get("retry_mode") != "SAME_SNAPSHOT":
            raise AssertionError(row)
        if row.get("compile_result_id") != compile_id:
            raise AssertionError(row)
        if row.get("materialization_result_id") != mat_id:
            raise AssertionError(row)
        if row.get("load_run_id"):
            raise AssertionError(f"load_run_id should be null: {row}")
        if row.get("started_at") or row.get("finished_at"):
            raise AssertionError(f"started/finished should be null: {row}")
        dedup = _psql(f"SELECT COALESCE(dedup_key,'') FROM tb_visual_pipeline_run WHERE visual_run_id='{retry_id}'")
        if not dedup.startswith("RETRY:") or failed_id not in dedup:
            # root may equal failed_id
            if not dedup.startswith(f"RETRY:"):
                raise AssertionError(f"bad dedup_key: {dedup}")
        orig_dedup = _psql(
            f"SELECT COALESCE(dedup_key,'') FROM tb_visual_pipeline_run WHERE visual_run_id='{failed_id}'"
        )
        if dedup == orig_dedup and dedup:
            raise AssertionError("dedup_key must differ from original")
        print("  [ok] retry run lineage/snapshot/dedup fields")

        # 5) events + audit
        events = api("GET", f"/visual-pipelines/{pipeline_id}/runs/{retry_id}/events")
        types = [e.get("event_type") for e in (events.get("items") or [])]
        if "RUN_CREATED" not in types:
            raise AssertionError(f"RUN_CREATED missing on retry run: {types}")
        src_events = api("GET", f"/visual-pipelines/{pipeline_id}/runs/{failed_id}/events")
        src_types = [e.get("event_type") for e in (src_events.get("items") or [])]
        if "RUN_RETRY_REQUESTED" not in src_types:
            raise AssertionError(f"RUN_RETRY_REQUESTED missing on source: {src_types}")
        audit_count = _psql(
            "SELECT COUNT(*) FROM tb_visual_pipeline_audit_log "
            f"WHERE event_type='RUN_RETRY_ENQUEUED' AND visual_run_id='{failed_id}' "
            f"AND metadata_json->>'retry_visual_run_id'='{retry_id}'"
        )
        if audit_count != "1":
            raise AssertionError(f"expected RUN_RETRY_ENQUEUED audit, got {audit_count}")
        print("  [ok] run_event + audit recorded")

        # Cancel pending retry so further retries are allowed
        api("POST", f"/visual-pipelines/{pipeline_id}/runs/{retry_id}/cancel")

        # 6) PARTIAL retry
        partial_id = _seed_terminal_run(
            pipeline_id,
            status="PARTIAL",
            compile_result_id=compile_id,
            materialization_result_id=mat_id,
            graph_version_hash=graph_hash,
        )
        partial_retry = api(
            "POST",
            f"/visual-pipelines/{pipeline_id}/runs/{partial_id}/retry",
            {
                "reason": "partial upsert retry",
                "confirm_visual_run_id": partial_id,
            },
            expect_status=202,
        )
        partial_retry_id = partial_retry["retry_visual_run_id"]
        api("POST", f"/visual-pipelines/{pipeline_id}/runs/{partial_retry_id}/cancel")
        print("  [ok] PARTIAL retry created")

        # 7) disallowed statuses
        for status in ("PENDING", "RUNNING", "SUCCESS", "CANCELLED"):
            seed = _seed_terminal_run(
                pipeline_id,
                status="SUCCESS" if status == "SUCCESS" else ("CANCELLED" if status == "CANCELLED" else "FAILED"),
                compile_result_id=compile_id,
                materialization_result_id=mat_id,
                graph_version_hash=graph_hash,
            )
            if status in ("PENDING", "RUNNING"):
                _psql_exec(
                    f"UPDATE tb_visual_pipeline_run SET run_status='{status}', finished_at=NULL "
                    f"WHERE visual_run_id='{seed}'"
                )
            elif status == "CANCELLED":
                _psql_exec(
                    f"UPDATE tb_visual_pipeline_run SET run_status='CANCELLED' WHERE visual_run_id='{seed}'"
                )
            bad = api(
                "POST",
                f"/visual-pipelines/{pipeline_id}/runs/{seed}/retry",
                {"reason": "should fail status", "confirm_visual_run_id": seed},
                expect_fail=True,
            )
            if bad.get("_http_status") != 409 or _detail_code(bad) != "RUN_RETRY_NOT_ALLOWED_STATUS":
                raise AssertionError(f"status={status} expected 409 NOT_ALLOWED, got {bad}")
            if status in ("PENDING", "RUNNING"):
                _psql_exec(
                    f"UPDATE tb_visual_pipeline_run SET run_status='CANCELLED', finished_at=NOW() "
                    f"WHERE visual_run_id='{seed}'"
                )
        print("  [ok] PENDING/RUNNING/SUCCESS/CANCELLED retry disallowed")

        # 8) confirm / reason / mode validation
        bad_confirm = api(
            "POST",
            f"/visual-pipelines/{pipeline_id}/runs/{failed_id}/retry",
            {"reason": "valid reason here", "confirm_visual_run_id": "VPR-WRONG"},
            expect_fail=True,
        )
        if bad_confirm.get("_http_status") != 400 or _detail_code(bad_confirm) != "RUN_RETRY_CONFIRM_MISMATCH":
            raise AssertionError(bad_confirm)
        bad_reason = api(
            "POST",
            f"/visual-pipelines/{pipeline_id}/runs/{failed_id}/retry",
            {"reason": "abc", "confirm_visual_run_id": failed_id},
            expect_fail=True,
        )
        # Pydantic may return 422 for min_length; accept 400/422
        if bad_reason.get("_http_status") not in (400, 422):
            raise AssertionError(bad_reason)
        bad_mode = api(
            "POST",
            f"/visual-pipelines/{pipeline_id}/runs/{failed_id}/retry",
            {
                "reason": "valid reason here",
                "confirm_visual_run_id": failed_id,
                "retry_mode": "LATEST_MATERIALIZATION",
            },
            expect_fail=True,
        )
        if bad_mode.get("_http_status") != 400 or _detail_code(bad_mode) != "RUN_RETRY_MODE_NOT_SUPPORTED":
            raise AssertionError(bad_mode)
        print("  [ok] confirm/reason/mode validation")

        # 9) 404 wrong pipeline / missing
        missing = api(
            "POST",
            f"/visual-pipelines/{pipeline_id}/runs/VPR-NOTEXIST/retry",
            {"reason": "valid reason here", "confirm_visual_run_id": "VPR-NOTEXIST"},
            expect_fail=True,
        )
        if missing.get("_http_status") != 404:
            raise AssertionError(missing)
        print("  [ok] source not found → 404")

        # 10) active run exists
        active = _seed_terminal_run(
            pipeline_id,
            status="FAILED",
            compile_result_id=compile_id,
            materialization_result_id=mat_id,
            graph_version_hash=graph_hash,
        )
        _psql_exec(
            f"UPDATE tb_visual_pipeline_run SET run_status='PENDING', finished_at=NULL "
            f"WHERE visual_run_id='{active}'"
        )
        blocked = api(
            "POST",
            f"/visual-pipelines/{pipeline_id}/runs/{failed_id}/retry",
            {"reason": "blocked by active", "confirm_visual_run_id": failed_id},
            expect_fail=True,
        )
        if blocked.get("_http_status") != 409 or _detail_code(blocked) != "RUN_RETRY_ACTIVE_RUN_EXISTS":
            raise AssertionError(blocked)
        _psql_exec(
            f"UPDATE tb_visual_pipeline_run SET run_status='CANCELLED', finished_at=NOW() "
            f"WHERE visual_run_id='{active}'"
        )
        print("  [ok] active run blocks retry")

        # 11) max retry exceeded (set max=1 via env is hard; simulate by inserting attempts)
        # With default max=3, create 3 retries then 4th fails.
        # Cancel each pending after create.
        chain_src = _seed_terminal_run(
            pipeline_id,
            status="FAILED",
            compile_result_id=compile_id,
            materialization_result_id=mat_id,
            graph_version_hash=graph_hash,
        )
        last = chain_src
        for i in range(3):
            r = api(
                "POST",
                f"/visual-pipelines/{pipeline_id}/runs/{last}/retry",
                {"reason": f"chain retry {i+1} ok", "confirm_visual_run_id": last},
                expect_status=202,
            )
            last = r["retry_visual_run_id"]
            # Mark previous retry terminal FAILED so next retry is allowed (no active)
            _psql_exec(
                f"UPDATE tb_visual_pipeline_run SET run_status='FAILED', finished_at=NOW() "
                f"WHERE visual_run_id='{last}'"
            )
        over = api(
            "POST",
            f"/visual-pipelines/{pipeline_id}/runs/{last}/retry",
            {"reason": "should exceed max", "confirm_visual_run_id": last},
            expect_fail=True,
        )
        if over.get("_http_status") != 409 or _detail_code(over) != "RUN_RETRY_MAX_ATTEMPT_EXCEEDED":
            raise AssertionError(over)
        print("  [ok] max retry exceeded → 409")

        # 12) history filter retry_of_run_id
        listed = api(
            "GET",
            f"/visual-pipelines/{pipeline_id}/runs?retry_of_run_id={failed_id}",
        )
        items = listed.get("items") or []
        if not any(i.get("visual_run_id") == retry_id for i in items):
            raise AssertionError(f"retry_of filter missing {retry_id}: {items}")
        print("  [ok] history filter retry_of_run_id")

        # 13) worker claim + progress on retry run
        worker_src = _seed_terminal_run(
            pipeline_id,
            status="FAILED",
            compile_result_id=compile_id,
            materialization_result_id=mat_id,
            graph_version_hash=graph_hash,
        )
        wr = api(
            "POST",
            f"/visual-pipelines/{pipeline_id}/runs/{worker_src}/retry",
            {"reason": "worker execute retry", "confirm_visual_run_id": worker_src},
            expect_status=202,
        )
        wr_id = wr["retry_visual_run_id"]
        import asyncio

        from sqlalchemy import text

        from app.core.database import async_session, engine
        from app.services.visual_pipeline.run_worker_service import (
            execute_claimed_visual_pipeline_run,
        )

        async def _claim_and_execute() -> dict:
            wid = f"test-retry-{uuid4().hex[:6]}"
            try:
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
                        {"worker_id": wid, "visual_run_id": wr_id},
                    )
                    claimed = result.fetchone()
                    await db.commit()
                    if claimed is None:
                        raise AssertionError(f"failed to claim retry run {wr_id}")
                async with async_session() as db:
                    return await execute_claimed_visual_pipeline_run(db, wr_id, worker_id=wid)
            finally:
                await engine.dispose()

        summary = asyncio.run(_claim_and_execute())
        terminal = _poll_run(pipeline_id, wr_id, timeout_s=60)
        if terminal.get("run_status") not in {"SUCCESS", "PARTIAL", "FAILED"}:
            raise AssertionError(f"retry run not terminal: {terminal}; worker={summary}")
        progress = api("GET", f"/visual-pipelines/{pipeline_id}/runs/{wr_id}/progress")
        if int(progress.get("event_count") or 0) < 1:
            raise AssertionError(f"expected progress events on retry run: {progress}")
        print(f"  [ok] worker executed retry run status={terminal.get('run_status')}")

        # 14) audit fail-close
        from app.core.database import async_session
        from app.services.visual_pipeline import run_retry_service as rrs

        async def _audit_fail_case() -> None:
            src = _seed_terminal_run(
                pipeline_id,
                status="FAILED",
                compile_result_id=compile_id,
                materialization_result_id=mat_id,
                graph_version_hash=graph_hash,
            )
            before_count = int(
                _psql(f"SELECT COUNT(*) FROM tb_visual_pipeline_run WHERE pipeline_id='{pipeline_id}'") or "0"
            )
            real = rrs.record_run_retry_enqueued_event

            async def boom(*_a, **_k):
                raise RuntimeError("forced audit failure")

            rrs.record_run_retry_enqueued_event = boom  # type: ignore[assignment]
            try:
                async with async_session() as db:
                    try:
                        await rrs.retry_visual_pipeline_run(
                            db,
                            pipeline_id=pipeline_id,
                            source_visual_run_id=src,
                            reason="audit fail close test",
                            confirm_visual_run_id=src,
                        )
                        raise AssertionError("expected RunRetryError")
                    except rrs.RunRetryError as exc:
                        if exc.code != "RUN_RETRY_AUDIT_REQUIRED_FAILED":
                            raise AssertionError(exc) from exc
                        await db.rollback()
            finally:
                rrs.record_run_retry_enqueued_event = real  # type: ignore[assignment]
                await engine.dispose()
            after_count = int(
                _psql(f"SELECT COUNT(*) FROM tb_visual_pipeline_run WHERE pipeline_id='{pipeline_id}'") or "0"
            )
            if after_count != before_count:
                raise AssertionError(f"audit fail-close leaked run: {before_count} -> {after_count}")
            snap = _snapshot_run(src)
            if snap["run_status"] != "FAILED":
                raise AssertionError(snap)

        asyncio.run(_audit_fail_case())
        print("  [ok] audit fail-close prevents retry run creation")

        print("\nR11-S8-4 run retry tests passed.")
    finally:
        if pipeline_id:
            try:
                archive_pipeline(pipeline_id)
            except Exception as exc:  # noqa: BLE001
                print(f"  [warn] archive_pipeline failed: {exc}")


if __name__ == "__main__":
    main()
