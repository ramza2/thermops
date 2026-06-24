from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.response import accepted, ok, paged
from app.models.entities import DriftReport, ModelPerformanceMetric, ModelVersion, RetrainingCandidate, Site
from app.schemas.api import DriftCheckCreate

router = APIRouter(tags=["Monitoring"])


@router.get("/performance-metrics")
async def performance_metrics(
    model_name: str | None = Query(default=None),
    model_version: str | None = Query(default=None),
    site_id: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    q = select(ModelPerformanceMetric)
    if site_id:
        q = q.where(ModelPerformanceMetric.site_id == site_id)
    rows = (await db.execute(q)).scalars().all()

    mv = None
    if model_name:
        mv = (await db.execute(
            select(ModelVersion).where(ModelVersion.model_name == model_name).limit(1)
        )).scalar_one_or_none()

    metrics = []
    for r in rows:
        site = (await db.execute(select(Site).where(Site.site_id == r.site_id))).scalar_one_or_none()
        metrics.append({
            "site_id": r.site_id,
            "site_name": site.site_name if site else r.site_id,
            "mae": float(r.mae) if r.mae else None,
            "rmse": float(r.rmse) if r.rmse else None,
            "mape": float(r.mape) if r.mape else None,
        })

    return ok({
        "model_name": model_name or (mv.model_name if mv else "heat_demand_lgbm"),
        "model_version": model_version or (mv.version_no if mv else "12"),
        "period": {"from": "2026-06-01", "to": "2026-06-23"},
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
