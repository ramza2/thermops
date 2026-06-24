from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import io
import csv

from app.core.database import get_db
from app.core.response import accepted, ok, paged
from app.models.entities import HeatDemandActual, HeatDemandPrediction, ModelVersion, PipelineRun, PredictionJob
from app.schemas.api import PredictionJobCreate

router = APIRouter(tags=["Prediction"])


@router.post("/prediction-jobs")
async def create_prediction_job(body: PredictionJobCreate, db: AsyncSession = Depends(get_db)):
    champion = None
    if body.model_name and body.model_version:
        champion = (await db.execute(
            select(ModelVersion).where(
                ModelVersion.model_name == body.model_name,
                ModelVersion.version_no == body.model_version,
            )
        )).scalar_one_or_none()
    else:
        champion = (await db.execute(
            select(ModelVersion).where(ModelVersion.model_stage == "CHAMPION").limit(1)
        )).scalar_one_or_none()

    if not champion:
        raise HTTPException(status_code=404, detail="Champion 모델이 지정되지 않았습니다.")

    job_id = f"PRJ-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{uuid4().hex[:6].upper()}"
    run_id = f"AIRFLOW-RUN-{uuid4().hex[:6].upper()}"
    now = datetime.now(timezone.utc)

    pipeline = PipelineRun(
        pipeline_run_id=run_id,
        pipeline_id="batch_prediction_dag",
        pipeline_name="batch_prediction_dag",
        pipeline_type="PREDICTION",
        orchestrator="AIRFLOW",
        run_status="RUNNING",
        started_at=now,
    )
    job = PredictionJob(
        prediction_job_id=job_id,
        pipeline_run_id=run_id,
        model_version_id=champion.model_version_id,
        prediction_horizon=body.prediction_horizon,
        target_start_at=body.target_start_at,
        target_end_at=body.target_end_at,
        site_ids=body.site_ids,
        job_status="RUNNING",
        created_at=now,
    )
    db.add(pipeline)
    db.add(job)
    return accepted({"job_id": job_id, "pipeline_run_id": run_id, "status": "RUNNING"}, message="배치 예측이 실행 요청되었습니다.")


@router.get("/prediction-jobs/{job_id}")
async def get_prediction_job(job_id: str, db: AsyncSession = Depends(get_db)):
    j = (await db.execute(select(PredictionJob).where(PredictionJob.prediction_job_id == job_id))).scalar_one_or_none()
    if not j:
        raise HTTPException(status_code=404, detail="NOT_FOUND")
    return ok({
        "job_id": j.prediction_job_id,
        "status": j.job_status,
        "prediction_horizon": j.prediction_horizon,
        "target_start_at": j.target_start_at.isoformat(),
        "target_end_at": j.target_end_at.isoformat(),
        "created_at": j.created_at.isoformat(),
        "finished_at": j.finished_at.isoformat() if j.finished_at else None,
    })


@router.get("/predictions")
async def list_predictions(
    site_id: str | None = Query(default=None),
    from_dt: datetime | None = Query(default=None, alias="from"),
    to_dt: datetime | None = Query(default=None, alias="to"),
    model_name: str | None = Query(default=None),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    q = select(HeatDemandPrediction).order_by(HeatDemandPrediction.target_at.desc())
    if site_id:
        q = q.where(HeatDemandPrediction.site_id == site_id)
    if from_dt:
        q = q.where(HeatDemandPrediction.target_at >= from_dt)
    if to_dt:
        q = q.where(HeatDemandPrediction.target_at <= to_dt)

    rows = (await db.execute(q)).scalars().all()
    items = []
    for p in rows:
        actual = None
        if site_id or p.site_id:
            sid = site_id or p.site_id
            a = (await db.execute(
                select(HeatDemandActual).where(
                    HeatDemandActual.site_id == sid,
                    HeatDemandActual.measured_at == p.target_at,
                )
            )).scalar_one_or_none()
            actual = float(a.heat_demand) if a else None

        pred_val = float(p.predicted_demand)
        mv = (await db.execute(
            select(ModelVersion).where(ModelVersion.model_version_id == p.model_version_id)
        )).scalar_one_or_none()

        items.append({
            "site_id": p.site_id,
            "target_at": p.target_at.isoformat(),
            "predicted_demand": pred_val,
            "actual_demand": actual,
            "absolute_error": round(abs(pred_val - actual), 2) if actual else None,
            "model_name": mv.model_name if mv else None,
            "model_version": mv.version_no if mv else None,
        })

    start = (page - 1) * size
    return paged(items[start:start + size], page, size, len(items))


@router.get("/predictions/summary")
async def predictions_summary(
    site_id: str = Query(default="SITE-001"),
    db: AsyncSession = Depends(get_db),
):
    preds = (await db.execute(
        select(HeatDemandPrediction).where(HeatDemandPrediction.site_id == site_id).limit(24)
    )).scalars().all()
    total = len(preds)
    avg_pred = sum(float(p.predicted_demand) for p in preds) / total if total else 0
    return ok({
        "site_id": site_id,
        "count": total,
        "avg_predicted_demand": round(avg_pred, 2),
        "horizon": "D_PLUS_1",
    })


@router.get("/predictions/export")
async def export_predictions(site_id: str = Query(default="SITE-001"), db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(
        select(HeatDemandPrediction).where(HeatDemandPrediction.site_id == site_id).limit(100)
    )).scalars().all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["site_id", "target_at", "predicted_demand"])
    for r in rows:
        writer.writerow([r.site_id, r.target_at.isoformat(), float(r.predicted_demand)])

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=predictions.csv"},
    )
