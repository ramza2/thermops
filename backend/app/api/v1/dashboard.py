from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.response import accepted, ok, paged
from app.models.entities import (
    DriftReport,
    ModelPerformanceMetric,
    ModelVersion,
    PipelineRun,
    PredictionJob,
    RetrainingCandidate,
    Site,
    TrainingJob,
)
from app.services.prediction_evaluation_service import EVAL_TYPE_PREDICTION, get_prediction_performance_avg_mape
from app.services.prediction_trend_service import TrendParams, get_prediction_trend

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get("/overview")
async def dashboard_overview(db: AsyncSession = Depends(get_db)):
    champion = (await db.execute(
        select(ModelVersion).where(ModelVersion.model_stage == "CHAMPION").limit(1)
    )).scalar_one_or_none()

    failed_count = (await db.execute(
        select(func.count()).select_from(PipelineRun).where(PipelineRun.run_status == "FAILED")
    )).scalar() or 0

    retrain_count = (await db.execute(
        select(func.count()).select_from(RetrainingCandidate).where(RetrainingCandidate.status == "REVIEW")
    )).scalar() or 0

    avg_mape = await get_prediction_performance_avg_mape(db, days=7)
    if avg_mape is None:
        avg_mape = (await db.execute(
            select(func.avg(ModelPerformanceMetric.mape)).where(
                ModelPerformanceMetric.metric_json["eval_type"].astext == "PREDICTION_ACTUAL_MATCH"
            )
        )).scalar()

    latest_pred = (await db.execute(
        select(PredictionJob).order_by(PredictionJob.created_at.desc()).limit(1)
    )).scalar_one_or_none()

    return ok({
        "prediction_status": latest_pred.job_status if latest_pred else "READY",
        "latest_prediction_at": latest_pred.created_at.isoformat() if latest_pred else None,
        "avg_mape_7d": round(float(avg_mape), 2) if avg_mape is not None else None,
        "prediction_accuracy": round(100 - float(avg_mape), 2) if avg_mape is not None else None,
        "champion_model": {
            "model_name": champion.model_name,
            "version": champion.version_no,
        } if champion else None,
        "failed_pipeline_count": failed_count,
        "retraining_candidate_count": retrain_count,
    })


@router.get("/prediction-trend")
async def prediction_trend(
    site_id: str | None = Query(default=None),
    model_version_id: str | None = Query(default=None),
    model_name: str | None = Query(default=None),
    start_at: datetime | None = Query(default=None),
    end_at: datetime | None = Query(default=None),
    limit: int = Query(default=168, ge=1, le=2000),
    aggregation: str = Query(default="HOURLY"),
    db: AsyncSession = Depends(get_db),
):
    params = TrendParams(
        site_id=site_id,
        model_version_id=model_version_id,
        model_name=model_name,
        start_at=start_at,
        end_at=end_at,
        limit=limit,
        aggregation=aggregation,
    )
    result = await get_prediction_trend(db, params)
    return ok(result)


@router.get("/model-health")
async def model_health(db: AsyncSession = Depends(get_db)):
    models = (await db.execute(select(ModelVersion).order_by(ModelVersion.registered_at.desc()))).scalars().all()

    op_rows = (
        await db.execute(
            select(ModelPerformanceMetric).where(
                ModelPerformanceMetric.metric_json["eval_type"].astext == EVAL_TYPE_PREDICTION,
            )
        )
    ).scalars().all()
    op_mape_by_mv: dict[str, list[float]] = {}
    for r in op_rows:
        if r.mape is not None:
            op_mape_by_mv.setdefault(r.model_version_id, []).append(float(r.mape))

    items = []
    for m in models:
        op_mapes = op_mape_by_mv.get(m.model_version_id, [])
        training_mape = m.metric_summary_json.get("mape") if m.metric_summary_json else None

        if op_mapes:
            mape = round(sum(op_mapes) / len(op_mapes), 4)
            mape_source = "OPERATIONAL"
        elif training_mape is not None:
            mape = float(training_mape)
            mape_source = "TRAINING"
        else:
            mape = None
            mape_source = "NONE"

        items.append({
            "model_name": m.model_name,
            "version": m.version_no,
            "stage": m.model_stage,
            "mape": mape,
            "mape_source": mape_source,
            "mape_operational": round(sum(op_mapes) / len(op_mapes), 4) if op_mapes else None,
            "mape_training": float(training_mape) if training_mape is not None else None,
            "registered_at": m.registered_at.isoformat(),
        })
    return ok(items)
