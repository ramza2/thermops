"""시스템 설정 조회·수정 서비스."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.time import utc_now
from app.models.entities import SystemConfig

DEFAULT_CONFIG_VALUES: dict[str, str] = {
    "default_model_name": "heat_demand_lightgbm",
    "mape_warning_threshold": "8.0",
    "drift_warning_threshold": "0.40",
    "retraining_mape_threshold": "10.0",
    "batch_prediction_default_horizon": "24",
    "system_version": "0.1.0",
}


def _is_editable(row: SystemConfig) -> bool:
    return (row.editable_yn or "Y").upper() == "Y"


def config_to_dict(row: SystemConfig) -> dict[str, Any]:
    return {
        "config_key": row.config_key,
        "config_name": row.config_name or row.config_key,
        "config_value": row.config_value,
        "config_type": row.config_type,
        "description": row.description,
        "editable_yn": _is_editable(row),
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


async def list_system_configs(db: AsyncSession) -> list[dict[str, Any]]:
    rows = (
        await db.execute(select(SystemConfig).order_by(SystemConfig.config_key))
    ).scalars().all()
    return [config_to_dict(r) for r in rows]


async def get_system_config(db: AsyncSession, config_key: str) -> dict[str, Any] | None:
    row = (
        await db.execute(select(SystemConfig).where(SystemConfig.config_key == config_key))
    ).scalar_one_or_none()
    return config_to_dict(row) if row else None


async def update_system_config(
    db: AsyncSession,
    config_key: str,
    config_value: str,
    updated_by: str | None = None,
) -> dict[str, Any]:
    row = (
        await db.execute(select(SystemConfig).where(SystemConfig.config_key == config_key))
    ).scalar_one_or_none()
    if not row:
        raise ValueError(f"설정 키를 찾을 수 없습니다: {config_key}")
    if not _is_editable(row):
        raise PermissionError(f"수정할 수 없는 설정입니다: {config_key}")

    row.config_value = config_value
    row.updated_by = updated_by
    row.updated_at = utc_now()
    await db.flush()
    return config_to_dict(row)


async def reset_system_configs(db: AsyncSession, updated_by: str | None = None) -> list[dict[str, Any]]:
    rows = (await db.execute(select(SystemConfig))).scalars().all()
    now = utc_now()
    updated: list[dict[str, Any]] = []
    for row in rows:
        if not _is_editable(row):
            continue
        default_val = DEFAULT_CONFIG_VALUES.get(row.config_key)
        if default_val is None:
            continue
        row.config_value = default_val
        row.updated_by = updated_by
        row.updated_at = now
        updated.append(config_to_dict(row))
    await db.flush()
    return updated
