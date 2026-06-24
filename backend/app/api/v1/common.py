from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.response import ok
from app.models.entities import CommonCode, Site

router = APIRouter(tags=["Common"])


@router.get("/codes")
async def get_codes(
    code_group: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    q = select(CommonCode).where(CommonCode.active_yn == "Y")
    if code_group:
        q = q.where(CommonCode.code_group == code_group)
    q = q.order_by(CommonCode.code_group, CommonCode.sort_order)
    rows = (await db.execute(q)).scalars().all()
    return ok([
        {"code_group": r.code_group, "code": r.code, "code_name": r.code_name}
        for r in rows
    ])


@router.get("/sites")
async def get_sites(db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(select(Site).where(Site.active_yn == "Y"))).scalars().all()
    return ok([
        {"site_id": r.site_id, "site_name": r.site_name, "site_type": r.site_type}
        for r in rows
    ])
