from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.response import ok
from app.models.entities import ModelVersion
from app.schemas.api import ChampionRequest, ModelStatusUpdate

router = APIRouter(prefix="/models", tags=["Model"])


def _model_dict(m: ModelVersion) -> dict:
    metrics = m.metric_summary_json or {}
    return {
        "model_version_id": m.model_version_id,
        "model_name": m.model_name,
        "version": m.version_no,
        "model_stage": m.model_stage,
        "mlflow_model_uri": m.mlflow_model_uri,
        "metrics": metrics,
        "registered_at": m.registered_at.isoformat(),
    }


@router.get("")
async def list_models(db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(select(ModelVersion).order_by(ModelVersion.registered_at.desc()))).scalars().all()
    names = sorted({r.model_name for r in rows})
    return ok([
        {
            "model_name": name,
            "latest_version": next((r.version_no for r in rows if r.model_name == name), None),
            "champion_version": next((r.version_no for r in rows if r.model_name == name and r.model_stage == "CHAMPION"), None),
            "version_count": sum(1 for r in rows if r.model_name == name),
        }
        for name in names
    ])


@router.get("/{model_name}/versions")
async def list_model_versions(model_name: str, db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(
        select(ModelVersion).where(ModelVersion.model_name == model_name).order_by(ModelVersion.registered_at.desc())
    )).scalars().all()
    if not rows:
        raise HTTPException(status_code=404, detail="NOT_FOUND")
    return ok([_model_dict(r) for r in rows])


@router.get("/{model_name}/versions/{version}")
async def get_model_version(model_name: str, version: str, db: AsyncSession = Depends(get_db)):
    m = (await db.execute(
        select(ModelVersion).where(ModelVersion.model_name == model_name, ModelVersion.version_no == version)
    )).scalar_one_or_none()
    if not m:
        raise HTTPException(status_code=404, detail="NOT_FOUND")
    return ok(_model_dict(m))


@router.post("/{model_name}/versions/{version}/champion")
async def set_champion(model_name: str, version: str, body: ChampionRequest, db: AsyncSession = Depends(get_db)):
    target = (await db.execute(
        select(ModelVersion).where(ModelVersion.model_name == model_name, ModelVersion.version_no == version)
    )).scalar_one_or_none()
    if not target:
        raise HTTPException(status_code=404, detail="NOT_FOUND")

    prev = (await db.execute(
        select(ModelVersion).where(ModelVersion.model_name == model_name, ModelVersion.model_stage == "CHAMPION")
    )).scalar_one_or_none()
    prev_version = prev.version_no if prev else None
    if prev:
        prev.model_stage = "CANDIDATE"
    target.model_stage = "CHAMPION"

    return ok({
        "model_name": model_name,
        "champion_version": version,
        "previous_champion_version": prev_version,
    }, message="Champion 모델이 변경되었습니다.")


@router.patch("/{model_name}/versions/{version}/status")
async def update_model_status(
    model_name: str, version: str, body: ModelStatusUpdate, db: AsyncSession = Depends(get_db)
):
    m = (await db.execute(
        select(ModelVersion).where(ModelVersion.model_name == model_name, ModelVersion.version_no == version)
    )).scalar_one_or_none()
    if not m:
        raise HTTPException(status_code=404, detail="NOT_FOUND")
    m.model_stage = body.model_stage
    return ok({"model_name": model_name, "version": version, "model_stage": body.model_stage})
