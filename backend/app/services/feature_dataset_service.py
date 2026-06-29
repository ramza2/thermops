"""Feature Dataset 조회·기간 검증."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.time import to_db_datetime
from app.models.entities import FeatureDataset, FeatureSet


class PredictionPeriodError(ValueError):
    """예측 기간 / Feature Dataset 범위 오류."""

    def __init__(self, error_code: str, message: str, **fields: Any):
        self.error_code = error_code
        self.message = message
        self.fields = fields
        super().__init__(message)

    def to_dict(self) -> dict[str, Any]:
        return {"error_code": self.error_code, "message": self.message, **self.fields}


def _format_db_datetime(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    return to_db_datetime(dt).isoformat(timespec="seconds")


def _feature_set_filter(feature_set_id: str):
    return FeatureDataset.feature_json["feature_set_id"].astext == feature_set_id


async def latest_dataset_version_id(db: AsyncSession, feature_set_id: str) -> str | None:
    row = (
        await db.execute(
            select(FeatureDataset.dataset_version_id)
            .where(_feature_set_filter(feature_set_id))
            .group_by(FeatureDataset.dataset_version_id)
            .order_by(func.max(FeatureDataset.created_at).desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    return row


async def get_feature_dataset_range(
    db: AsyncSession,
    feature_set_id: str,
    *,
    site_ids: list[str] | None = None,
) -> dict[str, Any]:
    """최신 dataset_version 기준 Feature Dataset 시간 범위 (DB 컬럼: feature_at)."""
    fs = (
        await db.execute(select(FeatureSet).where(FeatureSet.feature_set_id == feature_set_id))
    ).scalar_one_or_none()
    if not fs:
        raise ValueError(f"Feature Set을 찾을 수 없습니다: {feature_set_id}")

    dataset_version_id = await latest_dataset_version_id(db, feature_set_id)
    empty: dict[str, Any] = {
        "feature_set_id": feature_set_id,
        "exists": False,
        "row_count": 0,
        "min_target_at": None,
        "max_target_at": None,
        "site_count": 0,
        "sites": [],
        "dataset_version_id": None,
    }
    if not dataset_version_id:
        return empty

    base = and_clauses(dataset_version_id, feature_set_id, site_ids)
    agg = (
        await db.execute(
            select(
                func.count().label("row_count"),
                func.min(FeatureDataset.feature_at).label("min_at"),
                func.max(FeatureDataset.feature_at).label("max_at"),
                func.count(func.distinct(FeatureDataset.site_id)).label("site_count"),
            ).where(*base)
        )
    ).one()

    row_count = int(agg.row_count or 0)
    if row_count == 0:
        return empty

    site_rows = (
        await db.execute(
            select(
                FeatureDataset.site_id,
                func.min(FeatureDataset.feature_at).label("min_at"),
                func.max(FeatureDataset.feature_at).label("max_at"),
                func.count().label("row_count"),
            )
            .where(
                FeatureDataset.dataset_version_id == dataset_version_id,
                _feature_set_filter(feature_set_id),
            )
            .group_by(FeatureDataset.site_id)
            .order_by(FeatureDataset.site_id)
        )
    ).all()

    sites = [
        {
            "site_id": row.site_id,
            "min_target_at": _format_db_datetime(row.min_at),
            "max_target_at": _format_db_datetime(row.max_at),
            "row_count": int(row.row_count),
        }
        for row in site_rows
    ]

    return {
        "feature_set_id": feature_set_id,
        "exists": True,
        "row_count": row_count,
        "min_target_at": _format_db_datetime(agg.min_at),
        "max_target_at": _format_db_datetime(agg.max_at),
        "site_count": int(agg.site_count or 0),
        "sites": sites,
        "dataset_version_id": dataset_version_id,
    }


def and_clauses(
    dataset_version_id: str,
    feature_set_id: str,
    site_ids: list[str] | None,
) -> list:
    clauses = [
        FeatureDataset.dataset_version_id == dataset_version_id,
        _feature_set_filter(feature_set_id),
    ]
    if site_ids:
        clauses.append(FeatureDataset.site_id.in_(site_ids))
    return clauses


async def validate_prediction_period(
    db: AsyncSession,
    feature_set_id: str,
    start_at: datetime,
    end_at: datetime,
    site_ids: list[str] | None = None,
) -> dict[str, Any]:
    """예측 기간이 Feature Dataset 범위 안인지 검증. 통과 시 range dict 반환."""
    start_at = to_db_datetime(start_at)
    end_at = to_db_datetime(end_at)
    if start_at > end_at:
        raise PredictionPeriodError(
            "INVALID_PREDICTION_PERIOD",
            "start_at must be before or equal to end_at.",
            feature_set_id=feature_set_id,
            requested_start_at=_format_db_datetime(start_at),
            requested_end_at=_format_db_datetime(end_at),
        )

    range_info = await get_feature_dataset_range(db, feature_set_id, site_ids=site_ids)
    if not range_info["exists"]:
        raise PredictionPeriodError(
            "NO_FEATURE_DATASET",
            f"No feature dataset exists for feature_set_id={feature_set_id}. Please run feature generation first.",
            feature_set_id=feature_set_id,
        )

    min_at = datetime.fromisoformat(range_info["min_target_at"])
    max_at = datetime.fromisoformat(range_info["max_target_at"])
    if start_at < min_at or end_at > max_at:
        raise PredictionPeriodError(
            "PREDICTION_PERIOD_OUT_OF_FEATURE_RANGE",
            "Prediction period is outside the available feature dataset range.",
            feature_set_id=feature_set_id,
            requested_start_at=_format_db_datetime(start_at),
            requested_end_at=_format_db_datetime(end_at),
            available_start_at=range_info["min_target_at"],
            available_end_at=range_info["max_target_at"],
        )

    return range_info
