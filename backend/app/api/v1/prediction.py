from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import io
import csv

from app.core.database import get_db
from app.core.response import ok, paged
from app.models.entities import HeatDemandActual, HeatDemandPrediction, ModelVersion, PredictionActualMatch
from app.schemas.api import PredictionEvaluateRequest, PredictionJobCreate
from app.services.prediction_evaluation_service import EvaluateParams, list_prediction_errors, run_prediction_evaluation
from app.services.prediction_service import (
    get_prediction_job,
    params_from_schema,
    run_prediction_job,
)

router = APIRouter(tags=["Prediction"])


@router.post("/prediction-jobs")
async def create_prediction_job(body: PredictionJobCreate, db: AsyncSession = Depends(get_db)):
    try:
        params = params_from_schema(body)
        result = await run_prediction_job(db, params)
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
    if model_version_id:
        q = q.where(HeatDemandPrediction.model_version_id == model_version_id)

    rows = (await db.execute(q)).scalars().all()

    model_version_ids = {p.model_version_id for p in rows}
    mv_map: dict[str, ModelVersion] = {}
    if model_version_ids:
        mvs = (
            await db.execute(select(ModelVersion).where(ModelVersion.model_version_id.in_(model_version_ids)))
        ).scalars().all()
        mv_map = {m.model_version_id: m for m in mvs}

    if model_name:
        rows = [p for p in rows if mv_map.get(p.model_version_id) and mv_map[p.model_version_id].model_name == model_name]

    items = []
    pred_ids = [p.prediction_id for p in rows]
    match_map: dict[int, PredictionActualMatch] = {}
    if pred_ids:
        matches = (
            await db.execute(
                select(PredictionActualMatch).where(PredictionActualMatch.prediction_id.in_(pred_ids))
            )
        ).scalars().all()
        match_map = {m.prediction_id: m for m in matches}

    for p in rows:
        match = match_map.get(p.prediction_id)
        if match:
            actual = float(match.actual_demand)
            pred_val = float(match.predicted_demand)
            abs_err = float(match.abs_error) if match.abs_error is not None else None
            ape = float(match.ape) if match.ape is not None else None
            error = float(match.error) if match.error is not None else None
        else:
            a = (
                await db.execute(
                    select(HeatDemandActual).where(
                        HeatDemandActual.site_id == p.site_id,
                        HeatDemandActual.measured_at == p.target_at,
                    )
                )
            ).scalar_one_or_none()
            actual = float(a.heat_demand) if a else None
            pred_val = float(p.predicted_demand)
            abs_err = round(abs(pred_val - actual), 2) if actual is not None else None
            ape = round(abs((actual - pred_val) / actual) * 100, 4) if actual and abs(actual) > 1e-8 else None
            error = round(actual - pred_val, 2) if actual is not None else None

        mv = mv_map.get(p.model_version_id)

        items.append({
            "site_id": p.site_id,
            "target_at": p.target_at.isoformat(),
            "predicted_demand": pred_val,
            "actual_demand": actual,
            "error": error,
            "absolute_error": abs_err,
            "ape": ape,
            "model_name": mv.model_name if mv else None,
            "model_version": mv.version_no if mv else None,
            "model_version_id": p.model_version_id,
            "feature_set_id": p.feature_set_id,
        })

    start = (page - 1) * size
    return paged(items[start:start + size], page, size, len(items))


@router.get("/predictions/summary")
async def predictions_summary(
    site_id: str | None = Query(default=None),
    from_dt: datetime | None = Query(default=None, alias="from"),
    to_dt: datetime | None = Query(default=None, alias="to"),
    model_version_id: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    q = select(HeatDemandPrediction)
    if site_id:
        q = q.where(HeatDemandPrediction.site_id == site_id)
    if from_dt:
        q = q.where(HeatDemandPrediction.target_at >= from_dt)
    if to_dt:
        q = q.where(HeatDemandPrediction.target_at <= to_dt)
    if model_version_id:
        q = q.where(HeatDemandPrediction.model_version_id == model_version_id)

    preds = (await db.execute(q.order_by(HeatDemandPrediction.target_at.desc()))).scalars().all()
    total = len(preds)
    avg_pred = sum(float(p.predicted_demand) for p in preds) / total if total else 0

    mv = None
    if model_version_id:
        mv = (
            await db.execute(select(ModelVersion).where(ModelVersion.model_version_id == model_version_id))
        ).scalar_one_or_none()
    elif preds:
        mv = (
            await db.execute(
                select(ModelVersion).where(ModelVersion.model_version_id == preds[0].model_version_id)
            )
        ).scalar_one_or_none()

    period_from = min(p.target_at for p in preds).date().isoformat() if preds else None
    period_to = max(p.target_at for p in preds).date().isoformat() if preds else None

    return ok({
        "site_id": site_id or "ALL",
        "count": total,
        "avg_predicted_demand": round(avg_pred, 2),
        "model_name": mv.model_name if mv else None,
        "model_version": mv.version_no if mv else None,
        "model_version_id": mv.model_version_id if mv else model_version_id,
        "period": {"from": period_from, "to": period_to},
        "horizon": "BATCH",
    })


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
