from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.response import ok, paged
from app.models.entities import Feature, FeatureSet
from app.schemas.api import FeatureCreate, FeatureSetCreate

router = APIRouter(tags=["Feature"])


@router.get("/features")
async def list_features(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    rows = (await db.execute(select(Feature).order_by(Feature.feature_name))).scalars().all()
    items = [
        {
            "feature_id": r.feature_id,
            "feature_name": r.feature_name,
            "feature_group": r.feature_group,
            "feature_type": r.feature_type,
            "calc_expression": r.calc_expression,
            "status": r.status,
            "description": r.description,
        }
        for r in rows
    ]
    start = (page - 1) * size
    return paged(items[start:start + size], page, size, len(items))


@router.post("/features")
async def create_feature(body: FeatureCreate, db: AsyncSession = Depends(get_db)):
    fid = f"FEAT-{uuid4().hex[:6].upper()}"
    f = Feature(
        feature_id=fid,
        feature_name=body.feature_name,
        feature_group=body.feature_group,
        feature_type=body.feature_type,
        calc_expression=body.calc_expression,
        status="ACTIVE",
        description=body.description,
        created_at=datetime.now(timezone.utc),
    )
    db.add(f)
    return ok({"feature_id": fid}, message="Feature가 등록되었습니다.")


@router.put("/features/{feature_id}")
async def update_feature(feature_id: str, body: FeatureCreate, db: AsyncSession = Depends(get_db)):
    f = (await db.execute(select(Feature).where(Feature.feature_id == feature_id))).scalar_one_or_none()
    if not f:
        raise HTTPException(status_code=404, detail="NOT_FOUND")
    f.feature_name = body.feature_name
    f.feature_group = body.feature_group
    f.feature_type = body.feature_type
    f.calc_expression = body.calc_expression
    f.description = body.description
    return ok({"feature_id": feature_id}, message="Feature가 수정되었습니다.")


@router.delete("/features/{feature_id}")
async def delete_feature(feature_id: str, db: AsyncSession = Depends(get_db)):
    f = (await db.execute(select(Feature).where(Feature.feature_id == feature_id))).scalar_one_or_none()
    if not f:
        raise HTTPException(status_code=404, detail="NOT_FOUND")
    await db.delete(f)
    return ok(message="Feature가 삭제되었습니다.")


@router.get("/feature-sets")
async def list_feature_sets(db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(select(FeatureSet).order_by(FeatureSet.created_at.desc()))).scalars().all()
    return ok([
        {
            "feature_set_id": r.feature_set_id,
            "feature_set_name": r.feature_set_name,
            "target_domain": r.target_domain,
            "features": r.features or [],
            "apply_site_scope": r.apply_site_scope,
            "description": r.description,
        }
        for r in rows
    ])


@router.post("/feature-sets")
async def create_feature_set(body: FeatureSetCreate, db: AsyncSession = Depends(get_db)):
    fsid = f"FS-{uuid4().hex[:6].upper()}"
    fs = FeatureSet(
        feature_set_id=fsid,
        feature_set_name=body.feature_set_name,
        target_domain=body.target_domain,
        features=body.features,
        apply_site_scope=body.apply_site_scope,
        description=body.description,
        active_yn="Y",
        created_at=datetime.now(timezone.utc),
    )
    db.add(fs)
    return ok({"feature_set_id": fsid}, message="Feature Set이 등록되었습니다.")


@router.get("/feature-sets/{feature_set_id}")
async def get_feature_set(feature_set_id: str, db: AsyncSession = Depends(get_db)):
    fs = (await db.execute(select(FeatureSet).where(FeatureSet.feature_set_id == feature_set_id))).scalar_one_or_none()
    if not fs:
        raise HTTPException(status_code=404, detail="NOT_FOUND")
    return ok({
        "feature_set_id": fs.feature_set_id,
        "feature_set_name": fs.feature_set_name,
        "target_domain": fs.target_domain,
        "features": fs.features or [],
        "apply_site_scope": fs.apply_site_scope,
        "description": fs.description,
    })


@router.delete("/feature-sets/{feature_set_id}")
async def delete_feature_set(feature_set_id: str, db: AsyncSession = Depends(get_db)):
    fs = (await db.execute(select(FeatureSet).where(FeatureSet.feature_set_id == feature_set_id))).scalar_one_or_none()
    if not fs:
        raise HTTPException(status_code=404, detail="NOT_FOUND")
    await db.delete(fs)
    return ok(message="Feature Set이 삭제되었습니다.")


@router.put("/feature-sets/{feature_set_id}")
async def update_feature_set(feature_set_id: str, body: FeatureSetCreate, db: AsyncSession = Depends(get_db)):
    fs = (await db.execute(select(FeatureSet).where(FeatureSet.feature_set_id == feature_set_id))).scalar_one_or_none()
    if not fs:
        raise HTTPException(status_code=404, detail="NOT_FOUND")
    fs.feature_set_name = body.feature_set_name
    fs.features = body.features
    fs.apply_site_scope = body.apply_site_scope
    fs.description = body.description
    return ok({"feature_set_id": feature_set_id}, message="Feature Set이 수정되었습니다.")


@router.post("/feature-sets/{feature_set_id}/preview")
async def preview_feature_set(feature_set_id: str, db: AsyncSession = Depends(get_db)):
    fs = (await db.execute(select(FeatureSet).where(FeatureSet.feature_set_id == feature_set_id))).scalar_one_or_none()
    if not fs:
        raise HTTPException(status_code=404, detail="NOT_FOUND")
    return ok({
        "feature_set_id": feature_set_id,
        "preview": [
            {"feature_at": "2026-06-24T01:00:00", "temperature": -2.5, "humidity": 65.0, "lag_24h": 120.5},
            {"feature_at": "2026-06-24T02:00:00", "temperature": -3.1, "humidity": 68.0, "lag_24h": 115.2},
        ],
    })
