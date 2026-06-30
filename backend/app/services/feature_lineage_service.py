"""Feature Lineage 저장·조회."""

from __future__ import annotations

import sys
from datetime import datetime
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.time import utc_now
from app.models.entities import FeatureLineage


class LineageTableMissingError(RuntimeError):
    """tb_feature_lineage 미적용 DB."""


def _is_missing_lineage_table(exc: BaseException) -> bool:
    msg = str(exc).lower()
    return "tb_feature_lineage" in msg and "does not exist" in msg


def _load_ml_registry():
    from pathlib import Path

    root = get_settings().project_root
    for candidate in (root / "ml", Path("/ml"), Path(__file__).resolve().parents[3] / "ml"):
        if candidate.exists():
            p = str(candidate.resolve())
            if p not in sys.path:
                sys.path.insert(0, p)
            break
    import feature_registry as reg  # noqa: WPS433

    return reg


def _spec_or_fallback(reg, feature_name: str):
    spec = reg.get_feature_spec(feature_name)
    if spec:
        return spec
    from feature_registry import FeatureSpec  # noqa: WPS433

    return FeatureSpec(
        feature_name=feature_name,
        display_name=feature_name,
        feature_group="미등록",
        feature_type="UNKNOWN",
        calc_method="CODE",
        calc_expression="",
        description="Registry에 미등록 Feature (Feature Set에만 포함됨)",
    )


async def delete_lineage_for_dataset(db: AsyncSession, dataset_version_id: str) -> None:
    await db.execute(
        delete(FeatureLineage).where(FeatureLineage.dataset_version_id == dataset_version_id)
    )


async def save_feature_lineage(
    db: AsyncSession,
    *,
    dataset_version_id: str,
    job_id: str,
    feature_set_id: str,
    site_filter: str | None,
    feature_names: list[str],
    build_start_at: datetime,
    build_end_at: datetime,
    site_ids: list[str],
) -> int:
    """Feature Set에 포함된 각 Feature별 lineage 1행 저장."""
    reg = _load_ml_registry()
    await delete_lineage_for_dataset(db, dataset_version_id)

    now = utc_now()
    inserted = 0
    for name in feature_names:
        spec = _spec_or_fallback(reg, name)
        lineage_json: dict[str, Any] = {
            "registry_version": reg.REGISTRY_VERSION,
            "feature_set_id": feature_set_id,
            "feature_build_job_id": job_id,
            "site_filter": site_filter,
            "site_ids": site_ids,
            "spec": spec.to_dict(),
        }
        row = FeatureLineage(
            dataset_version_id=dataset_version_id,
            feature_build_job_id=job_id,
            feature_set_id=feature_set_id,
            feature_name=name,
            registry_version=reg.REGISTRY_VERSION,
            calc_method=spec.calc_method,
            calc_expression=spec.calc_expression,
            source_tables=spec.source_tables,
            source_columns=spec.source_columns,
            partition_keys=spec.partition_keys,
            time_key=spec.time_key,
            lookback_hours=spec.lookback_hours,
            requires_shift=spec.requires_shift,
            leakage_safe=spec.leakage_safe,
            build_start_at=build_start_at,
            build_end_at=build_end_at,
            site_filter=site_filter,
            lineage_json=lineage_json,
            created_at=now,
        )
        db.add(row)
        inserted += 1
    return inserted


def _lineage_row_to_dict(row: FeatureLineage) -> dict[str, Any]:
    return {
        "lineage_id": row.lineage_id,
        "dataset_version_id": row.dataset_version_id,
        "feature_build_job_id": row.feature_build_job_id,
        "feature_set_id": row.feature_set_id,
        "feature_name": row.feature_name,
        "registry_version": row.registry_version,
        "calc_method": row.calc_method,
        "calc_expression": row.calc_expression,
        "source_tables": row.source_tables or [],
        "source_columns": row.source_columns or [],
        "partition_keys": row.partition_keys or [],
        "time_key": row.time_key,
        "lookback_hours": row.lookback_hours,
        "requires_shift": row.requires_shift,
        "leakage_safe": row.leakage_safe,
        "build_start_at": row.build_start_at.isoformat() if row.build_start_at else None,
        "build_end_at": row.build_end_at.isoformat() if row.build_end_at else None,
        "site_filter": row.site_filter,
        "lineage_json": row.lineage_json,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


async def get_lineage_by_dataset_version(db: AsyncSession, dataset_version_id: str) -> list[dict[str, Any]]:
    try:
        rows = (
            await db.execute(
                select(FeatureLineage)
                .where(FeatureLineage.dataset_version_id == dataset_version_id)
                .order_by(FeatureLineage.feature_name)
            )
        ).scalars().all()
    except ProgrammingError as exc:
        if _is_missing_lineage_table(exc):
            raise LineageTableMissingError(
                "tb_feature_lineage 테이블이 없습니다. 호스트에서 python3 scripts/apply_dev_migrations.py 를 실행하세요."
            ) from exc
        raise
    return [_lineage_row_to_dict(r) for r in rows]


async def get_lineage_by_job_id(db: AsyncSession, job_id: str) -> list[dict[str, Any]]:
    try:
        rows = (
            await db.execute(
                select(FeatureLineage)
                .where(FeatureLineage.feature_build_job_id == job_id)
                .order_by(FeatureLineage.feature_name)
            )
        ).scalars().all()
    except ProgrammingError as exc:
        if _is_missing_lineage_table(exc):
            raise LineageTableMissingError(
                "tb_feature_lineage 테이블이 없습니다. 호스트에서 python3 scripts/apply_dev_migrations.py 를 실행하세요."
            ) from exc
        raise
    return [_lineage_row_to_dict(r) for r in rows]


def list_registry_specs() -> dict[str, Any]:
    reg = _load_ml_registry()
    return {
        "registry_version": reg.REGISTRY_VERSION,
        "features": [s.to_dict() for s in reg.list_feature_specs()],
    }


def get_registry_spec(feature_name: str) -> dict[str, Any] | None:
    reg = _load_ml_registry()
    spec = reg.get_feature_spec(feature_name)
    if not spec:
        return None
    payload = spec.to_dict()
    payload["registry_version"] = reg.REGISTRY_VERSION
    return payload
