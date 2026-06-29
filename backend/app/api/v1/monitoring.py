from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.response import ok, paged
from app.core.time import utc_now
from app.models.entities import (
    DriftReport,
    ModelPerformanceMetric,
    ModelVersion,
    RetrainingCandidate,
    Site,
)
from app.schemas.api import DriftCheckCreate
from app.services.drift_detection_service import (
    DriftCheckParams,
    SOURCE_TYPE_COMPUTED,
    VALID_SOURCE_TYPES,
    drift_report_to_dict,
    resolve_drift_report_source_type,
    resolve_retraining_candidate_source_type,
    retraining_candidate_to_dict,
    run_drift_detection,
)
from app.services.retraining_candidate_service import train_retraining_candidate
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
    try:
        result = await run_drift_detection(
            db,
            DriftCheckParams(
                model_version_id=body.model_version_id,
                feature_set_id=body.feature_set_id,
                site_ids=body.site_ids,
                baseline_start_at=body.baseline_start_at,
                baseline_end_at=body.baseline_end_at,
                current_start_at=body.current_start_at,
                current_end_at=body.current_end_at,
                force_candidate=body.force_candidate,
            ),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ok(result, message="드리프트 점검이 완료되었습니다.")


@router.get("/drift-reports")
async def list_drift_reports(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    model_version_id: str | None = Query(default=None),
    site_id: str | None = Query(default=None),
    drift_status: str | None = Query(default=None),
    start_at: datetime | None = Query(default=None),
    end_at: datetime | None = Query(default=None),
    computed_only: bool = Query(default=False),
    source_type: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    if source_type and source_type not in VALID_SOURCE_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"source_type은 {sorted(VALID_SOURCE_TYPES)} 중 하나여야 합니다.",
        )

    q = select(DriftReport).order_by(DriftReport.created_at.desc())
    if model_version_id:
        q = q.where(DriftReport.model_version_id == model_version_id)
    if site_id:
        q = q.where(DriftReport.site_id == site_id)
    if drift_status:
        q = q.where(DriftReport.drift_status == drift_status)
    if start_at:
        q = q.where(DriftReport.created_at >= start_at)
    if end_at:
        q = q.where(DriftReport.created_at <= end_at)

    rows = list((await db.execute(q)).scalars().all())
    if computed_only:
        rows = [r for r in rows if resolve_drift_report_source_type(r) == SOURCE_TYPE_COMPUTED]
    elif source_type:
        rows = [r for r in rows if resolve_drift_report_source_type(r) == source_type]

    items = []
    for r in rows:
        site_name = None
        if r.site_id:
            site = (await db.execute(select(Site).where(Site.site_id == r.site_id))).scalar_one_or_none()
            site_name = site.site_name if site else None
        items.append(drift_report_to_dict(r, site_name))

    start = (page - 1) * size
    return paged(items[start:start + size], page, size, len(items))


@router.get("/drift-reports/{drift_report_id}")
async def get_drift_report(drift_report_id: str, db: AsyncSession = Depends(get_db)):
    report = (
        await db.execute(select(DriftReport).where(DriftReport.drift_report_id == drift_report_id))
    ).scalar_one_or_none()
    if not report:
        raise HTTPException(status_code=404, detail="드리프트 리포트를 찾을 수 없습니다.")
    site_name = None
    if report.site_id:
        site = (await db.execute(select(Site).where(Site.site_id == report.site_id))).scalar_one_or_none()
        site_name = site.site_name if site else None
    return ok(drift_report_to_dict(report, site_name))


@router.get("/retraining-candidates")
async def list_retraining_candidates(
    status: str | None = Query(default=None),
    severity: str | None = Query(default=None),
    model_version_id: str | None = Query(default=None),
    site_id: str | None = Query(default=None),
    computed_only: bool = Query(default=False),
    source_type: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    if source_type and source_type not in VALID_SOURCE_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"source_type은 {sorted(VALID_SOURCE_TYPES)} 중 하나여야 합니다.",
        )

    q = select(RetrainingCandidate).order_by(RetrainingCandidate.created_at.desc())
    if status:
        q = q.where(RetrainingCandidate.status == status)
    if severity:
        q = q.where(
            or_(
                RetrainingCandidate.severity == severity,
                RetrainingCandidate.risk_level == severity,
            )
        )
    if model_version_id:
        q = q.where(RetrainingCandidate.model_version_id == model_version_id)
    if site_id:
        q = q.where(RetrainingCandidate.site_id == site_id)
    rows = (await db.execute(q)).scalars().all()
    if computed_only:
        rows = [r for r in rows if resolve_retraining_candidate_source_type(r) == SOURCE_TYPE_COMPUTED]
    elif source_type:
        rows = [r for r in rows if resolve_retraining_candidate_source_type(r) == source_type]

    items = []
    for r in rows:
        site = None
        if r.site_id:
            site = (await db.execute(select(Site).where(Site.site_id == r.site_id))).scalar_one_or_none()
        items.append(retraining_candidate_to_dict(r, site.site_name if site else None))
    return ok(items)


@router.post("/retraining-candidates/{candidate_id}/approve")
async def approve_retraining_candidate(candidate_id: str, db: AsyncSession = Depends(get_db)):
    row = (
        await db.execute(select(RetrainingCandidate).where(RetrainingCandidate.candidate_id == candidate_id))
    ).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="재학습 후보를 찾을 수 없습니다.")
    if row.status in ("APPROVED", "TRAINED"):
        raise HTTPException(status_code=400, detail=f"이미 {row.status} 상태입니다.")
    row.status = "APPROVED"
    row.updated_at = utc_now()
    await db.commit()
    return ok(retraining_candidate_to_dict(row), message="재학습 후보가 승인되었습니다.")


@router.post("/retraining-candidates/{candidate_id}/reject")
async def reject_retraining_candidate(candidate_id: str, db: AsyncSession = Depends(get_db)):
    row = (
        await db.execute(select(RetrainingCandidate).where(RetrainingCandidate.candidate_id == candidate_id))
    ).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="재학습 후보를 찾을 수 없습니다.")
    if row.status == "REJECTED":
        raise HTTPException(status_code=400, detail="이미 반려된 후보입니다.")
    row.status = "REJECTED"
    row.updated_at = utc_now()
    await db.commit()
    return ok(retraining_candidate_to_dict(row), message="재학습 후보가 반려되었습니다.")


@router.post("/retraining-candidates/{candidate_id}/train")
async def train_retraining_candidate_endpoint(candidate_id: str, db: AsyncSession = Depends(get_db)):
  # TODO(P1-3): APPROVED candidate → Airflow retraining_dag trigger, 완료 후 TRAINED 갱신
    try:
        result = await train_retraining_candidate(db, candidate_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    if result.get("status") != "SUCCESS":
        raise HTTPException(
            status_code=400,
            detail=result.get("candidate", {}).get("error_message", "모델 학습 실패"),
        )

    return ok(result, message="재학습이 완료되었습니다.")
