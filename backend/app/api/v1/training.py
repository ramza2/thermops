from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.response import accepted, ok, paged
from app.models.entities import PipelineRun, TrainingConfig, TrainingJob
from app.schemas.api import TrainingConfigCreate, TrainingJobCreate

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
        created_at=datetime.now(timezone.utc),
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
    job_id = f"TRJ-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{uuid4().hex[:6].upper()}"
    run_id = f"AIRFLOW-RUN-{uuid4().hex[:6].upper()}"
    now = datetime.now(timezone.utc)

    pipeline = PipelineRun(
        pipeline_run_id=run_id,
        pipeline_id="model_training_dag",
        pipeline_name="model_training_dag",
        pipeline_type="TRAINING",
        orchestrator="AIRFLOW",
        run_status="RUNNING",
        started_at=now,
        message="모델 학습 파이프라인 실행 중",
    )
    job = TrainingJob(
        job_id=job_id,
        config_id=body.config_id,
        pipeline_run_id=run_id,
        status="RUNNING",
        site_ids=body.site_ids,
        train_start_at=body.train_start_at,
        train_end_at=body.train_end_at,
        validation_start_at=body.validation_start_at,
        validation_end_at=body.validation_end_at,
        started_at=now,
        created_at=now,
    )
    db.add(pipeline)
    db.add(job)
    return accepted({
        "job_id": job_id,
        "pipeline_run_id": run_id,
        "status": "RUNNING",
    }, message="모델 학습 파이프라인이 실행 요청되었습니다.")


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
async def get_training_job(job_id: str, db: AsyncSession = Depends(get_db)):
    j = (await db.execute(select(TrainingJob).where(TrainingJob.job_id == job_id))).scalar_one_or_none()
    if not j:
        raise HTTPException(status_code=404, detail="NOT_FOUND")
    return ok(_job_dict(j))


@router.post("/training-jobs/{job_id}/cancel")
async def cancel_training_job(job_id: str, db: AsyncSession = Depends(get_db)):
    j = (await db.execute(select(TrainingJob).where(TrainingJob.job_id == job_id))).scalar_one_or_none()
    if not j:
        raise HTTPException(status_code=404, detail="NOT_FOUND")
    if j.status not in ("RUNNING", "READY"):
        raise HTTPException(status_code=409, detail="CONFLICT")
    j.status = "CANCELED"
    j.ended_at = datetime.now(timezone.utc)
    return ok({"job_id": job_id, "status": "CANCELED"}, message="학습 작업이 취소되었습니다.")


def _job_dict(j: TrainingJob) -> dict:
    config = None
    return {
        "job_id": j.job_id,
        "config_id": j.config_id,
        "status": j.status,
        "pipeline_run_id": j.pipeline_run_id,
        "site_ids": j.site_ids,
        "mlflow_run_id": j.mlflow_run_id,
        "registered_model_name": j.registered_model_name,
        "registered_model_version": j.registered_model_version,
        "metrics": j.metrics,
        "started_at": j.started_at.isoformat() if j.started_at else None,
        "ended_at": j.ended_at.isoformat() if j.ended_at else None,
    }
