"""예측 추이(trend) 조회 서비스 — 실제 매칭/예측 데이터만 사용."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entities import HeatDemandPrediction, ModelVersion, PredictionActualMatch

DATA_SOURCE_MATCHED = "MATCHED"
DATA_SOURCE_PREDICTION_ONLY = "PREDICTION_ONLY"
DATA_SOURCE_EMPTY = "EMPTY"


@dataclass
class TrendParams:
    site_id: str | None = None
    model_version_id: str | None = None
    model_name: str | None = None
    start_at: datetime | None = None
    end_at: datetime | None = None
    limit: int = 168
    aggregation: str = "HOURLY"


def _time_label(dt: datetime) -> str:
    return dt.strftime("%m-%d %H:%M")


def _trend_item(
    target_at: datetime,
    predicted: float,
    actual: float | None,
    abs_error: float | None,
    ape: float | None,
    site_id: str,
    model_version_id: str | None,
) -> dict[str, Any]:
    return {
        "target_at": target_at.isoformat(),
        "timestamp": target_at.isoformat(),
        "time": _time_label(target_at),
        "predicted_demand": predicted,
        "predicted": predicted,
        "actual_demand": actual,
        "actual": actual,
        "error": abs_error,
        "ape": ape,
        "mape": ape,
        "site_id": site_id,
        "model_version_id": model_version_id,
    }


async def _resolve_model_version_id(
    db: AsyncSession,
    model_version_id: str | None,
    model_name: str | None,
) -> str | None:
    if model_version_id:
        return model_version_id
    if not model_name:
        return None
    mv = (
        await db.execute(
            select(ModelVersion)
            .where(ModelVersion.model_name == model_name)
            .order_by(ModelVersion.registered_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    return mv.model_version_id if mv else None


async def get_prediction_trend(db: AsyncSession, params: TrendParams) -> dict[str, Any]:
    mv_id = await _resolve_model_version_id(db, params.model_version_id, params.model_name)
    limit = max(1, min(params.limit, 2000))

    match_clauses = []
    if params.site_id:
        match_clauses.append(PredictionActualMatch.site_id == params.site_id)
    if mv_id:
        match_clauses.append(PredictionActualMatch.model_version_id == mv_id)
    if params.start_at:
        match_clauses.append(PredictionActualMatch.target_at >= params.start_at)
    if params.end_at:
        match_clauses.append(PredictionActualMatch.target_at <= params.end_at)

    match_q = select(PredictionActualMatch).order_by(PredictionActualMatch.target_at)
    if match_clauses:
        match_q = match_q.where(and_(*match_clauses))
    match_rows = list((await db.execute(match_q.limit(limit))).scalars().all())

    if match_rows:
        items = [
            _trend_item(
                target_at=r.target_at,
                predicted=float(r.predicted_demand),
                actual=float(r.actual_demand),
                abs_error=float(r.abs_error) if r.abs_error is not None else None,
                ape=float(r.ape) if r.ape is not None else None,
                site_id=r.site_id,
                model_version_id=r.model_version_id,
            )
            for r in match_rows
        ]
        return {
            "data_source": DATA_SOURCE_MATCHED,
            "items": items,
            "count": len(items),
        }

    pred_clauses = []
    if params.site_id:
        pred_clauses.append(HeatDemandPrediction.site_id == params.site_id)
    if mv_id:
        pred_clauses.append(HeatDemandPrediction.model_version_id == mv_id)
    if params.start_at:
        pred_clauses.append(HeatDemandPrediction.target_at >= params.start_at)
    if params.end_at:
        pred_clauses.append(HeatDemandPrediction.target_at <= params.end_at)

    pred_q = select(HeatDemandPrediction).order_by(HeatDemandPrediction.target_at)
    if pred_clauses:
        pred_q = pred_q.where(and_(*pred_clauses))
    pred_rows = list((await db.execute(pred_q.limit(limit))).scalars().all())

    if pred_rows:
        items = [
            _trend_item(
                target_at=p.target_at,
                predicted=float(p.predicted_demand),
                actual=None,
                abs_error=None,
                ape=None,
                site_id=p.site_id,
                model_version_id=p.model_version_id,
            )
            for p in pred_rows
        ]
        return {
            "data_source": DATA_SOURCE_PREDICTION_ONLY,
            "items": items,
            "count": len(items),
        }

    return {
        "data_source": DATA_SOURCE_EMPTY,
        "items": [],
        "count": 0,
    }
