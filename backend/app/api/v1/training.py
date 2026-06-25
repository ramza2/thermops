from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.response import ok, paged
from app.core.time import utc_now
from app.models.entities import TrainingConfig, TrainingJob
from app.schemas.api import TrainingConfigCreate, TrainingJobCreate
from app.services.training_service import (
    _job_dict,
    get_training_job,
    params_from_schema,
    run_training_job,
)

router = APIRouter(tags=["Training"])


@router.get("/training-configs")
async def list_training_configs(db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(select(TrainingConfig).order_by(TrainingConfig.created_at.desc()))).scalars().all()
    return ok([
        {
            "config_id": r.config_id,
            "config_name": r.config_name,
            "feature_set_id": r.feature_set_id,
            "algorithm": r.algorithm,
            "train_period_months": r.train_period_months,
            "validation_period_months": r.validation_period_months,
            "hyperparams": r.hyperparams,
            "active_yn": r.active_yn == "Y",
        }
        for r in rows
    ])


@router.post("/training-configs")
async def create_training_config(body: TrainingConfigCreate, db: AsyncSession = Depends(get_db)):
    cid = f"TRC-{uuid4().hex[:6].upper()}"
    c = TrainingConfig(
        config_id=cid,
        config_name=body.config_name,
        feature_set_id=body.feature_set_id,
        algorithm=body.algorithm,
        train_period_months=body.train_period_months,
        validation_period_months=body.validation_period_months,
        hyperparams=body.hyperparams,
        active_yn="Y",
        created_at=utc_now(),
    )
    db.add(c)
    return ok({"config_id": cid}, message="학습 설정이 등록되었습니다.")


@router.put("/training-configs/{config_id}")
async def update_training_config(config_id: str, body: TrainingConfigCreate, db: AsyncSession = Depends(get_db)):
    c = (await db.execute(select(TrainingConfig).where(TrainingConfig.config_id == config_id))).scalar_one_or_none()
    if not c:
        raise HTTPException(status_code=404, detail="NOT_FOUND")
    c.config_name = body.config_name
    c.feature_set_id = body.feature_set_id
    c.algorithm = body.algorithm
    c.hyperparams = body.hyperparams
    return ok({"config_id": config_id}, message="학습 설정이 수정되었습니다.")


@router.post("/training-jobs")
async def create_training_job(body: TrainingJobCreate, db: AsyncSession = Depends(get_db)):
    try:
        result = await run_training_job(db, params_from_schema(body))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    if result.get("status") == "FAILED":
        raise HTTPException(status_code=400, detail=result.get("error_message", "모델 학습 실패"))

    msg = "모델 학습이 완료되었습니다."
    if result.get("warnings"):
        msg += f" (경고 {len(result['warnings'])}건)"
    return ok(result, message=msg)


@router.get("/training-jobs")
async def list_training_jobs(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    rows = (await db.execute(select(TrainingJob).order_by(TrainingJob.created_at.desc()))).scalars().all()
    items = [_job_dict(r) for r in rows]
    start = (page - 1) * size
    return paged(items[start:start + size], page, size, len(items))


@router.get("/training-jobs/{job_id}")
async def get_training_job_endpoint(job_id: str, db: AsyncSession = Depends(get_db)):
    result = await get_training_job(db, job_id)
    if not result:
        raise HTTPException(status_code=404, detail="NOT_FOUND")
    return ok(result)


@router.post("/training-jobs/{job_id}/cancel")
async def cancel_training_job(job_id: str, db: AsyncSession = Depends(get_db)):
    from app.core.time import utc_now

    j = (await db.execute(select(TrainingJob).where(TrainingJob.job_id == job_id))).scalar_one_or_none()
    if not j:
        raise HTTPException(status_code=404, detail="NOT_FOUND")
    if j.status not in ("RUNNING", "READY"):
        raise HTTPException(status_code=409, detail="CONFLICT")
    j.status = "CANCELED"
    j.ended_at = utc_now()
    return ok({"job_id": job_id, "status": "CANCELED"}, message="학습 작업이 취소되었습니다.")
