"""예측용 기상 입력 행 저장 (R10-S5)."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.time import utc_now
from app.models.entities import PredictionWeatherInput


def _new_id(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex[:8].upper()}"


def _weather_input_dict(row: PredictionWeatherInput) -> dict[str, Any]:
    return {
        "weather_input_id": row.weather_input_id,
        "prediction_job_id": row.prediction_job_id,
        "snapshot_id": row.snapshot_id,
        "entity_id": row.entity_id,
        "forecast_base_at": row.forecast_base_at.isoformat() if row.forecast_base_at else None,
        "forecast_target_at": row.forecast_target_at.isoformat() if row.forecast_target_at else None,
        "forecast_horizon_hours": row.forecast_horizon_hours,
        "nx": row.nx,
        "ny": row.ny,
        "temperature": float(row.temperature) if row.temperature is not None else None,
        "humidity": float(row.humidity) if row.humidity is not None else None,
        "wind_speed": float(row.wind_speed) if row.wind_speed is not None else None,
        "precipitation": float(row.precipitation) if row.precipitation is not None else None,
        "precipitation_probability": float(row.precipitation_probability)
        if row.precipitation_probability is not None
        else None,
        "sky_condition": row.sky_condition,
        "precipitation_type": row.precipitation_type,
        "raw_category_values_json": row.raw_category_values_json,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


async def save_prediction_weather_inputs(
    db: AsyncSession,
    *,
    prediction_job_id: str,
    snapshot_id: str | None,
    entity_id: str | None,
    nx: int,
    ny: int,
    rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    now = utc_now()
    saved: list[dict[str, Any]] = []
    for row in rows:
        target_text = row.get("forecast_target_at")
        if not target_text:
            continue
        target_at = datetime.fromisoformat(str(target_text))
        base_at = None
        if row.get("forecast_base_at"):
            base_at = datetime.fromisoformat(str(row["forecast_base_at"]))
        entity = PredictionWeatherInput(
            weather_input_id=_new_id("PWI"),
            prediction_job_id=prediction_job_id,
            snapshot_id=snapshot_id,
            entity_id=entity_id,
            forecast_base_at=base_at,
            forecast_target_at=target_at,
            forecast_horizon_hours=row.get("forecast_horizon_hours"),
            nx=nx,
            ny=ny,
            temperature=row.get("temperature"),
            humidity=row.get("humidity"),
            wind_speed=row.get("wind_speed"),
            precipitation=row.get("precipitation"),
            precipitation_probability=row.get("precipitation_probability"),
            sky_condition=row.get("sky_condition"),
            precipitation_type=row.get("precipitation_type"),
            raw_category_values_json=row.get("raw_category_values_json"),
            created_at=now,
        )
        db.add(entity)
        saved.append(_weather_input_dict(entity))
    await db.flush()
    return saved


async def list_prediction_weather_inputs(
    db: AsyncSession,
    prediction_job_id: str,
) -> list[dict[str, Any]]:
    rows = (
        await db.execute(
            select(PredictionWeatherInput)
            .where(PredictionWeatherInput.prediction_job_id == prediction_job_id)
            .order_by(PredictionWeatherInput.forecast_target_at)
        )
    ).scalars().all()
    return [_weather_input_dict(r) for r in rows]
