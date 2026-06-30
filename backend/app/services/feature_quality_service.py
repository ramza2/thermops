"""Feature Dataset(feature_json) 품질 검증."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import uuid4

import numpy as np
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.time import utc_now
from app.models.entities import DataQualityRun, FeatureDataset, FeatureSet
from app.services.feature_dataset_service import _feature_set_filter, latest_dataset_version_id

# feature_name -> (min, max). None means no upper/lower bound on that side.
RANGE_RULES: dict[str, tuple[float | None, float | None]] = {
    "hour": (0, 23),
    "day_of_week": (0, 6),
    "month": (1, 12),
    "is_weekend": (0, 1),
    "is_holiday": (0, 1),
    "heat_demand": (0, None),
    "demand_lag_24h": (0, None),
    "demand_lag_168h": (0, None),
    "demand_ma_24h": (0, None),
    "demand_ma_168h": (0, None),
    "temperature": (-50, 60),
    "temperature_diff_24h": (-50, 50),
    "temperature_lag_24h": (-50, 60),
    "temperature_ma_24h": (-50, 60),
    "heating_degree_days": (0, None),
    "cooling_degree_days": (0, None),
    "humidity": (0, 100),
    "humidity_lag_24h": (0, 100),
    "wind_speed": (0, None),
    "rainfall": (0, None),
}

BOOL_LIKE_FEATURES = frozenset({"is_weekend", "is_holiday", "season_winter", "season_summer"})
SKIP_OUTLIER_FEATURES = BOOL_LIKE_FEATURES | frozenset({"hour", "day_of_week", "month"})

MAX_ISSUE_SAMPLES = 20

# 점수: 100 - (missing*40 + null*25 + invalid*20 + range*10 + outlier*5) 비율 가중 (각 항목 비율 0~1)
SCORE_WEIGHTS = {
    "missing_key": 40.0,
    "null": 25.0,
    "invalid": 20.0,
    "range": 10.0,
    "outlier": 5.0,
}


@dataclass
class FeatureQualityParams:
    feature_set_id: str
    dataset_version_id: str | None = None


def _is_null(val: Any) -> bool:
    if val is None:
        return True
    if isinstance(val, float) and (math.isnan(val) or math.isinf(val)):
        return True
    return False


def _to_float(val: Any) -> float | None:
    if _is_null(val):
        return None
    if isinstance(val, bool):
        return float(val)
    if isinstance(val, (int, float)):
        if math.isnan(val) or math.isinf(val):
            return None
        return float(val)
    if isinstance(val, str):
        text = val.strip().lower()
        if text in ("", "null", "none", "nan"):
            return None
        if text in ("true", "y", "yes"):
            return 1.0
        if text in ("false", "n", "no"):
            return 0.0
        try:
            return float(text)
        except ValueError:
            return None
    return None


def _check_range(feature_name: str, num: float) -> bool:
    rule = RANGE_RULES.get(feature_name)
    if not rule:
        return True
    lo, hi = rule
    if lo is not None and num < lo:
        return False
    if hi is not None and num > hi:
        return False
    return True


def _percentile(arr: np.ndarray, q: float) -> float | None:
    if arr.size == 0:
        return None
    return float(np.percentile(arr, q))


def _feature_status(
    *,
    missing_key_ratio: float,
    null_ratio: float,
    invalid_ratio: float,
    range_ratio: float,
    outlier_ratio: float,
) -> str:
    if missing_key_ratio >= 0.3 or invalid_ratio >= 0.1:
        return "FAILED"
    if null_ratio >= 0.01 or outlier_ratio >= 0.05 or range_ratio > 0:
        return "WARNING"
    return "SUCCESS"


def _compute_score(
    *,
    missing_key_row_ratio: float,
    null_ratio: float,
    invalid_ratio: float,
    range_ratio: float,
    outlier_ratio: float,
) -> float:
    score = 100.0
    score -= min(SCORE_WEIGHTS["missing_key"], missing_key_row_ratio * 100 * (SCORE_WEIGHTS["missing_key"] / 100))
    score -= min(SCORE_WEIGHTS["null"], null_ratio * 100 * (SCORE_WEIGHTS["null"] / 100))
    score -= min(SCORE_WEIGHTS["invalid"], invalid_ratio * 100 * (SCORE_WEIGHTS["invalid"] / 100))
    score -= min(SCORE_WEIGHTS["range"], range_ratio * 100 * (SCORE_WEIGHTS["range"] / 100))
    score -= min(SCORE_WEIGHTS["outlier"], outlier_ratio * 100 * (SCORE_WEIGHTS["outlier"] / 100))
    return round(max(0.0, min(100.0, score)), 1)


def _overall_status(score: float, errors: list[str], warnings: list[str]) -> str:
    if errors:
        return "FAILED"
    if score < 70:
        return "FAILED"
    if score < 90 or warnings:
        return "WARNING"
    return "SUCCESS"


def _append_issue(
    samples: list[dict[str, Any]],
    *,
    feature_name: str,
    site_id: str,
    feature_at: datetime,
    value: Any,
    issue_type: str,
    message: str,
) -> None:
    if len(samples) >= MAX_ISSUE_SAMPLES:
        return
    samples.append(
        {
            "feature_name": feature_name,
            "site_id": site_id,
            "feature_at": feature_at.isoformat() if feature_at else None,
            "value": value,
            "issue_type": issue_type,
            "message": message,
        }
    )


async def run_feature_quality_check(db: AsyncSession, params: FeatureQualityParams) -> dict[str, Any]:
    started = utc_now()
    run_id = f"FQR-{started.strftime('%Y%m%d')}-{uuid4().hex[:6].upper()}"

    fs = (
        await db.execute(select(FeatureSet).where(FeatureSet.feature_set_id == params.feature_set_id))
    ).scalar_one_or_none()
    if not fs:
        raise ValueError(f"Feature Set을 찾을 수 없습니다: {params.feature_set_id}")

    feature_names: list[str] = list(fs.features or [])
    dataset_version_id = params.dataset_version_id or await latest_dataset_version_id(db, params.feature_set_id)

    run = DataQualityRun(
        run_id=run_id,
        source_id=params.feature_set_id,
        check_type="FEATURE_QUALITY",
        run_status="RUNNING",
        started_at=started,
    )
    db.add(run)
    await db.flush()

    errors: list[str] = []
    warnings: list[str] = []
    issue_samples: list[dict[str, Any]] = []

    if not dataset_version_id:
        errors.append("Feature Dataset이 없습니다. 먼저 Feature 생성 작업을 실행하세요.")
        result_summary = _build_failed_summary(
            params.feature_set_id,
            None,
            feature_names,
            errors,
            warnings,
            issue_samples,
            started,
        )
        run.run_status = "FAILED"
        run.finished_at = utc_now()
        run.result_summary = result_summary
        return _run_response(run, result_summary)

    rows = (
        await db.execute(
            select(FeatureDataset)
            .where(
                FeatureDataset.dataset_version_id == dataset_version_id,
                _feature_set_filter(params.feature_set_id),
            )
            .order_by(FeatureDataset.feature_at)
        )
    ).scalars().all()

    row_count = len(rows)
    if row_count == 0:
        errors.append(
            f"dataset_version_id={dataset_version_id} 에 대한 Feature Dataset 행이 없습니다."
        )
        result_summary = _build_failed_summary(
            params.feature_set_id,
            dataset_version_id,
            feature_names,
            errors,
            warnings,
            issue_samples,
            started,
        )
        run.run_status = "FAILED"
        run.finished_at = utc_now()
        run.result_summary = result_summary
        return _run_response(run, result_summary)

    # lineage_error 참고 warning
    lineage_run = (
        await db.execute(
            select(DataQualityRun)
            .where(
                DataQualityRun.check_type == "FEATURE_BUILD",
                DataQualityRun.source_id == params.feature_set_id,
                DataQualityRun.result_summary["dataset_version_id"].astext == dataset_version_id,
            )
            .order_by(DataQualityRun.started_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if lineage_run and isinstance(lineage_run.result_summary, dict):
        lineage_error = lineage_run.result_summary.get("lineage_error")
        if lineage_error:
            warnings.append(f"해당 dataset_version의 Lineage 저장 실패 이력: {lineage_error}")

    feature_at_values = [r.feature_at for r in rows if r.feature_at]
    site_ids = sorted({r.site_id for r in rows})
    time_range = {
        "min_feature_at": min(feature_at_values).isoformat() if feature_at_values else None,
        "max_feature_at": max(feature_at_values).isoformat() if feature_at_values else None,
    }

    # row-level missing key
    rows_with_missing = 0
    for row in rows:
        fj = row.feature_json or {}
        missing = [n for n in feature_names if n not in fj]
        if missing:
            rows_with_missing += 1
            if len(issue_samples) < MAX_ISSUE_SAMPLES:
                _append_issue(
                    issue_samples,
                    feature_name=missing[0],
                    site_id=row.site_id,
                    feature_at=row.feature_at,
                    value=None,
                    issue_type="MISSING_KEY",
                    message=f"feature_json에 {missing[0]} key 없음",
                )

    missing_key_row_ratio = rows_with_missing / row_count if row_count else 0.0
    if missing_key_row_ratio >= 0.3:
        errors.append(f"전체 row의 {missing_key_row_ratio * 100:.1f}%에서 필수 Feature key 누락")

    feature_results: list[dict[str, Any]] = []
    total_null = 0
    total_invalid = 0
    total_range = 0
    total_outlier = 0
    total_cells = 0

    for name in feature_names:
        values: list[float | None] = []
        null_count = 0
        invalid_count = 0
        range_count = 0

        for idx, row in enumerate(rows):
            fj = row.feature_json or {}
            total_cells += 1
            if name not in fj:
                continue
            raw = fj[name]
            if _is_null(raw):
                null_count += 1
                total_null += 1
                if null_count <= 3:
                    _append_issue(
                        issue_samples,
                        feature_name=name,
                        site_id=row.site_id,
                        feature_at=row.feature_at,
                        value=raw,
                        issue_type="NULL",
                        message=f"{name} 값이 null/NaN/Infinity",
                    )
                continue

            num = _to_float(raw)
            if num is None:
                invalid_count += 1
                total_invalid += 1
                _append_issue(
                    issue_samples,
                    feature_name=name,
                    site_id=row.site_id,
                    feature_at=row.feature_at,
                    value=raw,
                    issue_type="INVALID",
                    message=f"{name} 숫자 변환 불가",
                )
                continue

            values.append(num)
            if not _check_range(name, num):
                range_count += 1
                total_range += 1
                _append_issue(
                    issue_samples,
                    feature_name=name,
                    site_id=row.site_id,
                    feature_at=row.feature_at,
                    value=num,
                    issue_type="RANGE_VIOLATION",
                    message=f"{name} 허용 범위 초과",
                )

        present_count = row_count - sum(1 for r in rows if name not in (r.feature_json or {}))
        arr = np.array([v for v in values if v is not None], dtype=float)
        outlier_count = 0
        if name not in SKIP_OUTLIER_FEATURES and arr.size >= 8:
            q1, q3 = np.percentile(arr, [25, 75])
            iqr = q3 - q1
            if iqr > 0:
                low, high = q1 - 1.5 * iqr, q3 + 1.5 * iqr
                for idx, row in enumerate(rows):
                    fj = row.feature_json or {}
                    if name not in fj:
                        continue
                    num = _to_float(fj[name])
                    if num is None:
                        continue
                    if num < low or num > high:
                        outlier_count += 1
                        total_outlier += 1
                        if outlier_count <= 3:
                            _append_issue(
                                issue_samples,
                                feature_name=name,
                                site_id=row.site_id,
                                feature_at=row.feature_at,
                                value=num,
                                issue_type="OUTLIER",
                                message=f"{name} IQR 이상치",
                            )

        count = present_count
        null_ratio = null_count / count if count else 0.0
        invalid_ratio = invalid_count / count if count else 0.0
        range_ratio = range_count / count if count else 0.0
        outlier_ratio = outlier_count / count if count else 0.0

        if invalid_ratio >= 0.1:
            errors.append(f"{name}: invalid 비율 {invalid_ratio * 100:.1f}%")
        elif null_ratio >= 0.01:
            warnings.append(f"{name}: null 비율 {null_ratio * 100:.1f}%")
        if outlier_ratio >= 0.05:
            warnings.append(f"{name}: 이상치 비율 {outlier_ratio * 100:.1f}%")
        if range_count > 0:
            warnings.append(f"{name}: 범위 위반 {range_count}건")

        missing_rows_for_feat = sum(1 for r in rows if name not in (r.feature_json or {}))
        feat_missing_ratio = missing_rows_for_feat / row_count if row_count else 0.0
        feat_status = _feature_status(
            missing_key_ratio=feat_missing_ratio,
            null_ratio=null_ratio,
            invalid_ratio=invalid_ratio,
            range_ratio=range_ratio,
            outlier_ratio=outlier_ratio,
        )

        feature_results.append(
            {
                "feature_name": name,
                "status": feat_status,
                "count": count,
                "null_count": null_count,
                "null_ratio": round(null_ratio, 4),
                "invalid_count": invalid_count,
                "range_violation_count": range_count,
                "outlier_count": outlier_count,
                "min": float(np.min(arr)) if arr.size else None,
                "p25": _percentile(arr, 25),
                "mean": float(np.mean(arr)) if arr.size else None,
                "p50": _percentile(arr, 50),
                "p75": _percentile(arr, 75),
                "max": float(np.max(arr)) if arr.size else None,
                "std": float(np.std(arr)) if arr.size else None,
            }
        )

    null_ratio_all = total_null / total_cells if total_cells else 0.0
    invalid_ratio_all = total_invalid / total_cells if total_cells else 0.0
    range_ratio_all = total_range / total_cells if total_cells else 0.0
    outlier_ratio_all = total_outlier / total_cells if total_cells else 0.0

    score = _compute_score(
        missing_key_row_ratio=missing_key_row_ratio,
        null_ratio=null_ratio_all,
        invalid_ratio=invalid_ratio_all,
        range_ratio=range_ratio_all,
        outlier_ratio=outlier_ratio_all,
    )

    status = _overall_status(score, errors, warnings)

    result_summary: dict[str, Any] = {
        "check_type": "FEATURE_QUALITY",
        "feature_set_id": params.feature_set_id,
        "feature_set_name": fs.feature_set_name,
        "dataset_version_id": dataset_version_id,
        "status": status,
        "score": score,
        "row_count": row_count,
        "feature_count": len(feature_names),
        "checked_at": utc_now().isoformat(),
        "time_range": time_range,
        "site_count": len(site_ids),
        "summary": {
            "missing_key_count": rows_with_missing,
            "null_count": total_null,
            "invalid_count": total_invalid,
            "range_violation_count": total_range,
            "outlier_count": total_outlier,
        },
        "features": feature_results,
        "warnings": warnings,
        "errors": errors,
        "issue_samples": issue_samples,
        "scoring": {
            "base": 100,
            "weights": SCORE_WEIGHTS,
            "thresholds": {"success": 90, "warning": 70},
        },
    }

    run.run_status = status
    run.finished_at = utc_now()
    run.result_summary = result_summary
    return _run_response(run, result_summary)


def _build_failed_summary(
    feature_set_id: str,
    dataset_version_id: str | None,
    feature_names: list[str],
    errors: list[str],
    warnings: list[str],
    issue_samples: list[dict[str, Any]],
    started: datetime,
) -> dict[str, Any]:
    return {
        "check_type": "FEATURE_QUALITY",
        "feature_set_id": feature_set_id,
        "dataset_version_id": dataset_version_id,
        "status": "FAILED",
        "score": 0.0,
        "row_count": 0,
        "feature_count": len(feature_names),
        "checked_at": utc_now().isoformat(),
        "time_range": {"min_feature_at": None, "max_feature_at": None},
        "site_count": 0,
        "summary": {
            "missing_key_count": 0,
            "null_count": 0,
            "invalid_count": 0,
            "range_violation_count": 0,
            "outlier_count": 0,
        },
        "features": [],
        "warnings": warnings,
        "errors": errors,
        "issue_samples": issue_samples,
        "scoring": {"base": 100, "weights": SCORE_WEIGHTS, "thresholds": {"success": 90, "warning": 70}},
    }


def _run_response(run: DataQualityRun, summary: dict[str, Any]) -> dict[str, Any]:
    return {
        "run_id": run.run_id,
        "feature_set_id": summary.get("feature_set_id"),
        "dataset_version_id": summary.get("dataset_version_id"),
        "status": summary.get("status"),
        "score": summary.get("score"),
        "row_count": summary.get("row_count"),
        "feature_count": summary.get("feature_count"),
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "ended_at": run.finished_at.isoformat() if run.finished_at else None,
        "summary": summary.get("summary"),
        "warnings": summary.get("warnings", []),
        "errors": summary.get("errors", []),
        "result_summary": summary,
    }


def _parse_summary(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    return {}


def _run_to_item(run: DataQualityRun, *, include_summary: bool = True) -> dict[str, Any]:
    summary = _parse_summary(run.result_summary)
    item: dict[str, Any] = {
        "run_id": run.run_id,
        "feature_set_id": summary.get("feature_set_id") or run.source_id,
        "dataset_version_id": summary.get("dataset_version_id"),
        "status": summary.get("status") or run.run_status,
        "score": summary.get("score"),
        "row_count": summary.get("row_count"),
        "feature_count": summary.get("feature_count"),
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "ended_at": run.finished_at.isoformat() if run.finished_at else None,
        "summary": summary.get("summary"),
        "warnings": summary.get("warnings", []),
        "errors": summary.get("errors", []),
    }
    if include_summary:
        item["result_summary"] = summary
    return item


async def list_feature_quality_runs(
    db: AsyncSession,
    *,
    feature_set_id: str | None = None,
    dataset_version_id: str | None = None,
    status: str | None = None,
    limit: int = 20,
    offset: int = 0,
    include_summary: bool = False,
) -> dict[str, Any]:
    clauses = [DataQualityRun.check_type == "FEATURE_QUALITY"]
    if feature_set_id:
        clauses.append(DataQualityRun.source_id == feature_set_id)
    if status:
        clauses.append(DataQualityRun.run_status == status)
    if dataset_version_id:
        clauses.append(DataQualityRun.result_summary["dataset_version_id"].astext == dataset_version_id)

    where = and_(*clauses)
    total = int((await db.execute(select(func.count()).select_from(DataQualityRun).where(where))).scalar_one() or 0)
    rows = (
        await db.execute(
            select(DataQualityRun)
            .where(where)
            .order_by(DataQualityRun.started_at.desc())
            .limit(limit)
            .offset(offset)
        )
    ).scalars().all()
    items = [_run_to_item(r, include_summary=include_summary) for r in rows]
    return {"items": items, "total": total, "limit": limit, "offset": offset}


async def get_feature_quality_run(db: AsyncSession, run_id: str) -> dict[str, Any] | None:
    run = (
        await db.execute(
            select(DataQualityRun).where(
                DataQualityRun.run_id == run_id,
                DataQualityRun.check_type == "FEATURE_QUALITY",
            )
        )
    ).scalar_one_or_none()
    if not run:
        return None
    return _run_to_item(run, include_summary=True)
