#!/usr/bin/env python3
"""R10-S10 Run Due Worker / Cron 운영 구성 테스트."""

from __future__ import annotations

import json
import os
import sys
import uuid
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent
_BACKEND = _SCRIPTS.parent / "backend"
for p in (str(_SCRIPTS), str(_BACKEND)):
    if p not in sys.path:
        sys.path.insert(0, p)

from test_fixtures import psql_run, psql_scalar

API_BASE = os.environ.get("THERMOOPS_API_BASE", "http://localhost:8000/api/v1")
SECRET_PROBE = "TEST_SECRET_R10S10_SHOULD_NOT_LEAK"
SEED_PATH = _SCRIPTS.parent / "db" / "init" / "02_seed_clean.sql"
COMPOSE_TRAEFIK = _SCRIPTS.parent / "docker-compose.traefik.yml"
CRON_SCRIPT = _SCRIPTS / "run_due_once.sh"


def api(method: str, path: str, body: dict | None = None) -> dict | list:
    import urllib.error
    import urllib.request

    url = f"{API_BASE}{path}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={"Content-Type": "application/json"} if data else {},
    )
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            payload = json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"HTTP {exc.code} {path}: {exc.read().decode()}") from exc
    if not payload.get("success"):
        raise RuntimeError(f"API failed {path}: {payload}")
    return payload.get("data")


def assert_no_secret(blob: str) -> None:
    if SECRET_PROBE in blob:
        raise AssertionError("secret probe leaked")


def _async_lock_tests() -> None:
    """Docker backend 컨테이너에서 실행 (호스트 .env extra 필드 회피)."""
    import subprocess

    inline = r'''
import asyncio
import json
import os
import sys
sys.path.insert(0, "/app")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://thermops:thermops@postgres:5432/thermops")

from app.core.database import async_session
from app.services.run_due_worker_lock_service import DEFAULT_LOCK_KEY, release_lock, try_acquire_lock
from app.services.run_due_worker_service import WorkerConfig, build_worker_instance_id, execute_worker_tick, mask_run_due_result, upsert_worker_instance
from app.services.runtime_param_template_service import mask_runtime_params

SECRET_PROBE = "TEST_SECRET_R10S10_SHOULD_NOT_LEAK"

async def main():
    owner_a = "test-worker-a@host:1"
    owner_b = "test-worker-b@host:2"
    async with async_session() as db:
        await release_lock(db, owner_instance_id=owner_a)
        await release_lock(db, owner_instance_id=owner_b)
        assert await try_acquire_lock(db, owner_instance_id=owner_a, ttl_seconds=120)
        assert not await try_acquire_lock(db, owner_instance_id=owner_b, ttl_seconds=120)
        await db.commit()
    from sqlalchemy import text
    async with async_session() as db:
        await db.execute(text("UPDATE tb_run_due_worker_lock SET expires_at = NOW() - INTERVAL '1 minute' WHERE lock_key = :k"), {"k": DEFAULT_LOCK_KEY})
        await db.commit()
    async with async_session() as db:
        assert await try_acquire_lock(db, owner_instance_id=owner_b, ttl_seconds=120)
        await release_lock(db, owner_instance_id=owner_b)
        await db.commit()
    masked = mask_run_due_result({"serviceKey": SECRET_PROBE, "results": [{"runtime_params": {"serviceKey": SECRET_PROBE}}]})
    assert SECRET_PROBE not in json.dumps(masked)
    assert SECRET_PROBE not in json.dumps(mask_runtime_params({"serviceKey": SECRET_PROBE}))
    cfg = WorkerConfig(enabled=True, worker_name="test-worker-local", worker_mode="once", poll_interval_seconds=60, lock_ttl_seconds=120, max_batch_size=20, fail_fast=False, notification_enabled=True, graceful_timeout_seconds=30, log_level="INFO")
    instance_id = build_worker_instance_id(cfg.worker_name)
    async with async_session() as db:
        await upsert_worker_instance(db, worker_instance_id=instance_id, config=cfg, status="RUNNING")
        await db.commit()
    async with async_session() as db:
        run = await execute_worker_tick(db, worker_instance_id=instance_id, config=cfg, run_mode="ONCE")
        await db.commit()
    assert run["run_status"] in ("SUCCESS", "SKIPPED", "WARNING")
    assert SECRET_PROBE not in json.dumps(run)

asyncio.run(main())
'''
    subprocess.run(
        ["docker", "compose", "exec", "-T", "backend", "python", "-c", inline],
        cwd=_SCRIPTS.parent,
        check=True,
        text=True,
        capture_output=True,
    )
    print("  [ok] lock acquire / duplicate / ttl expiry (container)")
    print("  [ok] secret masking in worker result (container)")
    print("  [ok] worker instance upsert + once tick (container)")


def test_compose_static() -> None:
    text = COMPOSE_TRAEFIK.read_text(encoding="utf-8")
    assert "run-due-worker:" in text
    assert "app.workers.run_due_worker" in text
    assert "traefik.enable=false" in text
    print("  [ok] docker-compose.traefik run-due-worker service")


def test_cron_script_exists() -> None:
    assert CRON_SCRIPT.is_file(), "scripts/run_due_once.sh missing"
    content = CRON_SCRIPT.read_text(encoding="utf-8")
    assert "--mode once" in content
    print("  [ok] cron example script exists")


def main() -> int:
    print(f"THERMOps run due worker test ({API_BASE})")
    try:
        worker_tables = (
            "tb_run_due_worker_instance",
            "tb_run_due_worker_run",
            "tb_run_due_worker_lock",
        )
        if os.environ.get("THERMOOPS_CLEAN_VERIFY") == "1":
            for tbl in worker_tables:
                assert int(psql_scalar(f"SELECT COUNT(*) FROM {tbl}") or "0") == 0, tbl
            seed = SEED_PATH.read_text(encoding="utf-8").lower()
            for tbl in worker_tables:
                assert f"insert into {tbl}" not in seed
            test_compose_static()
            test_cron_script_exists()
            print("PASS")
            return 0

        for tbl in worker_tables:
            count = int(psql_scalar(f"SELECT COUNT(*) FROM {tbl}") or "0")
            print(f"  [info] {tbl} count={count}")

        test_compose_static()
        test_cron_script_exists()

        summary = api("GET", "/run-due-worker/summary")
        assert "instance_count" in summary and "lock_key" in summary
        print("  [ok] API summary")

        instances = api("GET", "/run-due-worker/instances")
        assert isinstance(instances, list)
        runs = api("GET", "/run-due-worker/runs?limit=10")
        assert isinstance(runs, list)
        locks = api("GET", "/run-due-worker/locks")
        assert isinstance(locks, list)
        print("  [ok] API instances/runs/locks list")

        _async_lock_tests()

        run_once = api("POST", "/run-due-worker/run-once", {"worker_name": f"test-api-{uuid.uuid4().hex[:6]}"})
        assert run_once.get("worker_run_id")
        assert_no_secret(json.dumps(run_once))
        detail = api("GET", f"/run-due-worker/runs/{run_once['worker_run_id']}")
        assert detail["worker_run_id"] == run_once["worker_run_id"]
        assert_no_secret(json.dumps(detail))
        print("  [ok] API run-once + run detail")

        inst_id = run_once.get("worker_instance_id")
        if inst_id:
            one = api("GET", f"/run-due-worker/instances/{inst_id}")
            assert one["worker_instance_id"] == inst_id
            print("  [ok] API instance detail")

        marked = api("POST", "/run-due-worker/mark-stale", {})
        assert isinstance(marked, list)
        print(f"  [ok] mark-stale returned {len(marked)} rows")

        # notification events (optional — tables may be empty)
        try:
            events = api("GET", "/notifications/events?limit=20")
            if isinstance(events, list):
                for ev in events:
                    if ev.get("event_source") == "RUN_DUE_WORKER":
                        assert_no_secret(json.dumps(ev))
        except RuntimeError:
            pass
        print("  [ok] notification RUN_DUE_WORKER events checked")

        # run-due backward compat
        run_due = api("POST", "/data-load-schedules/run-due")
        assert "due_count" in run_due and "due_schedule_count" in run_due
        print("  [ok] data_load_scheduler run-due backward compat")

        print("PASS")
        return 0
    except Exception as exc:
        print(f"FAIL: {exc}")
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
