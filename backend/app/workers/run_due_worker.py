"""Run-due Worker CLI 진입점 (R10-S10)."""

from __future__ import annotations

import argparse
import asyncio
import logging
import signal
import sys

from app.core.config import get_settings
from app.core.database import async_session
from app.services.run_due_worker_lock_service import release_lock
from app.services.run_due_worker_service import (
    WorkerConfig,
    build_worker_instance_id,
    execute_worker_tick,
    set_worker_status,
    update_heartbeat,
    upsert_worker_instance,
)

_shutdown = False


def _handle_signal(signum, _frame) -> None:
    global _shutdown
    logging.getLogger(__name__).info("received signal %s — graceful shutdown", signum)
    _shutdown = True


async def _run_loop(instance_id: str, config: WorkerConfig) -> int:
    global _shutdown
    while not _shutdown:
        async with async_session() as db:
            try:
                await update_heartbeat(db, instance_id, status="RUNNING")
                await execute_worker_tick(db, worker_instance_id=instance_id, config=config, run_mode="LOOP_TICK")
                await db.commit()
            except Exception:
                await db.rollback()
                logging.getLogger(__name__).exception("worker tick failed")
        if _shutdown:
            break
        await asyncio.sleep(config.poll_interval_seconds)
    return 0


async def _run_once(instance_id: str, config: WorkerConfig) -> int:
    async with async_session() as db:
        try:
            await update_heartbeat(db, instance_id, status="RUNNING")
            result = await execute_worker_tick(db, worker_instance_id=instance_id, config=config, run_mode="ONCE")
            await db.commit()
            logging.getLogger(__name__).info("once run finished: %s", result.get("run_status"))
            return 0 if result.get("run_status") != "FAILED" else 1
        except Exception:
            await db.rollback()
            logging.getLogger(__name__).exception("once run failed")
            return 1


async def _shutdown_worker(instance_id: str, config: WorkerConfig) -> None:
    async with async_session() as db:
        try:
            await release_lock(db, owner_instance_id=instance_id)
            await set_worker_status(db, instance_id, "STOPPED")
            await db.commit()
        except Exception:
            await db.rollback()
            logging.getLogger(__name__).exception("shutdown cleanup failed")


async def amain(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="THERMOps run-due worker")
    parser.add_argument("--mode", choices=("loop", "once"), default=None, help="loop or once")
    args = parser.parse_args(argv)

    settings = get_settings()
    config = WorkerConfig.from_settings(settings)
    if args.mode:
        config = WorkerConfig(
            enabled=config.enabled,
            worker_name=config.worker_name,
            worker_mode=args.mode,
            poll_interval_seconds=config.poll_interval_seconds,
            lock_ttl_seconds=config.lock_ttl_seconds,
            max_batch_size=config.max_batch_size,
            fail_fast=config.fail_fast,
            notification_enabled=config.notification_enabled,
            graceful_timeout_seconds=config.graceful_timeout_seconds,
            log_level=config.log_level,
        )

    logging.basicConfig(
        level=getattr(logging, config.log_level, logging.INFO),
        format="%(asctime)s %(levelname)s [run-due-worker] %(message)s",
    )
    log = logging.getLogger(__name__)

    if not config.enabled:
        log.info("THERMOOPS_RUN_DUE_WORKER_ENABLED is false — exiting")
        return 0

    instance_id = build_worker_instance_id(config.worker_name)
    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)

    async with async_session() as db:
        try:
            await upsert_worker_instance(db, worker_instance_id=instance_id, config=config, status="STARTING")
            await db.commit()
        except Exception:
            await db.rollback()
            log.exception("worker initialization failed")
            return 1

    log.info("worker started instance=%s mode=%s", instance_id, config.worker_mode)
    try:
        if config.worker_mode == "once":
            code = await _run_once(instance_id, config)
        else:
            code = await _run_loop(instance_id, config)
    finally:
        await _shutdown_worker(instance_id, config)
    return code


def main() -> None:
    raise SystemExit(asyncio.run(amain()))


if __name__ == "__main__":
    main()
