"""Drift 감지 및 재학습 후보 자동 생성 서비스."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any
from uuid import uuid4

import numpy as np
from scipy import stats
from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.time import utc_now
from app.models.entities import (
    DriftReport,
    FeatureDataset,
    ModelPerformanceMetric,
    ModelVersion,
    PredictionActualMatch,
    RetrainingCandidate,
    SystemConfig,
)
from app.services.prediction_evaluation_service import EVAL_TYPE_PREDICTION

SOURCE_TYPE_COMPUTED = "COMPUTED"
SOURCE_TYPE_SEED = "SEED"
SOURCE_TYPE_MANUAL = "MANUAL"

VALID_SOURCE_TYPES = {SOURCE_TYPE_COMPUTED, SOURCE_TYPE_SEED, SOURCE_TYPE_MANUAL}


def resolve_drift_report_source_type(report: DriftReport) -> str:
    if report.source_type:
        return report.source_type
    if (report.drift_score_json or {}).get("computed"):
        return SOURCE_TYPE_COMPUTED
    return SOURCE_TYPE_SEED


def resolve_retraining_candidate_source_type(row: RetrainingCandidate) -> str:
    if row.source_type:
        return row.source_type
    if row.drift_report_id and row.model_version_id:
        return SOURCE_TYPE_COMPUTED
    return SOURCE_TYPE_SEED


FEATURE_KEYS = (
    "temperature",
    "humidity",
    "demand_lag_24h",
    "demand_lag_168h",
    "demand_ma_24h",
    "temperature_diff_24h",
)

COLUMN_FALLBACK = {
    "temperature": "temp",
    "humidity": "humidity",
    "demand_lag_24h": "lag_24h_demand",
    "demand_lag_168h": "lag_168h_demand",
    "demand_ma_24h": "rolling_24h_avg",
}

DEFAULT_THRESHOLDS = {
    "mape_warning_threshold": 8.0,
    "retraining_mape_threshold": 10.0,
    "drift_warning_threshold": 0.40,
}

ERROR_WARNING_RATIO = 1.2
ERROR_CRITICAL_RATIO = 1.5


@dataclass
class DriftCheckParams:
    model_version_id: str | None = None
    feature_set_id: str | None = None
    site_ids: list[str] | None = None
    baseline_start_at: datetime | None = None
    baseline_end_at: datetime | None = None
    current_start_at: datetime | None = None
    current_end_at: datetime | None = None
    force_candidate: bool = False


@dataclass
class DriftThresholds:
    mape_warning: float
    retraining_mape: float
    drift_warning: float
    warnings: list[str] = field(default_factory=list)


@dataclass
class PeriodMetrics:
    mape: float | None = None
    mae: float | None = None
    rmse: float | None = None
    sample_count: int = 0
    avg_ape: float | None = None
    avg_abs_error: float | None = None


def _max_status(*statuses: str) -> str:
    order = {"NORMAL": 0, "WARNING": 1, "CRITICAL": 2}
    return max(statuses, key=lambda s: order.get(s, 0))


def _period_label(start: datetime, end: datetime) -> str:
    return f"{start.strftime('%Y-%m-%d %H:%M')} ~ {end.strftime('%Y-%m-%d %H:%M')}"


async def _load_thresholds(db: AsyncSession) -> DriftThresholds:
    warnings: list[str] = []
    values: dict[str, float] = {}
    for key, default in DEFAULT_THRESHOLDS.items():
        row = (
            await db.execute(select(SystemConfig).where(SystemConfig.config_key == key))
        ).scalar_one_or_none()
        raw = row.config_value if row and row.config_value else None
        if raw is None:
            values[key] = default
            warnings.append(f"{key} 미설정 — 기본값 {default} 사용")
            continue
        try:
            values[key] = float(raw)
        except (TypeError, ValueError):
            values[key] = default
            warnings.append(f"{key} 파싱 실패 — 기본값 {default} 사용")
    return DriftThresholds(
        mape_warning=values["mape_warning_threshold"],
        retraining_mape=values["retraining_mape_threshold"],
        drift_warning=values["drift_warning_threshold"],
        warnings=warnings,
    )


async def _resolve_model_version(db: AsyncSession, model_version_id: str | None) -> ModelVersion:
    if model_version_id:
        mv = (
            await db.execute(select(ModelVersion).where(ModelVersion.model_version_id == model_version_id))
        ).scalar_one_or_none()
        if not mv:
            raise ValueError(f"모델 버전을 찾을 수 없습니다: {model_version_id}")
        return mv
    champion = (
        await db.execute(
            select(ModelVersion).where(ModelVersion.model_stage == "CHAMPION").order_by(ModelVersion.registered_at.desc()).limit(1)
        )
    ).scalar_one_or_none()
    if champion:
        return champion
    latest = (
        await db.execute(select(ModelVersion).order_by(ModelVersion.registered_at.desc()).limit(1))
    ).scalar_one_or_none()
    if not latest:
        raise ValueError("등록된 모델 버전이 없습니다.")
    return latest


def _default_periods() -> tuple[datetime, datetime, datetime, datetime]:
    now = utc_now()
    current_end = now.replace(minute=0, second=0, microsecond=0)
    current_start = current_end - timedelta(days=14)
    baseline_end = current_start - timedelta(hours=1)
    baseline_start = baseline_end - timedelta(days=14)
    return baseline_start, baseline_end, current_start, current_end


def _metrics_from_matches(rows: list[PredictionActualMatch]) -> PeriodMetrics:
    if not rows:
        return PeriodMetrics()
    apes = [float(r.ape) for r in rows if r.ape is not None]
    abs_errors = [float(r.abs_error) for r in rows if r.abs_error is not None]
    squared = [float(r.squared_error) for r in rows if r.squared_error is not None]
    mape = float(np.mean(apes)) if apes else None
    mae = float(np.mean(abs_errors)) if abs_errors else None
    rmse = float(math.sqrt(np.mean(squared))) if squared else None
    return PeriodMetrics(
        mape=mape,
        mae=mae,
        rmse=rmse,
        sample_count=len(rows),
        avg_ape=mape,
        avg_abs_error=mae,
    )


async def _fetch_matches(
    db: AsyncSession,
    model_version_id: str,
    site_ids: list[str] | None,
    start_at: datetime,
    end_at: datetime,
) -> list[PredictionActualMatch]:
    clauses = [
        PredictionActualMatch.model_version_id == model_version_id,
        PredictionActualMatch.target_at >= start_at,
        PredictionActualMatch.target_at <= end_at,
    ]
    if site_ids:
        clauses.append(PredictionActualMatch.site_id.in_(site_ids))
    return list(
        (await db.execute(select(PredictionActualMatch).where(and_(*clauses)))).scalars().all()
    )


async def detect_performance_drift(
    db: AsyncSession,
    model_version_id: str,
    site_ids: list[str] | None,
    current_start: datetime,
    current_end: datetime,
    thresholds: DriftThresholds,
) -> dict[str, Any]:
    clauses = [
        ModelPerformanceMetric.model_version_id == model_version_id,
        ModelPerformanceMetric.eval_end_at >= current_start,
        ModelPerformanceMetric.eval_start_at <= current_end,
        ModelPerformanceMetric.metric_json["eval_type"].astext == EVAL_TYPE_PREDICTION,
    ]
    if site_ids:
        clauses.append(ModelPerformanceMetric.site_id.in_(site_ids))
    rows = list((await db.execute(select(ModelPerformanceMetric).where(and_(*clauses)))).scalars().all())

    mape_values = [float(r.mape) for r in rows if r.mape is not None]
    if not mape_values:
        match_rows = await _fetch_matches(db, model_version_id, site_ids, current_start, current_end)
        pm = _metrics_from_matches(match_rows)
        mape_values = [pm.mape] if pm.mape is not None else []

    if not mape_values:
        return {
            "drift_type": "PERFORMANCE",
            "drift_status": "NORMAL",
            "drift_score": 0.0,
            "current_mape": None,
            "sample_count": 0,
            "message": "운영 성능 데이터 없음",
        }

    current_mape = float(np.mean(mape_values))
    status = "NORMAL"
    if current_mape >= thresholds.retraining_mape:
        status = "CRITICAL"
    elif current_mape >= thresholds.mape_warning:
        status = "WARNING"

    score = min(1.0, current_mape / max(thresholds.retraining_mape, 1e-6))
    return {
        "drift_type": "PERFORMANCE",
        "drift_status": status,
        "drift_score": round(score, 4),
        "current_mape": round(current_mape, 4),
        "mape_warning_threshold": thresholds.mape_warning,
        "retraining_mape_threshold": thresholds.retraining_mape,
        "sample_count": len(mape_values),
    }


async def detect_error_drift(
    db: AsyncSession,
    model_version_id: str,
    site_ids: list[str] | None,
    baseline_start: datetime,
    baseline_end: datetime,
    current_start: datetime,
    current_end: datetime,
) -> dict[str, Any]:
    baseline_rows = await _fetch_matches(db, model_version_id, site_ids, baseline_start, baseline_end)
    current_rows = await _fetch_matches(db, model_version_id, site_ids, current_start, current_end)
    baseline = _metrics_from_matches(baseline_rows)
    current = _metrics_from_matches(current_rows)

    if baseline.sample_count == 0 or current.sample_count == 0:
        return {
            "drift_type": "ERROR",
            "drift_status": "NORMAL",
            "drift_score": 0.0,
            "baseline": baseline.__dict__,
            "current": current.__dict__,
            "message": "매칭 데이터 부족",
        }

    status = "NORMAL"
    ratios: dict[str, float | None] = {}
    for key, b_val, c_val in (
        ("mape", baseline.mape, current.mape),
        ("mae", baseline.mae, current.mae),
        ("rmse", baseline.rmse, current.rmse),
    ):
        if b_val is None or c_val is None or b_val <= 1e-8:
            ratios[key] = None
            continue
        ratio = c_val / b_val
        ratios[key] = round(ratio, 4)
        if ratio >= ERROR_CRITICAL_RATIO:
            status = _max_status(status, "CRITICAL")
        elif ratio >= ERROR_WARNING_RATIO:
            status = _max_status(status, "WARNING")

    mape_ratio = ratios.get("mape") or 1.0
    score = min(1.0, max(0.0, (mape_ratio - 1.0) / (ERROR_CRITICAL_RATIO - 1.0)))

    return {
        "drift_type": "ERROR",
        "drift_status": status,
        "drift_score": round(score, 4),
        "baseline": {
            "mape": baseline.mape,
            "mae": baseline.mae,
            "rmse": baseline.rmse,
            "sample_count": baseline.sample_count,
        },
        "current": {
            "mape": current.mape,
            "mae": current.mae,
            "rmse": current.rmse,
            "sample_count": current.sample_count,
        },
        "ratios": ratios,
        "warning_ratio": ERROR_WARNING_RATIO,
        "critical_ratio": ERROR_CRITICAL_RATIO,
    }


def _extract_feature_value(row: FeatureDataset, key: str) -> float | None:
    fj = row.feature_json or {}
    if key in fj and fj[key] is not None:
        try:
            return float(fj[key])
        except (TypeError, ValueError):
            pass
    col = COLUMN_FALLBACK.get(key)
    if col:
        val = getattr(row, col, None)
        if val is not None:
            return float(val)
    return None


async def _fetch_feature_rows(
    db: AsyncSession,
    site_ids: list[str] | None,
    start_at: datetime,
    end_at: datetime,
) -> list[FeatureDataset]:
    clauses = [
        FeatureDataset.feature_at >= start_at,
        FeatureDataset.feature_at <= end_at,
    ]
    if site_ids:
        clauses.append(FeatureDataset.site_id.in_(site_ids))
    return list(
        (await db.execute(select(FeatureDataset).where(and_(*clauses)))).scalars().all()
    )


def _feature_stats(values: list[float]) -> dict[str, float | int]:
    arr = np.array(values, dtype=float)
    return {
        "count": int(len(arr)),
        "mean": float(np.mean(arr)),
        "std": float(np.std(arr)),
        "missing_rate": 0.0,
    }


def _compare_feature(
    key: str,
    baseline_vals: list[float],
    current_vals: list[float],
    drift_warning: float,
) -> dict[str, Any]:
    if not baseline_vals or not current_vals:
        return {
            "feature": key,
            "drift_status": "NORMAL",
            "drift_score": 0.0,
            "message": "데이터 부족",
        }

    b_stats = _feature_stats(baseline_vals)
    c_stats = _feature_stats(current_vals)
    b_mean, b_std = b_stats["mean"], max(b_stats["std"], 1e-6)
    c_mean, c_std = c_stats["mean"], c_stats["std"]

    mean_shift = abs(c_mean - b_mean) / (abs(b_mean) + 1e-6)
    std_shift = abs(c_std - b_std) / (b_std + 1e-6)
    missing_delta = 0.0

    ks_pvalue: float | None = None
    try:
        ks_pvalue = float(stats.ks_2samp(baseline_vals, current_vals).pvalue)
    except Exception:
        ks_pvalue = None

    score = min(1.0, 0.35 * mean_shift + 0.25 * std_shift + 0.15 * max(0.0, missing_delta) + (
        0.25 if ks_pvalue is not None and ks_pvalue < 0.05 else 0.0
    ))

    status = "NORMAL"
    if score >= drift_warning * 1.5 or (ks_pvalue is not None and ks_pvalue < 0.01):
        status = "CRITICAL"
    elif score >= drift_warning or (ks_pvalue is not None and ks_pvalue < 0.05):
        status = "WARNING"

    return {
        "feature": key,
        "drift_status": status,
        "drift_score": round(score, 4),
        "baseline_mean": round(b_mean, 4),
        "current_mean": round(c_mean, 4),
        "baseline_std": round(b_std, 4),
        "current_std": round(c_std, 4),
        "mean_shift_ratio": round(mean_shift, 4),
        "std_shift_ratio": round(std_shift, 4),
        "ks_pvalue": round(ks_pvalue, 6) if ks_pvalue is not None else None,
        "baseline_count": len(baseline_vals),
        "current_count": len(current_vals),
    }


async def detect_feature_drift(
    db: AsyncSession,
    site_ids: list[str] | None,
    baseline_start: datetime,
    baseline_end: datetime,
    current_start: datetime,
    current_end: datetime,
    thresholds: DriftThresholds,
) -> dict[str, Any]:
    baseline_rows = await _fetch_feature_rows(db, site_ids, baseline_start, baseline_end)
    current_rows = await _fetch_feature_rows(db, site_ids, current_start, current_end)

    if not baseline_rows or not current_rows:
        return {
            "drift_type": "FEATURE",
            "drift_status": "NORMAL",
            "drift_score": 0.0,
            "features": {},
            "message": "Feature Dataset 데이터 부족",
        }

    feature_results: dict[str, Any] = {}
    statuses: list[str] = []
    scores: list[float] = []
    for key in FEATURE_KEYS:
        b_vals = [v for r in baseline_rows if (v := _extract_feature_value(r, key)) is not None]
        c_vals = [v for r in current_rows if (v := _extract_feature_value(r, key)) is not None]
        result = _compare_feature(key, b_vals, c_vals, thresholds.drift_warning)
        feature_results[key] = result
        statuses.append(result["drift_status"])
        scores.append(result["drift_score"])

    overall_status = _max_status(*statuses) if statuses else "NORMAL"
    overall_score = max(scores) if scores else 0.0
    warning_count = sum(1 for r in feature_results.values() if r["drift_status"] in ("WARNING", "CRITICAL"))

    return {
        "drift_type": "FEATURE",
        "drift_status": overall_status,
        "drift_score": round(overall_score, 4),
        "features": feature_results,
        "warning_feature_count": warning_count,
        "drift_warning_threshold": thresholds.drift_warning,
    }


def _build_recommendation(overall: str, perf: dict, err: dict, feat: dict) -> str:
    parts: list[str] = []
    if perf.get("drift_status") in ("WARNING", "CRITICAL"):
        parts.append(f"운영 MAPE {perf.get('current_mape')}% — 성능 Drift {perf.get('drift_status')}")
    if err.get("drift_status") in ("WARNING", "CRITICAL"):
        parts.append(f"예측 오차 증가 — ERROR Drift {err.get('drift_status')}")
    if feat.get("drift_status") in ("WARNING", "CRITICAL"):
        parts.append(
            f"Feature 분포 변화 {feat.get('warning_feature_count', 0)}건 — FEATURE Drift {feat.get('drift_status')}"
        )
    if not parts:
        return "모든 Drift 지표가 정상 범위입니다."
    if overall == "CRITICAL":
        return "재학습 검토 권장: " + "; ".join(parts)
    return "모니터링 강화 권장: " + "; ".join(parts)


async def create_drift_report(
    db: AsyncSession,
    *,
    model_version: ModelVersion,
    feature_set_id: str | None,
    site_id: str | None,
    baseline_start: datetime,
    baseline_end: datetime,
    current_start: datetime,
    current_end: datetime,
    performance: dict,
    error: dict,
    feature: dict,
    thresholds: DriftThresholds,
) -> DriftReport:
    overall = _max_status(
        performance.get("drift_status", "NORMAL"),
        error.get("drift_status", "NORMAL"),
        feature.get("drift_status", "NORMAL"),
    )
    scores = [
        performance.get("drift_score") or 0,
        error.get("drift_score") or 0,
        feature.get("drift_score") or 0,
    ]
    drift_score = max(scores)
    metric_summary = {
        "performance": performance,
        "error": error,
        "overall_drift_status": overall,
        "warnings": thresholds.warnings,
    }
    feature_drift = feature.get("features") or {}
    recommendation = _build_recommendation(overall, performance, error, feature)

    report_id = f"DRIFT-{utc_now().strftime('%Y%m%d')}-{uuid4().hex[:4].upper()}"
    payload = {
        "computed": True,
        "overall_drift_status": overall,
        "drift_score": drift_score,
        "performance": performance,
        "error": error,
        "feature": feature,
        "metric_summary": metric_summary,
        "feature_drift": feature_drift,
        "recommendation": recommendation,
        "warnings": thresholds.warnings,
    }

    report = DriftReport(
        drift_report_id=report_id,
        dataset_version_id=None,
        model_version_id=model_version.model_version_id,
        feature_set_id=feature_set_id,
        site_id=site_id,
        base_period=_period_label(baseline_start, baseline_end),
        current_period=_period_label(current_start, current_end),
        baseline_start_at=baseline_start,
        baseline_end_at=baseline_end,
        current_start_at=current_start,
        current_end_at=current_end,
        drift_type="OVERALL",
        drift_status=overall,
        drift_score=drift_score,
        drift_score_json=payload,
        recommendation=recommendation,
        source_type=SOURCE_TYPE_COMPUTED,
        created_at=utc_now(),
    )
    db.add(report)
    await db.flush()
    return report


async def _has_pending_candidate(
    db: AsyncSession,
    model_version_id: str,
    site_id: str | None,
    reason_type: str,
    current_end: datetime,
) -> RetrainingCandidate | None:
    period_key = current_end.strftime("%Y-%m-%d")
    q = select(RetrainingCandidate).where(
        RetrainingCandidate.model_version_id == model_version_id,
        RetrainingCandidate.reason_type == reason_type,
        RetrainingCandidate.status.in_(("PENDING", "REVIEW")),
    )
    if site_id:
        q = q.where(RetrainingCandidate.site_id == site_id)
    else:
        q = q.where(or_(RetrainingCandidate.site_id.is_(None), RetrainingCandidate.site_id == ""))
    rows = list((await db.execute(q)).scalars().all())
    for row in rows:
        snap = row.metric_snapshot_json or {}
        if snap.get("current_period_end", "").startswith(period_key):
            return row
    return None


async def create_retraining_candidate_if_needed(
    db: AsyncSession,
    *,
    drift_report: DriftReport,
    model_version: ModelVersion,
    feature_set_id: str | None,
    site_id: str | None,
    performance: dict,
    error: dict,
    feature: dict,
    thresholds: DriftThresholds,
    force: bool = False,
) -> RetrainingCandidate | None:
    reasons: list[tuple[str, str, str]] = []

    if performance.get("drift_status") == "CRITICAL":
        reasons.append((
            "PERFORMANCE_DEGRADATION",
            "CRITICAL",
            f"운영 MAPE {performance.get('current_mape')}% >= 재학습 임계치 {thresholds.retraining_mape}%",
        ))
    elif force:
        reasons.append((
            "PERFORMANCE_DEGRADATION",
            "WARNING",
            "테스트용 force_candidate",
        ))

    if error.get("drift_status") == "CRITICAL":
        reasons.append((
            "ERROR_DRIFT",
            "CRITICAL",
            f"예측 오차 증가 (MAPE ratio {error.get('ratios', {}).get('mape')})",
        ))
    elif error.get("drift_status") == "WARNING" and force:
        reasons.append(("ERROR_DRIFT", "WARNING", "테스트용 force_candidate"))

    feat_warning_count = feature.get("warning_feature_count") or 0
    if feature.get("drift_status") == "CRITICAL" or feat_warning_count >= 3:
        reasons.append((
            "FEATURE_DRIFT",
            "CRITICAL" if feature.get("drift_status") == "CRITICAL" else "WARNING",
            f"Feature Drift {feat_warning_count}개 Feature WARNING 이상",
        ))
    elif feature.get("drift_status") == "WARNING" and force:
        reasons.append(("FEATURE_DRIFT", "WARNING", "테스트용 force_candidate"))

    if not reasons:
        return None

    reason_type, severity, summary = reasons[0]
    current_end = drift_report.current_end_at or utc_now()
    existing = await _has_pending_candidate(
        db, model_version.model_version_id, site_id, reason_type, current_end
    )
    snapshot = {
        "performance": performance,
        "error": error,
        "feature_summary": {
            "drift_status": feature.get("drift_status"),
            "warning_feature_count": feat_warning_count,
        },
        "current_period_end": current_end.isoformat(),
        "baseline_period": drift_report.base_period,
        "current_period": drift_report.current_period,
    }
    if existing:
        existing.metric_snapshot_json = snapshot
        existing.reason_summary = summary
        existing.reason = summary
        existing.severity = severity
        existing.risk_level = "HIGH" if severity == "CRITICAL" else "MEDIUM"
        existing.source_type = SOURCE_TYPE_COMPUTED
        existing.updated_at = utc_now()
        await db.flush()
        return existing

    candidate_id = f"RTC-{utc_now().strftime('%Y%m%d')}-{uuid4().hex[:4].upper()}"
    candidate = RetrainingCandidate(
        candidate_id=candidate_id,
        reason=summary,
        reason_summary=summary,
        model_name=model_version.model_name,
        model_version=model_version.version_no,
        model_version_id=model_version.model_version_id,
        feature_set_id=feature_set_id,
        site_id=site_id,
        reason_type=reason_type,
        severity=severity,
        risk_level="HIGH" if severity == "CRITICAL" else "MEDIUM",
        status="PENDING",
        drift_report_id=drift_report.drift_report_id,
        metric_snapshot_json=snapshot,
        source_type=SOURCE_TYPE_COMPUTED,
        created_at=utc_now(),
    )
    db.add(candidate)
    await db.flush()
    return candidate


async def run_drift_detection(db: AsyncSession, params: DriftCheckParams) -> dict[str, Any]:
    thresholds = await _load_thresholds(db)
    mv = await _resolve_model_version(db, params.model_version_id)

    if params.baseline_start_at and params.baseline_end_at and params.current_start_at and params.current_end_at:
        baseline_start, baseline_end = params.baseline_start_at, params.baseline_end_at
        current_start, current_end = params.current_start_at, params.current_end_at
    else:
        baseline_start, baseline_end, current_start, current_end = _default_periods()

    site_ids = params.site_ids
    feature_set_id = params.feature_set_id or "FS-TPL-LAG-ROLL"

    performance = await detect_performance_drift(
        db, mv.model_version_id, site_ids, current_start, current_end, thresholds
    )
    error = await detect_error_drift(
        db, mv.model_version_id, site_ids, baseline_start, baseline_end, current_start, current_end
    )
    feature = await detect_feature_drift(
        db, site_ids, baseline_start, baseline_end, current_start, current_end, thresholds
    )

    site_scope = site_ids[0] if site_ids and len(site_ids) == 1 else None
    report = await create_drift_report(
        db,
        model_version=mv,
        feature_set_id=feature_set_id,
        site_id=site_scope,
        baseline_start=baseline_start,
        baseline_end=baseline_end,
        current_start=current_start,
        current_end=current_end,
        performance=performance,
        error=error,
        feature=feature,
        thresholds=thresholds,
    )

    candidate = await create_retraining_candidate_if_needed(
        db,
        drift_report=report,
        model_version=mv,
        feature_set_id=feature_set_id,
        site_id=site_scope,
        performance=performance,
        error=error,
        feature=feature,
        thresholds=thresholds,
        force=params.force_candidate,
    )
    await db.commit()

    overall = report.drift_status
    metric_summary = {
        "performance": performance,
        "error": error,
        "feature": {
            "drift_status": feature.get("drift_status"),
            "drift_score": feature.get("drift_score"),
            "warning_feature_count": feature.get("warning_feature_count"),
        },
        "warnings": thresholds.warnings,
    }

    return {
        "status": "SUCCESS",
        "overall_drift_status": overall,
        "drift_report_id": report.drift_report_id,
        "created_retraining_candidates": 1 if candidate else 0,
        "retraining_candidate_id": candidate.candidate_id if candidate else None,
        "metric_summary": metric_summary,
        "feature_drift_json": feature.get("features"),
        "recommendation": report.recommendation,
    }


def drift_report_to_dict(report: DriftReport, site_name: str | None = None) -> dict[str, Any]:
    payload = report.drift_score_json or {}
    source_type = resolve_drift_report_source_type(report)
    computed = source_type == SOURCE_TYPE_COMPUTED
    feature_drift = payload.get("feature_drift") or (
        {k: v for k, v in payload.items() if isinstance(v, (int, float))} if not computed else {}
    )
    metric_summary = payload.get("metric_summary") or payload.get("performance") and payload or {}
    if computed and "metric_summary" in payload:
        metric_summary = payload["metric_summary"]

    return {
        "drift_report_id": report.drift_report_id,
        "model_version_id": report.model_version_id,
        "feature_set_id": report.feature_set_id,
        "site_id": report.site_id,
        "site_name": site_name or (report.site_id or "전체"),
        "drift_type": report.drift_type or ("OVERALL" if computed else "LEGACY"),
        "drift_status": report.drift_status,
        "drift_score": float(report.drift_score) if report.drift_score is not None else payload.get("drift_score"),
        "base_period": report.base_period,
        "current_period": report.current_period,
        "baseline_start_at": report.baseline_start_at.isoformat() if report.baseline_start_at else None,
        "baseline_end_at": report.baseline_end_at.isoformat() if report.baseline_end_at else None,
        "current_start_at": report.current_start_at.isoformat() if report.current_start_at else None,
        "current_end_at": report.current_end_at.isoformat() if report.current_end_at else None,
        "drift_score_json": report.drift_score_json,
        "metric_summary_json": metric_summary,
        "feature_drift_json": feature_drift,
        "recommendation": report.recommendation or payload.get("recommendation"),
        "source_type": source_type,
        "computed": computed,
        "computed_yn": computed,
        "created_at": report.created_at.isoformat(),
    }


def retraining_candidate_to_dict(row: RetrainingCandidate, site_name: str | None = None) -> dict[str, Any]:
    source_type = resolve_retraining_candidate_source_type(row)
    computed = source_type == SOURCE_TYPE_COMPUTED
    return {
        "candidate_id": row.candidate_id,
        "model_version_id": row.model_version_id,
        "feature_set_id": row.feature_set_id,
        "model_name": row.model_name,
        "model_version": row.model_version,
        "site_id": row.site_id,
        "site_name": site_name or (row.site_id or "전체"),
        "reason_type": row.reason_type or "MANUAL",
        "severity": row.severity or row.risk_level,
        "reason_summary": row.reason_summary or row.reason,
        "reason": row.reason_summary or row.reason,
        "risk_level": row.risk_level or row.severity,
        "status": row.status,
        "drift_report_id": row.drift_report_id,
        "metric_snapshot_json": row.metric_snapshot_json,
        "source_type": source_type,
        "computed": computed,
        "computed_yn": computed,
        "created_at": row.created_at.isoformat(),
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }
