"""R11-S7-6 Visual Pipeline Run Worker — Option C DB claim + R10 run_load.

Separate from R10 run-due-worker. Does not activate schedules or call due worker.
"""

from __future__ import annotations

import asyncio
import logging
import socket
from dataclasses import dataclass
from typing import Any, Callable
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.database import async_session
from app.core.time import utc_now
from app.models.entities import VisualPipelineRun
from app.services.visual_pipeline.manual_run_service import (
    ACTIVE_RUN_STATUSES,
    _clear_run_lease,
    _issue,
    _run_load_and_update_result,
    _sanitize_error_message,
)
from app.services.visual_pipeline.visual_pipeline_service import _get_visual_definition

logger = logging.getLogger(__name__)

CLAIM_SQL = text(
    """
WITH picked AS (
  SELECT visual_run_id
  FROM tb_visual_pipeline_run
  WHERE run_status = 'PENDING'
  ORDER BY created_at ASC
  FOR UPDATE SKIP LOCKED
  LIMIT :batch_size
)
UPDATE tb_visual_pipeline_run r
SET run_status = 'RUNNING',
    claimed_at = NOW(),
    claimed_by = :worker_id,
    locked_until = NOW() + make_interval(secs => :lock_ttl_seconds),
    heartbeat_at = NOW(),
    attempt_count = COALESCE(attempt_count, 0) + 1,
    started_at = COALESCE(started_at, NOW())
FROM picked
WHERE r.visual_run_id = picked.visual_run_id
RETURNING r.visual_run_id
"""
)


@dataclass
class VpRunWorkerConfig:
    enabled: bool = True
    worker_id: str = ""
    worker_mode: str = "loop"
    poll_interval_seconds: int = 5
    lock_ttl_seconds: int = 120
    max_batch_size: int = 1
    log_level: str = "INFO"

    @classmethod
    def from_settings(cls, settings: Settings | None = None) -> VpRunWorkerConfig:
        s = settings or get_settings()
        return cls(
            enabled=bool(s.vp_run_worker_enabled),
            worker_id=str(s.vp_run_worker_id or "").strip(),
            worker_mode=str(s.vp_run_worker_mode or "loop").strip().lower() or "loop",
            poll_interval_seconds=max(1, int(s.vp_run_worker_poll_interval_seconds)),
            lock_ttl_seconds=max(30, int(s.vp_run_worker_lock_ttl_seconds)),
            max_batch_size=max(1, min(int(s.vp_run_worker_max_batch_size), 10)),
            log_level=str(s.vp_run_worker_log_level or "INFO").upper(),
        )


def build_worker_id(explicit: str | None = None) -> str:
    text_id = (explicit or "").strip()
    if text_id:
        return text_id[:120]
    host = socket.gethostname().split(".")[0][:40] or "host"
    return f"vp-run-{host}-{uuid4().hex[:8]}"


async def claim_next_visual_pipeline_runs(
    db: AsyncSession,
    *,
    worker_id: str,
    lock_ttl_seconds: int = 120,
    batch_size: int = 1,
) -> list[str]:
    """Atomically claim PENDING runs via FOR UPDATE SKIP LOCKED. Returns visual_run_ids."""
    result = await db.execute(
        CLAIM_SQL,
        {
            "worker_id": worker_id,
            "lock_ttl_seconds": int(lock_ttl_seconds),
            "batch_size": max(1, int(batch_size)),
        },
    )
    ids = [str(row[0]) for row in result.fetchall()]
    await db.commit()
    return ids


async def execute_claimed_visual_pipeline_run(
    db: AsyncSession,
    visual_run_id: str,
    *,
    worker_id: str,
) -> dict[str, Any]:
    """Execute R10 run_load for an already-claimed RUNNING row. Commits."""
    run_row = await db.get(VisualPipelineRun, visual_run_id)
    if run_row is None:
        logger.warning("claimed visual run %s not found", visual_run_id)
        return {"visual_run_id": visual_run_id, "run_status": "MISSING", "claimed": False}

    if run_row.run_status != "RUNNING":
        logger.info(
            "visual run %s status=%s — skip worker execute (expected RUNNING)",
            visual_run_id,
            run_row.run_status,
        )
        return {
            "visual_run_id": visual_run_id,
            "run_status": run_row.run_status,
            "claimed": False,
            "skipped": True,
        }

    sync_before = None
    try:
        defn = await _get_visual_definition(db, run_row.pipeline_id)
        sync_before = defn.current_sync_status
    except LookupError:
        sync_before = None

    try:
        await _run_load_and_update_result(db, run_row)
        if sync_before is not None:
            try:
                defn = await _get_visual_definition(db, run_row.pipeline_id)
                defn.current_sync_status = sync_before
                await db.flush()
            except LookupError:
                pass
        await db.commit()
        await db.refresh(run_row)
        logger.info(
            "worker=%s visual_run_id=%s status=%s",
            worker_id,
            visual_run_id,
            run_row.run_status,
        )
        return {
            "visual_run_id": visual_run_id,
            "run_status": run_row.run_status,
            "load_run_id": run_row.load_run_id,
            "claimed": True,
            "worker_id": worker_id,
        }
    except Exception as exc:  # noqa: BLE001 — mark FAILED, keep worker alive
        logger.exception("worker execute failed visual_run_id=%s", visual_run_id)
        await db.rollback()
        async with async_session() as db2:
            row = await db2.get(VisualPipelineRun, visual_run_id)
            if row is not None and row.run_status in ACTIVE_RUN_STATUSES:
                row.run_status = "FAILED"
                row.finished_at = utc_now()
                row.error_message = _sanitize_error_message(str(exc))
                row.issues_json = [
                    _issue(
                        "RUN_WORKER_TASK_FAILED",
                        _sanitize_error_message(str(exc)) or "VP run-worker task failed",
                        step_id="worker",
                    )
                ]
                _clear_run_lease(row)
                await db2.commit()
                return {
                    "visual_run_id": visual_run_id,
                    "run_status": "FAILED",
                    "claimed": True,
                    "worker_id": worker_id,
                    "error": True,
                }
        return {
            "visual_run_id": visual_run_id,
            "run_status": "FAILED",
            "claimed": True,
            "worker_id": worker_id,
            "error": True,
        }


async def run_worker_once(
    *,
    worker_id: str | None = None,
    batch_size: int = 1,
    lock_ttl_seconds: int = 120,
) -> dict[str, Any]:
    wid = build_worker_id(worker_id)
    async with async_session() as db:
        claimed_ids = await claim_next_visual_pipeline_runs(
            db,
            worker_id=wid,
            lock_ttl_seconds=lock_ttl_seconds,
            batch_size=batch_size,
        )
    results: list[dict[str, Any]] = []
    for run_id in claimed_ids:
        async with async_session() as db:
            results.append(
                await execute_claimed_visual_pipeline_run(db, run_id, worker_id=wid)
            )
    return {
        "worker_id": wid,
        "claimed": len(claimed_ids),
        "executed": len(results),
        "results": results,
    }


async def run_worker_loop(
    *,
    worker_id: str | None = None,
    poll_interval_seconds: int = 5,
    batch_size: int = 1,
    lock_ttl_seconds: int = 120,
    max_iterations: int | None = None,
    should_stop: Callable[[], bool] | None = None,
) -> None:
    wid = build_worker_id(worker_id)
    iteration = 0
    logger.info(
        "vp-run-worker loop started worker_id=%s poll=%ss batch=%s lock_ttl=%ss",
        wid,
        poll_interval_seconds,
        batch_size,
        lock_ttl_seconds,
    )
    while True:
        if should_stop and should_stop():
            logger.info("vp-run-worker loop stopping worker_id=%s", wid)
            break
        if max_iterations is not None and iteration >= max_iterations:
            logger.info("vp-run-worker loop max_iterations=%s reached", max_iterations)
            break
        iteration += 1
        try:
            summary = await run_worker_once(
                worker_id=wid,
                batch_size=batch_size,
                lock_ttl_seconds=lock_ttl_seconds,
            )
            if summary.get("claimed"):
                logger.info("vp-run-worker tick: %s", summary)
        except Exception:  # noqa: BLE001 — continue loop unless fatal stop
            logger.exception("vp-run-worker tick failed worker_id=%s", wid)
        if should_stop and should_stop():
            break
        await asyncio.sleep(max(1, int(poll_interval_seconds)))
