"""Visual Pipeline Schedule Worker CLI (R11-S7-8).

Due enqueue only — never calls run_load. Separate from R10 run-due-worker
and VP run-worker.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import signal
import sys

from app.core.config import get_settings
from app.services.visual_pipeline.schedule_worker_service import (
    VpScheduleWorkerConfig,
    build_schedule_worker_id,
    run_schedule_worker_loop,
    run_schedule_worker_once,
)

_shutdown = False


def _handle_signal(signum, _frame) -> None:
    global _shutdown
    logging.getLogger(__name__).info("received signal %s — graceful shutdown", signum)
    _shutdown = True


async def amain(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="THERMOps Visual Pipeline schedule-worker")
    parser.add_argument("--mode", choices=("loop", "once"), default=None)
    parser.add_argument("--batch-size", type=int, default=None)
    parser.add_argument("--poll-interval-seconds", type=int, default=None)
    parser.add_argument("--worker-id", type=str, default=None)
    parser.add_argument("--max-iterations", type=int, default=None, help="loop test helper")
    parser.add_argument(
        "--force",
        action="store_true",
        help="run even when THERMOOPS_VP_SCHEDULE_WORKER_ENABLED=false",
    )
    args = parser.parse_args(argv)

    settings = get_settings()
    config = VpScheduleWorkerConfig.from_settings(settings)
    if args.mode:
        config.worker_mode = args.mode
    if args.batch_size is not None:
        config.max_batch_size = max(1, args.batch_size)
    if args.poll_interval_seconds is not None:
        config.poll_interval_seconds = max(1, args.poll_interval_seconds)
    if args.worker_id:
        config.worker_id = args.worker_id

    logging.basicConfig(
        level=getattr(logging, config.log_level, logging.INFO),
        format="%(asctime)s %(levelname)s [vp-schedule-worker] %(message)s",
    )
    log = logging.getLogger(__name__)

    if not config.enabled and not args.force:
        log.info("THERMOOPS_VP_SCHEDULE_WORKER_ENABLED is false — exiting")
        return 0

    worker_id = build_schedule_worker_id(config.worker_id)
    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)

    log.info("worker started worker_id=%s mode=%s", worker_id, config.worker_mode)
    if config.worker_mode == "once":
        summary = await run_schedule_worker_once(
            worker_id=worker_id,
            batch_size=config.max_batch_size,
        )
        log.info("once finished: %s", summary)
        return 0

    await run_schedule_worker_loop(
        worker_id=worker_id,
        poll_interval_seconds=config.poll_interval_seconds,
        batch_size=config.max_batch_size,
        max_iterations=args.max_iterations,
        should_stop=lambda: _shutdown,
    )
    return 0


def main() -> None:
    raise SystemExit(asyncio.run(amain()))


if __name__ == "__main__":
    main()
