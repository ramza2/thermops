from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.response import accepted, ok, paged
from app.models.entities import (
    DriftReport,
    ModelPerformanceMetric,
    ModelVersion,
    RetrainingCandidate,
    Site,
)
from app.schemas.api import DriftCheckCreate
from app.services.prediction_evaluation_service import EVAL_TYPE_PREDICTION, EVAL_TYPE_TRAINING

router = APIRouter(tags=["Monitoring"])

VALID_EVAL_TYPES = {EVAL_TYPE_PREDICTION, EVAL_TYPE_TRAINING}


def _eval_type_clause(eval_type: str):
    if eval_type == EVAL_TYPE_TRAINING:
        return or_(
            ModelPerformanceMetric.metric_json["eval_type"].astext == EVAL_TYPE_TRAINING,
            ModelPerformanceMetric.metric_json.is_(None),
            ModelPerformanceMetric.metric_json["eval_type"].astext.is_(None),
        )
    return ModelPerformanceMetric.metric_json["eval_type"].astext == eval_type


async def _fetch_metric_rows(
    db: AsyncSession,
    model_version_id: str | None,
    site_id: str | None,
    eval_type: str | None,
) -> list[ModelPerformanceMetric]:
    q = select(ModelPerformanceMetric)
    if model_version_id:
        q = q.where(ModelPerformanceMetric.model_version_id == model_version_id)
    if site_id:
        q = q.where(ModelPerformanceMetric.site_id == site_id)
    if eval_type:
        q = q.where(_eval_type_clause(eval_type))
    return list((await db.execute(q.order_by(ModelPerformanceMetric.site_id))).scalars().all())


def _metric_item(r: ModelPerformanceMetric, site_name: str | None) -> dict:
    extra = r.metric_json or {}
    row_eval = extra.get("eval_type")
    return {
        "site_id": r.site_id,
        "site_name": site_name or r.site_id,
        "mae": float(r.mae) if r.mae is not None else None,
        "rmse": float(r.rmse) if r.rmse is not None else None,
        "mape": float(r.mape) if r.mape is not None else None,
        "r2": extra.get("r2"),
        "sample_count": r.sample_count,
        "max_abs_error": extra.get("max_abs_error"),
        "avg_actual_demand": extra.get("avg_actual_demand"),
        "avg_predicted_demand": extra.get("avg_predicted_demand"),
        "eval_type": row_eval or "UNCLASSIFIED",
    }


@router.get("/performance-metrics")
async def performance_metrics(
    model_name: str | None = Query(default=None),
    model_version: str | None = Query(default=None),
    model_version_id: str | None = Query(default=None),
    site_id: str | None = Query(default=None),
    eval_type: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    if eval_type and eval_type not in VALID_EVAL_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"eval_type은 {sorted(VALID_EVAL_TYPES)} 중 하나여야 합니다.",
        )

    mv: ModelVersion | None = None
    if model_version_id:
        mv = (
            await db.execute(select(ModelVersion).where(ModelVersion.model_version_id == model_version_id))
        ).scalar_one_or_none()
    elif model_name and model_version:
        mv = (
            await db.execute(
                select(ModelVersion).where(
                    ModelVersion.model_name == model_name,
                    ModelVersion.version_no == model_version,
                )
            )
        ).scalar_one_or_none()
    elif model_name:
        mv = (
            await db.execute(
                select(ModelVersion)
                .where(ModelVersion.model_name == model_name)
                .order_by(ModelVersion.registered_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
    else:
        mv = (
            await db.execute(
                select(ModelVersion).order_by(ModelVersion.registered_at.desc()).limit(1)
            )
        ).scalar_one_or_none()

    mv_id = mv.model_version_id if mv else None

    if eval_type:
        effective_eval_type = eval_type
        rows = await _fetch_metric_rows(db, mv_id, site_id, eval_type)
    else:
        rows = await _fetch_metric_rows(db, mv_id, site_id, EVAL_TYPE_PREDICTION)
        effective_eval_type = EVAL_TYPE_PREDICTION
        if not rows:
            rows = await _fetch_metric_rows(db, mv_id, site_id, EVAL_TYPE_TRAINING)
            effective_eval_type = EVAL_TYPE_TRAINING
        if not rows:
            rows = await _fetch_metric_rows(db, mv_id, site_id, None)
            effective_eval_type = None

    period_from = None
    period_to = None
    if rows:
        period_from = min(r.eval_start_at for r in rows).date().isoformat()
        period_to = max(r.eval_end_at for r in rows).date().isoformat()

    metrics = []
    for r in rows:
        site = (await db.execute(select(Site).where(Site.site_id == r.site_id))).scalar_one_or_none()
        metrics.append(_metric_item(r, site.site_name if site else None))

    if eval_type == EVAL_TYPE_PREDICTION:
        metrics = [m for m in metrics if m["eval_type"] == EVAL_TYPE_PREDICTION]
    elif eval_type == EVAL_TYPE_TRAINING:
        metrics = [m for m in metrics if m["eval_type"] in (EVAL_TYPE_TRAINING, "UNCLASSIFIED")]

    return ok({
        "model_name": mv.model_name if mv else (model_name or "heat_demand_lightgbm"),
        "model_version": mv.version_no if mv else (model_version or "-"),
        "model_version_id": mv.model_version_id if mv else model_version_id,
        "eval_type": effective_eval_type,
        "period": {
            "from": period_from or datetime.utcnow().date().isoformat(),
            "to": period_to or datetime.utcnow().date().isoformat(),
        },
        "metrics": metrics,
    })


@router.post("/drift-checks")
async def run_drift_check(body: DriftCheckCreate, db: AsyncSession = Depends(get_db)):
    report_id = f"DRIFT-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{uuid4().hex[:4].upper()}"
    report = DriftReport(
        drift_report_id=report_id,
        dataset_version_id=body.dataset_version_id or "DSV-20260601-TRAIN",
        model_version_id=body.model_version_id,
        base_period="2024-01 ~ 2026-03",
        current_period="2026-06-01 ~ 2026-06-23",
        drift_status="WARNING",
        drift_score_json={"temperature": 0.35, "lag_24h_demand": 0.22},
        created_at=datetime.now(timezone.utc),
    )
    db.add(report)
    return accepted({"report_id": report_id, "status": "WARNING"}, message="드리프트 점검이 요청되었습니다.")


@router.get("/drift-reports")
async def list_drift_reports(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    rows = (await db.execute(select(DriftReport).order_by(DriftReport.created_at.desc()))).scalars().all()
    items = [
        {
            "drift_report_id": r.drift_report_id,
            "base_period": r.base_period,
            "current_period": r.current_period,
            "drift_status": r.drift_status,
            "drift_score_json": r.drift_score_json,
            "created_at": r.created_at.isoformat(),
        }
        for r in rows
    ]
    start = (page - 1) * size
    return paged(items[start:start + size], page, size, len(items))


@router.get("/retraining-candidates")
async def list_retraining_candidates(
    status: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    q = select(RetrainingCandidate).order_by(RetrainingCandidate.created_at.desc())
    if status:
        q = q.where(RetrainingCandidate.status == status)
    rows = (await db.execute(q)).scalars().all()

    items = []
    for r in rows:
        site = None
        if r.site_id:
            site = (await db.execute(select(Site).where(Site.site_id == r.site_id))).scalar_one_or_none()
        items.append({
            "candidate_id": r.candidate_id,
            "reason": r.reason,
            "model_name": r.model_name,
            "model_version": r.model_version,
            "site_id": r.site_id,
            "site_name": site.site_name if site else "전체",
            "risk_level": r.risk_level,
            "status": r.status,
            "created_at": r.created_at.isoformat(),
        })
    return ok(items)
