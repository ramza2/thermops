from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import io
import csv

from app.core.database import get_db
from app.core.response import ok, paged
from app.models.entities import HeatDemandPrediction
from app.schemas.api import PredictionEvaluateRequest, PredictionJobCreate
from app.services.prediction_evaluation_service import EvaluateParams, list_prediction_errors, run_prediction_evaluation
from app.services.prediction_service import (
    PredictionModelError,
    get_prediction_job,
    list_predictions_paged,
    params_from_schema,
    predictions_summary_stats,
    run_prediction_job,
)
from app.services.feature_dataset_service import PredictionPeriodError

router = APIRouter(tags=["Prediction"])


@router.post("/prediction-jobs")
async def create_prediction_job(body: PredictionJobCreate, db: AsyncSession = Depends(get_db)):
    try:
        params = params_from_schema(body)
        result = await run_prediction_job(db, params)
    except PredictionModelError as exc:
        raise HTTPException(status_code=400, detail=exc.to_dict()) from exc
    except PredictionPeriodError as exc:
        raise HTTPException(status_code=400, detail=exc.to_dict()) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    if result.get("status") == "FAILED":
        raise HTTPException(status_code=400, detail=result.get("error_message", "배치 예측 실패"))

    msg = f"배치 예측이 완료되었습니다. ({result.get('predicted_count', 0)}건)"
    if result.get("warnings"):
        msg += f" (경고 {len(result['warnings'])}건)"
    return ok(result, message=msg)


@router.get("/prediction-jobs/{job_id}")
async def get_prediction_job_endpoint(job_id: str, db: AsyncSession = Depends(get_db)):
    result = await get_prediction_job(db, job_id)
    if not result:
        raise HTTPException(status_code=404, detail="NOT_FOUND")
    return ok(result)


@router.get("/predictions")
async def list_predictions(
    site_id: str | None = Query(default=None),
    from_dt: datetime | None = Query(default=None, alias="from"),
    to_dt: datetime | None = Query(default=None, alias="to"),
    model_name: str | None = Query(default=None),
    model_version_id: str | None = Query(default=None),
    page: int = Query(1, ge=1),
    size: int | None = Query(default=None, ge=1, le=1000),
    limit: int | None = Query(default=None, ge=1, le=1000),
    db: AsyncSession = Depends(get_db),
):
    page_size = size or limit or 20
    try:
        items, total = await list_predictions_paged(
            db,
            site_id=site_id,
            from_dt=from_dt,
            to_dt=to_dt,
            model_name=model_name,
            model_version_id=model_version_id,
            page=page,
            size=page_size,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"예측 결과 조회 실패: {exc}") from exc
    return paged(items, page, page_size, total)


@router.get("/predictions/summary")
async def predictions_summary(
    site_id: str | None = Query(default=None),
    from_dt: datetime | None = Query(default=None, alias="from"),
    to_dt: datetime | None = Query(default=None, alias="to"),
    model_version_id: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    try:
        data = await predictions_summary_stats(
            db,
            site_id=site_id,
            from_dt=from_dt,
            to_dt=to_dt,
            model_version_id=model_version_id,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"예측 요약 조회 실패: {exc}") from exc
    return ok(data)


@router.post("/predictions/evaluate")
async def evaluate_predictions(body: PredictionEvaluateRequest, db: AsyncSession = Depends(get_db)):
    params = EvaluateParams(
        model_version_id=body.model_version_id,
        prediction_job_id=body.prediction_job_id,
        site_ids=body.site_ids,
        start_at=body.start_at,
        end_at=body.end_at,
    )
    try:
        result = await run_prediction_evaluation(db, params)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return ok(result, message=f"예측 성능 평가 완료 ({result['matched_count']}건 매칭)")


@router.get("/predictions/errors")
async def list_prediction_errors_endpoint(
    site_id: str | None = Query(default=None),
    model_version_id: str | None = Query(default=None),
    from_dt: datetime | None = Query(default=None, alias="from"),
    to_dt: datetime | None = Query(default=None, alias="to"),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    items, total = await list_prediction_errors(
        db,
        site_id=site_id,
        model_version_id=model_version_id,
        start_at=from_dt,
        end_at=to_dt,
        page=page,
        size=size,
    )
    return paged(items, page, size, total)


@router.get("/predictions/export")
async def export_predictions(
    site_id: str = Query(default="SITE-001"),
    model_version_id: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    q = select(HeatDemandPrediction).where(HeatDemandPrediction.site_id == site_id)
    if model_version_id:
        q = q.where(HeatDemandPrediction.model_version_id == model_version_id)
    rows = (await db.execute(q.order_by(HeatDemandPrediction.target_at).limit(1000))).scalars().all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["site_id", "target_at", "predicted_demand", "model_version_id", "feature_set_id"])
    for r in rows:
        writer.writerow([
            r.site_id,
            r.target_at.isoformat(),
            float(r.predicted_demand),
            r.model_version_id,
            r.feature_set_id or "",
        ])

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=predictions.csv"},
    )
