"""Dataset Version 목록·조회 API 서비스."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entities import DatasetVersion
from app.services.dataset_version_policy_service import (
    dataset_version_to_dict,
    get_dataset_version,
    load_dataset_versions_for_feature_set,
)


async def list_dataset_versions(
    db: AsyncSession,
    *,
    feature_set_id: str | None = None,
    role: str | None = None,
    status: str | None = None,
    build_scope: str | None = None,
    is_primary: bool | None = None,
    training_ready: bool | None = None,
    serving_ready: bool | None = None,
) -> list[dict[str, Any]]:
    q = select(DatasetVersion).order_by(DatasetVersion.created_at.desc())
    if feature_set_id:
        q = q.where(DatasetVersion.feature_set_id == feature_set_id)
    if role:
        q = q.where(DatasetVersion.dataset_version_role == role.upper())
    if status:
        q = q.where(DatasetVersion.dataset_version_status == status.upper())
    if build_scope:
        q = q.where(DatasetVersion.build_scope == build_scope.upper())
    if is_primary is not None:
        q = q.where(DatasetVersion.is_primary.is_(is_primary))
    if training_ready is not None:
        q = q.where(DatasetVersion.is_training_ready.is_(training_ready))
    if serving_ready is not None:
        q = q.where(DatasetVersion.is_serving_ready.is_(serving_ready))
    rows = (await db.execute(q)).scalars().all()
    if rows:
        return [dataset_version_to_dict(r) for r in rows]
    if feature_set_id:
        legacy = await load_dataset_versions_for_feature_set(db, feature_set_id)
        return [dataset_version_to_dict(r) for r in legacy]
    return []


async def get_dataset_version_detail(db: AsyncSession, dataset_version_id: str) -> dict[str, Any] | None:
    dv = await get_dataset_version(db, dataset_version_id)
    if not dv:
        return None
    return dataset_version_to_dict(dv)
