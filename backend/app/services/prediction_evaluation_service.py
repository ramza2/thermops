"""예측값-실제값 매칭 및 운영 성능 평가 서비스."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
from sqlalchemy import and_, delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.time import utc_now
from app.models.entities import (
    HeatDemandActual,
    HeatDemandPrediction,
    ModelPerformanceMetric,
    ModelVersion,
    PredictionActualMatch,
)

EVAL_TYPE_PREDICTION = "PREDICTION_ACTUAL_MATCH"
EVAL_TYPE_TRAINING = "TRAINING_VALIDATION"


@dataclass
class EvaluateParams:
    model_version_id: str | None = None
    prediction_job_id: str | None = None
    site_ids: list[str] | None = None
    start_at: datetime | None = None
    end_at: datetime | None = None


def _load_evaluation_module():
    root = get_settings().project_root
    for candidate in (root / "ml", Path("/ml"), Path(__file__).resolve().parents[3] / "ml"):
        if candidate.exists():
            p = str(candidate.resolve())
            if p not in sys.path:
                sys.path.insert(0, p)
            break
    import evaluation  # noqa: WPS433

    return evaluation


def _compute_row_errors(predicted: float, actual: float) -> dict[str, float | None]:
    error = actual - predicted
    abs_error = abs(error)
    squared_error = error * error
    ape = None
    if actual is not None and abs(actual) > 1e-8:
        ape = abs(error / actual) * 100
    return {
        "error": error,
        "abs_error": abs_error,
        "squared_error": squared_error,
        "ape": ape,
    }


def _aggregate_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict[str, float]:
    eval_mod = _load_evaluation_module()
    base = eval_mod.compute_metrics(y_true, y_pred)
    base["sample_count"] = float(len(y_true))
    base["max_abs_error"] = float(np.max(np.abs(y_true - y_pred))) if len(y_true) else 0.0
    base["avg_actual_demand"] = float(np.mean(y_true)) if len(y_true) else 0.0
    base["avg_predicted_demand"] = float(np.mean(y_pred)) if len(y_pred) else 0.0
    return base


async def _fetch_predictions(
    db: AsyncSession,
    params: EvaluateParams,
) -> list[HeatDemandPrediction]:
    clauses = []
    if params.model_version_id:
        clauses.append(HeatDemandPrediction.model_version_id == params.model_version_id)
    if params.prediction_job_id:
        clauses.append(HeatDemandPrediction.prediction_job_id == params.prediction_job_id)
    if params.site_ids:
        clauses.append(HeatDemandPrediction.site_id.in_(params.site_ids))
    if params.start_at:
        clauses.append(HeatDemandPrediction.target_at >= params.start_at)
    if params.end_at:
        clauses.append(HeatDemandPrediction.target_at <= params.end_at)

    q = select(HeatDemandPrediction).order_by(HeatDemandPrediction.target_at, HeatDemandPrediction.site_id)
    if clauses:
        q = q.where(and_(*clauses))
    return list((await db.execute(q)).scalars().all())


async def run_prediction_evaluation(db: AsyncSession, params: EvaluateParams) -> dict[str, Any]:
    predictions = await _fetch_predictions(db, params)
    if not predictions:
        raise ValueError("평가 대상 예측 데이터가 없습니다.")

    model_version_id = params.model_version_id or predictions[0].model_version_id
    mv = (
        await db.execute(select(ModelVersion).where(ModelVersion.model_version_id == model_version_id))
    ).scalar_one_or_none()

    matched_rows: list[dict[str, Any]] = []
    now = utc_now()

    for pred in predictions:
        actual_row = (
            await db.execute(
                select(HeatDemandActual).where(
                    HeatDemandActual.site_id == pred.site_id,
                    HeatDemandActual.measured_at == pred.target_at,
                )
            )
        ).scalar_one_or_none()
        if not actual_row or actual_row.heat_demand is None:
            continue

        predicted = float(pred.predicted_demand)
        actual = float(actual_row.heat_demand)
        errs = _compute_row_errors(predicted, actual)

        existing = (
            await db.execute(
                select(PredictionActualMatch).where(PredictionActualMatch.prediction_id == pred.prediction_id)
            )
        ).scalar_one_or_none()

        if existing:
            existing.site_id = pred.site_id
            existing.target_at = pred.target_at
            existing.model_version_id = pred.model_version_id
            existing.prediction_job_id = pred.prediction_job_id
            existing.predicted_demand = predicted
            existing.actual_demand = actual
            existing.error = errs["error"]
            existing.abs_error = errs["abs_error"]
            existing.squared_error = errs["squared_error"]
            existing.ape = errs["ape"]
            existing.created_at = now
            match_row = existing
        else:
            await db.execute(
                delete(PredictionActualMatch).where(
                    PredictionActualMatch.site_id == pred.site_id,
                    PredictionActualMatch.target_at == pred.target_at,
                    PredictionActualMatch.model_version_id == pred.model_version_id,
                )
            )
            match_row = PredictionActualMatch(
                prediction_id=pred.prediction_id,
                site_id=pred.site_id,
                target_at=pred.target_at,
                model_version_id=pred.model_version_id,
                prediction_job_id=pred.prediction_job_id,
                predicted_demand=predicted,
                actual_demand=actual,
                error=errs["error"],
                abs_error=errs["abs_error"],
                squared_error=errs["squared_error"],
                ape=errs["ape"],
                created_at=now,
            )
            db.add(match_row)

        matched_rows.append({
            "prediction_id": pred.prediction_id,
            "site_id": pred.site_id,
            "target_at": pred.target_at,
            "predicted_demand": predicted,
            "actual_demand": actual,
            **errs,
        })

    await db.flush()

    if not matched_rows:
        raise ValueError("매칭된 예측-실적 행이 없습니다. site_id와 target_at=measured_at을 확인하세요.")

    eval_start = min(r["target_at"] for r in matched_rows)
    eval_end = max(r["target_at"] for r in matched_rows)

    overall_true = np.array([r["actual_demand"] for r in matched_rows], dtype=float)
    overall_pred = np.array([r["predicted_demand"] for r in matched_rows], dtype=float)
    metric_summary = _aggregate_metrics(overall_true, overall_pred)

    site_metrics: dict[str, dict[str, float]] = {}
    for site_id in sorted({r["site_id"] for r in matched_rows}):
        site_rows = [r for r in matched_rows if r["site_id"] == site_id]
        y_true = np.array([r["actual_demand"] for r in site_rows], dtype=float)
        y_pred = np.array([r["predicted_demand"] for r in site_rows], dtype=float)
        site_metrics[site_id] = _aggregate_metrics(y_true, y_pred)

        await db.execute(
            delete(ModelPerformanceMetric).where(
                ModelPerformanceMetric.site_id == site_id,
                ModelPerformanceMetric.model_version_id == model_version_id,
                ModelPerformanceMetric.metric_json["eval_type"].astext == EVAL_TYPE_PREDICTION,
            )
        )
        sm = site_metrics[site_id]
        db.add(
            ModelPerformanceMetric(
                site_id=site_id,
                model_version_id=model_version_id,
                eval_start_at=eval_start,
                eval_end_at=eval_end,
                mae=sm["mae"],
                rmse=sm["rmse"],
                mape=sm["mape"],
                sample_count=int(sm["sample_count"]),
                metric_json={
                    "eval_type": EVAL_TYPE_PREDICTION,
                    "r2": sm["r2"],
                    "max_abs_error": sm["max_abs_error"],
                    "avg_actual_demand": sm["avg_actual_demand"],
                    "avg_predicted_demand": sm["avg_predicted_demand"],
                    "model_name": mv.model_name if mv else None,
                    "version_no": mv.version_no if mv else None,
                },
                created_at=now,
            )
        )

    await db.flush()

    return {
        "status": "SUCCESS",
        "matched_count": len(matched_rows),
        "model_version_id": model_version_id,
        "model_name": mv.model_name if mv else None,
        "model_version": mv.version_no if mv else None,
        "evaluation_start_at": eval_start.isoformat(),
        "evaluation_end_at": eval_end.isoformat(),
        "metric_summary": {
            "mape": metric_summary["mape"],
            "mae": metric_summary["mae"],
            "rmse": metric_summary["rmse"],
            "r2": metric_summary["r2"],
            "sample_count": int(metric_summary["sample_count"]),
            "max_abs_error": metric_summary["max_abs_error"],
            "avg_actual_demand": metric_summary["avg_actual_demand"],
            "avg_predicted_demand": metric_summary["avg_predicted_demand"],
        },
        "site_metrics": site_metrics,
    }


async def list_prediction_errors(
    db: AsyncSession,
    site_id: str | None = None,
    model_version_id: str | None = None,
    start_at: datetime | None = None,
    end_at: datetime | None = None,
    page: int = 1,
    size: int = 20,
) -> tuple[list[dict[str, Any]], int]:
    clauses = []
    if site_id:
        clauses.append(PredictionActualMatch.site_id == site_id)
    if model_version_id:
        clauses.append(PredictionActualMatch.model_version_id == model_version_id)
    if start_at:
        clauses.append(PredictionActualMatch.target_at >= start_at)
    if end_at:
        clauses.append(PredictionActualMatch.target_at <= end_at)

    q = select(PredictionActualMatch).order_by(PredictionActualMatch.target_at.desc())
    if clauses:
        q = q.where(and_(*clauses))

    rows = list((await db.execute(q)).scalars().all())
    total = len(rows)
    start = (page - 1) * size
    page_rows = rows[start : start + size]

    mv_ids = {r.model_version_id for r in page_rows}
    mv_map: dict[str, ModelVersion] = {}
    if mv_ids:
        mvs = (await db.execute(select(ModelVersion).where(ModelVersion.model_version_id.in_(mv_ids)))).scalars().all()
        mv_map = {m.model_version_id: m for m in mvs}

    items = []
    for r in page_rows:
        mv = mv_map.get(r.model_version_id)
        items.append({
            "match_id": r.match_id,
            "prediction_id": r.prediction_id,
            "site_id": r.site_id,
            "target_at": r.target_at.isoformat(),
            "model_version_id": r.model_version_id,
            "model_name": mv.model_name if mv else None,
            "model_version": mv.version_no if mv else None,
            "prediction_job_id": r.prediction_job_id,
            "predicted_demand": float(r.predicted_demand),
            "actual_demand": float(r.actual_demand),
            "error": float(r.error) if r.error is not None else None,
            "abs_error": float(r.abs_error) if r.abs_error is not None else None,
            "squared_error": float(r.squared_error) if r.squared_error is not None else None,
            "ape": float(r.ape) if r.ape is not None else None,
        })
    return items, total


async def get_prediction_performance_avg_mape(
    db: AsyncSession,
    days: int = 7,
) -> float | None:
    since = utc_now() - timedelta(days=days)
    rows = (
        await db.execute(
            select(ModelPerformanceMetric).where(
                ModelPerformanceMetric.metric_json["eval_type"].astext == EVAL_TYPE_PREDICTION,
                ModelPerformanceMetric.eval_end_at >= since,
            )
        )
    ).scalars().all()
    if not rows:
        return None
    values = [float(r.mape) for r in rows if r.mape is not None]
    return sum(values) / len(values) if values else None
