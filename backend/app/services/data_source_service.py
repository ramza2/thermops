"""데이터 소스 삭제·의존성 검사."""

from __future__ import annotations

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entities import DataMapping, DataSource, FeatureColumnRole, FeatureRecipe


async def get_data_source_delete_blockers(
    db: AsyncSession,
    source_id: str,
) -> list[dict[str, Any]]:
    blockers: list[dict[str, Any]] = []

    mappings = (
        await db.execute(select(DataMapping).where(DataMapping.source_id == source_id))
    ).scalars().all()
    if mappings:
        blockers.append({
            "code": "MAPPING_REFERENCES",
            "count": len(mappings),
            "message": f"연결된 데이터 매핑이 {len(mappings)}건 있어 삭제할 수 없습니다.",
            "items": [{"mapping_id": m.mapping_id, "mapping_name": m.mapping_name} for m in mappings],
        })

    role_count = (
        await db.execute(
            select(func.count()).select_from(FeatureColumnRole).where(
                FeatureColumnRole.data_source_id == source_id,
                FeatureColumnRole.active_yn == "Y",
            )
        )
    ).scalar_one()
    if role_count:
        blockers.append({
            "code": "COLUMN_ROLE_REFERENCES",
            "count": int(role_count),
            "message": f"연결된 Column Role이 {int(role_count)}건 있어 삭제할 수 없습니다.",
        })

    recipe_count = (
        await db.execute(
            select(func.count()).select_from(FeatureRecipe).where(
                FeatureRecipe.data_source_id == source_id,
                FeatureRecipe.active_yn == "Y",
            )
        )
    ).scalar_one()
    if recipe_count:
        blockers.append({
            "code": "FEATURE_RECIPE_REFERENCES",
            "count": int(recipe_count),
            "message": f"연결된 Feature Recipe가 {int(recipe_count)}건 있어 삭제할 수 없습니다.",
        })

    return blockers


async def delete_data_source(db: AsyncSession, source_id: str) -> None:
    s = (
        await db.execute(select(DataSource).where(DataSource.data_source_id == source_id))
    ).scalar_one_or_none()
    if not s:
        raise LookupError("NOT_FOUND")

    blockers = await get_data_source_delete_blockers(db, source_id)
    if blockers:
        raise ValueError(blockers)

    await db.delete(s)
