"""데이터 적재 서비스 — CSV/DB/API Connector 공통."""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.time import utc_now
from app.models.entities import DataMapping, DataQualityRun, DataSource, HeatDemandActual, WeatherObservation
from app.services.connectors.base import ConnectorError
from app.services.connectors.registry import get_connector, normalize_source_type
from app.services.mapping_service import (
    HEAT_TARGET,
    WEATHER_TARGET,
    _target_table_key,
    normalize_row_for_insert,
)


class IngestionError(Exception):
    pass


async def get_active_mapping(db: AsyncSession, source_id: str) -> DataMapping | None:
    result = await db.execute(
        select(DataMapping)
        .where(DataMapping.source_id == source_id, DataMapping.active_yn == "Y")
        .order_by(DataMapping.created_at.desc())
    )
    return result.scalars().first()


async def run_ingestion(
    db: AsyncSession,
    source_id: str,
    job_id: str,
    *,
    start_at: datetime | None = None,
    end_at: datetime | None = None,
    limit: int | None = None,
) -> dict[str, Any]:
    source = (
        await db.execute(select(DataSource).where(DataSource.data_source_id == source_id))
    ).scalar_one_or_none()
    if not source:
        raise IngestionError("데이터 소스를 찾을 수 없습니다.")
    if source.active_yn != "Y":
        raise IngestionError("비활성 데이터 소스입니다.")

    mapping = await get_active_mapping(db, source_id)
    if not mapping:
        raise IngestionError("연결된 활성 매핑이 없습니다.")

    table = _target_table_key(mapping)
    if table not in (HEAT_TARGET, WEATHER_TARGET):
        raise IngestionError(f"지원하지 않는 저장 대상: {mapping.target_table}")

    try:
        connector = get_connector(source)
        mapped_rows, _ = await asyncio.to_thread(
            connector.fetch_rows,
            source,
            mapping=mapping,
            start_at=start_at,
            end_at=end_at,
            limit=limit,
        )
    except ConnectorError as exc:
        raise IngestionError(str(exc)) from exc

    inserted = 0
    failed = 0
    skipped = 0
    missing_optional = 0
    duplicate_keys: set[tuple] = set()
    duplicate_in_file = 0
    warnings: list[str] = []
    now = utc_now()
    source_type = normalize_source_type(source.source_type)

    for raw_mapped in mapped_rows:
        normalized = normalize_row_for_insert(raw_mapped, mapping)
        if normalized is None:
            failed += 1
            continue

        if table == HEAT_TARGET:
            key = (normalized["site_id"], normalized["measured_at"])
            if key in duplicate_keys:
                duplicate_in_file += 1
                skipped += 1
                continue
            duplicate_keys.add(key)

            for col in ("supply_temp", "return_temp", "flow_rate"):
                if col not in normalized:
                    missing_optional += 1
                    break

            stmt = pg_insert(HeatDemandActual).values(
                site_id=normalized["site_id"],
                measured_at=normalized["measured_at"],
                heat_demand=normalized["heat_demand"],
                supply_temp=normalized.get("supply_temp"),
                return_temp=normalized.get("return_temp"),
                flow_rate=normalized.get("flow_rate"),
                loaded_at=now,
            )
            stmt = stmt.on_conflict_do_update(
                constraint="uk_heat_actual",
                set_={
                    "heat_demand": stmt.excluded.heat_demand,
                    "supply_temp": stmt.excluded.supply_temp,
                    "return_temp": stmt.excluded.return_temp,
                    "flow_rate": stmt.excluded.flow_rate,
                    "loaded_at": stmt.excluded.loaded_at,
                },
            )
        else:
            key = (
                normalized["weather_area_id"],
                normalized["measured_at"],
                normalized["data_type"],
            )
            if key in duplicate_keys:
                duplicate_in_file += 1
                skipped += 1
                continue
            duplicate_keys.add(key)

            stmt = pg_insert(WeatherObservation).values(
                weather_area_id=normalized["weather_area_id"],
                measured_at=normalized["measured_at"],
                data_type=normalized["data_type"],
                temperature=normalized.get("temperature"),
                humidity=normalized.get("humidity"),
                wind_speed=normalized.get("wind_speed"),
                rainfall=normalized.get("rainfall"),
                apparent_temp=normalized.get("apparent_temp"),
                loaded_at=now,
            )
            stmt = stmt.on_conflict_do_update(
                constraint="uk_weather_obs",
                set_={
                    "temperature": stmt.excluded.temperature,
                    "humidity": stmt.excluded.humidity,
                    "wind_speed": stmt.excluded.wind_speed,
                    "rainfall": stmt.excluded.rainfall,
                    "apparent_temp": stmt.excluded.apparent_temp,
                    "loaded_at": stmt.excluded.loaded_at,
                },
            )

        await db.execute(stmt)
        inserted += 1

    source.last_loaded_at = now

    run = (
        await db.execute(select(DataQualityRun).where(DataQualityRun.run_id == job_id))
    ).scalar_one_or_none()
    summary = {
        "inserted_count": inserted,
        "updated_count": inserted,
        "failed_count": failed,
        "skipped_count": skipped,
        "duplicate_count": duplicate_in_file,
        "missing_optional_count": missing_optional,
        "source_row_count": len(mapped_rows),
        "target_table": mapping.target_table,
        "source_type": source_type,
        "connector_type": source_type,
        "warnings": warnings,
    }
    status = "SUCCESS" if inserted > 0 or len(mapped_rows) == 0 else "FAILED"
    if run:
        run.run_status = status
        run.finished_at = now
        run.result_summary = summary
        if status == "FAILED":
            run.result_summary = {**summary, "error_message": "적재된 행이 없습니다."}

    return {
        "job_id": job_id,
        "status": status,
        "inserted_count": inserted,
        "failed_count": failed,
        "result_summary": summary,
        "source_type": source_type,
    }


async def fail_ingestion_job(db: AsyncSession, job_id: str, error_message: str) -> None:
    run = (
        await db.execute(select(DataQualityRun).where(DataQualityRun.run_id == job_id))
    ).scalar_one_or_none()
    if run:
        run.run_status = "FAILED"
        run.finished_at = utc_now()
        run.result_summary = {"error_message": error_message}
