#!/usr/bin/env python3
"""R11-S8-3 Visual Pipeline Run Progress — event table + API + execution emit tests.

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
EXPECTED_EVENT_TYPES = {
    "RUN_CREATED",
    "RUN_STARTED",
    "STEP_STARTED",
    "STEP_COMPLETED",
    "LOAD_FINALIZE",
    "RUN_COMPLETED",
    "RUN_FAILED",
}


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


def _event_types(visual_run_id: str) -> list[str]:
    raw = _psql(
        "SELECT COALESCE(string_agg(event_type, ',' ORDER BY created_at, event_id), '') "
        f"FROM tb_visual_pipeline_run_event WHERE visual_run_id = '{visual_run_id}'"
    )
    return [x for x in raw.split(",") if x]


def _assert_no_secret_in_events(visual_run_id: str) -> None:
    raw = _psql(
        "SELECT COALESCE(string_agg(COALESCE(message,'') || COALESCE(metadata_json::text,''), E'\\n'), '') "
        f"FROM tb_visual_pipeline_run_event WHERE visual_run_id = '{visual_run_id}'"
    ).lower()
    for marker in ("bearer ", "authorization:", "password=", "api_key=", "secret"):
        if marker in raw:
            raise AssertionError(f"secret marker '{marker}' found in run events for {visual_run_id}")


def main() -> None:
    ensure_test_standard_datasets()
    pipeline_id = None
    try:
        setup = setup_compiled_materialized(f"S83-PROG-{uuid4().hex[:6]}")
        pipeline_id = setup["pipeline_id"]
        print(f"  [ok] fixture pipeline={pipeline_id}")

        table_exists = _psql(
            "SELECT COUNT(*) FROM information_schema.tables "
            "WHERE table_schema='public' AND table_name='tb_visual_pipeline_run_event'"
        )
        if table_exists != "1":
            raise AssertionError("tb_visual_pipeline_run_event table missing — run apply_dev_migrations.py")

        created = api(
            "POST",
            f"/visual-pipelines/{pipeline_id}/runs",
            {},
            expect_status=202,
        )
        visual_run_id = str(created.get("visual_run_id") or "")
        if not visual_run_id:
            raise AssertionError(f"missing visual_run_id in create response: {created}")
        print(f"  [ok] created run {visual_run_id}")

        created_events = _event_types(visual_run_id)
        if "RUN_CREATED" not in created_events:
            raise AssertionError(f"RUN_CREATED missing after create: {created_events}")

        terminal = _poll_run(pipeline_id, visual_run_id)
        status = str(terminal.get("run_status") or "").upper()
        print(f"  [ok] run terminal status={status}")

        events_api = api(
            "GET",
            f"/visual-pipelines/{pipeline_id}/runs/{visual_run_id}/events",
        )
        items = events_api.get("items") if isinstance(events_api, dict) else None
        if not isinstance(items, list) or len(items) < 3:
            raise AssertionError(f"expected >=3 events, got {events_api}")
        for item in items:
            if not isinstance(item, dict):
                continue
            et = str(item.get("event_type") or "")
            if et not in EXPECTED_EVENT_TYPES and et not in {"WORKER_CLAIMED"}:
                raise AssertionError(f"unexpected event_type in API: {et}")
        print(f"  [ok] events API count={len(items)}")

        progress = api(
            "GET",
            f"/visual-pipelines/{pipeline_id}/runs/{visual_run_id}/progress",
        )
        if progress.get("visual_run_id") != visual_run_id:
            raise AssertionError(f"progress visual_run_id mismatch: {progress}")
        if progress.get("run_status") != status:
            raise AssertionError(
                f"progress run_status={progress.get('run_status')} != terminal={status}"
            )
        steps = progress.get("steps")
        if not isinstance(steps, list) or len(steps) < 3:
            raise AssertionError(f"expected 3 progress steps, got {progress}")
        print(f"  [ok] progress API percent={progress.get('progress_percent')}")

        all_types = set(_event_types(visual_run_id))
        for required in ("RUN_CREATED", "RUN_STARTED", "LOAD_FINALIZE"):
            if required not in all_types:
                raise AssertionError(f"missing {required} in DB events: {all_types}")
        if status in {"SUCCESS", "PARTIAL"} and "RUN_COMPLETED" not in all_types:
            raise AssertionError(f"RUN_COMPLETED missing for status={status}: {all_types}")
        if status == "FAILED" and "RUN_FAILED" not in all_types:
            raise AssertionError(f"RUN_FAILED missing for status={status}: {all_types}")

        step_started = [t for t in all_types if t == "STEP_STARTED"]
        step_completed = [t for t in all_types if t == "STEP_COMPLETED"]
        if not step_started or not step_completed:
            raise AssertionError(f"step events missing: started={step_started} completed={step_completed}")

        step_keys = _psql(
            "SELECT COALESCE(string_agg(DISTINCT step_key, ',' ORDER BY step_key), '') "
            f"FROM tb_visual_pipeline_run_event WHERE visual_run_id='{visual_run_id}' "
            "AND step_key IS NOT NULL"
        )
        for expected_key in ("SOURCE_FETCH", "TRANSFORM", "UPSERT_LOAD"):
            if expected_key not in step_keys.split(","):
                raise AssertionError(f"missing step_key {expected_key} in events: {step_keys}")
        print(f"  [ok] step keys recorded: {step_keys}")

        _assert_no_secret_in_events(visual_run_id)
        print("  [ok] no secret markers in event payloads")

        # Cancel path — RUN_CANCELLED event
        created2 = api("POST", f"/visual-pipelines/{pipeline_id}/runs", {}, expect_status=202)
        vid2 = str(created2.get("visual_run_id") or "")
        cancelled = api("POST", f"/visual-pipelines/{pipeline_id}/runs/{vid2}/cancel")
        if str(cancelled.get("run_status") or "").upper() != "CANCELLED":
            raise AssertionError(f"cancel expected CANCELLED, got {cancelled}")
        cancel_events = _event_types(vid2)
        if "RUN_CANCELLED" not in cancel_events:
            raise AssertionError(f"RUN_CANCELLED missing after cancel: {cancel_events}")
        print("  [ok] cancel emits RUN_CANCELLED")

        # Read-only: events API must not mutate run row
        before = _psql(
            f"SELECT run_status || '|' || COALESCE(finished_at::text,'') "
            f"FROM tb_visual_pipeline_run WHERE visual_run_id='{visual_run_id}'"
        )
        api("GET", f"/visual-pipelines/{pipeline_id}/runs/{visual_run_id}/events")
        api("GET", f"/visual-pipelines/{pipeline_id}/runs/{visual_run_id}/progress")
        after = _psql(
            f"SELECT run_status || '|' || COALESCE(finished_at::text,'') "
            f"FROM tb_visual_pipeline_run WHERE visual_run_id='{visual_run_id}'"
        )
        if before != after:
            raise AssertionError(f"read APIs mutated run row: {before} -> {after}")
        print("  [ok] events/progress APIs are read-only")

        print("\nR11-S8-3 run progress tests passed.")
    finally:
        if pipeline_id:
            try:
                archive_pipeline(pipeline_id)
            except Exception as exc:  # noqa: BLE001
                print(f"  [warn] archive_pipeline failed: {exc}")


if __name__ == "__main__":
    main()
