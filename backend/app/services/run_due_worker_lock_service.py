"""Run-due worker 분산 잠금 (R10-S10)."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.time import utc_now
from app.models.entities import RunDueWorkerLock

DEFAULT_LOCK_KEY = "run-due-global"


def _lock_dict(row: RunDueWorkerLock) -> dict[str, Any]:
    return {
        "lock_key": row.lock_key,
        "owner_instance_id": row.owner_instance_id,
        "acquired_at": row.acquired_at.isoformat() if row.acquired_at else None,
        "expires_at": row.expires_at.isoformat() if row.expires_at else None,
        "heartbeat_at": row.heartbeat_at.isoformat() if row.heartbeat_at else None,
        "metadata_json": row.metadata_json,
    }


async def list_locks(db: AsyncSession) -> list[dict[str, Any]]:
    rows = (await db.execute(select(RunDueWorkerLock).order_by(RunDueWorkerLock.lock_key))).scalars().all()
    return [_lock_dict(r) for r in rows]


async def try_acquire_lock(
    db: AsyncSession,
    *,
    owner_instance_id: str,
    lock_key: str = DEFAULT_LOCK_KEY,
    ttl_seconds: int = 120,
) -> bool:
    now = utc_now()
    expires = now + timedelta(seconds=ttl_seconds)
    row = (
        await db.execute(select(RunDueWorkerLock).where(RunDueWorkerLock.lock_key == lock_key))
    ).scalar_one_or_none()
    if row is None:
        db.add(
            RunDueWorkerLock(
                lock_key=lock_key,
                owner_instance_id=owner_instance_id,
                acquired_at=now,
                expires_at=expires,
                heartbeat_at=now,
            )
        )
        await db.flush()
        return True
    if row.expires_at <= now or row.owner_instance_id == owner_instance_id:
        row.owner_instance_id = owner_instance_id
        row.acquired_at = now
        row.expires_at = expires
        row.heartbeat_at = now
        await db.flush()
        return True
    return False


async def extend_lock(
    db: AsyncSession,
    *,
    owner_instance_id: str,
    lock_key: str = DEFAULT_LOCK_KEY,
    ttl_seconds: int = 120,
) -> bool:
    now = utc_now()
    row = (
        await db.execute(select(RunDueWorkerLock).where(RunDueWorkerLock.lock_key == lock_key))
    ).scalar_one_or_none()
    if row is None or row.owner_instance_id != owner_instance_id:
        return False
    row.expires_at = now + timedelta(seconds=ttl_seconds)
    row.heartbeat_at = now
    await db.flush()
    return True


async def release_lock(
    db: AsyncSession,
    *,
    owner_instance_id: str,
    lock_key: str = DEFAULT_LOCK_KEY,
) -> bool:
    row = (
        await db.execute(select(RunDueWorkerLock).where(RunDueWorkerLock.lock_key == lock_key))
    ).scalar_one_or_none()
    if row is None:
        return True
    if row.owner_instance_id != owner_instance_id:
        return False
    await db.delete(row)
    await db.flush()
    return True
