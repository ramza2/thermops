"""기상 격자·관측소·예측 대상 기상 매핑 서비스."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.time import utc_now
from app.models.entities import (
    PredictionEntityWeatherMapping,
    WeatherForecastGrid,
    WeatherObservationStation,
)
from app.services.prediction_entity_service import (
    PredictionEntityError,
    _get_entity,
    get_active_location,
)
from app.utils.kma_grid import latlon_to_kma_grid, validate_kma_grid, validate_latlon

MAPPING_TYPES = frozenset({"FORECAST_GRID", "OBSERVATION_STATION", "BOTH"})
MAPPING_METHODS = frozenset({"MANUAL", "LATLON_TO_GRID", "NEAREST_STATION", "ADMIN_AREA", "IMPORTED"})
STATION_TYPES = frozenset({"ASOS", "AWS", "CUSTOM"})


def _new_id(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex[:8].upper()}"


def _grid_dict(g: WeatherForecastGrid) -> dict[str, Any]:
    return {
        "forecast_grid_id": g.forecast_grid_id,
        "grid_system": g.grid_system,
        "nx": g.nx,
        "ny": g.ny,
        "grid_name": g.grid_name,
        "latitude": float(g.latitude) if g.latitude is not None else None,
        "longitude": float(g.longitude) if g.longitude is not None else None,
        "active_yn": bool(g.active_yn),
        "metadata_json": g.metadata_json,
        "created_at": g.created_at.isoformat() if g.created_at else None,
        "updated_at": g.updated_at.isoformat() if g.updated_at else None,
    }


def _station_dict(s: WeatherObservationStation) -> dict[str, Any]:
    return {
        "station_id": s.station_id,
        "station_code": s.station_code,
        "station_name": s.station_name,
        "station_type": s.station_type,
        "latitude": float(s.latitude) if s.latitude is not None else None,
        "longitude": float(s.longitude) if s.longitude is not None else None,
        "address": s.address,
        "active_yn": bool(s.active_yn),
        "metadata_json": s.metadata_json,
        "created_at": s.created_at.isoformat() if s.created_at else None,
        "updated_at": s.updated_at.isoformat() if s.updated_at else None,
    }


def _mapping_dict(m: PredictionEntityWeatherMapping, *, grid=None, station=None) -> dict[str, Any]:
    data = {
        "mapping_id": m.mapping_id,
        "entity_id": m.entity_id,
        "forecast_grid_id": m.forecast_grid_id,
        "station_id": m.station_id,
        "mapping_type": m.mapping_type,
        "mapping_method": m.mapping_method,
        "distance_km": float(m.distance_km) if m.distance_km is not None else None,
        "priority": m.priority,
        "valid_from": m.valid_from.isoformat() if m.valid_from else None,
        "valid_to": m.valid_to.isoformat() if m.valid_to else None,
        "active_yn": bool(m.active_yn),
        "metadata_json": m.metadata_json,
        "created_at": m.created_at.isoformat() if m.created_at else None,
        "updated_at": m.updated_at.isoformat() if m.updated_at else None,
    }
    if grid:
        data["forecast_grid"] = _grid_dict(grid)
    if station:
        data["observation_station"] = _station_dict(station)
    return data


async def list_forecast_grids(db: AsyncSession, *, active_only: bool = True) -> list[dict[str, Any]]:
    q = select(WeatherForecastGrid).order_by(WeatherForecastGrid.nx, WeatherForecastGrid.ny)
    if active_only:
        q = q.where(WeatherForecastGrid.active_yn.is_(True))
    rows = (await db.execute(q)).scalars().all()
    return [_grid_dict(r) for r in rows]


async def upsert_forecast_grid(db: AsyncSession, payload: dict[str, Any]) -> dict[str, Any]:
    nx = int(payload["nx"])
    ny = int(payload["ny"])
    validate_kma_grid(nx, ny)
    system = (payload.get("grid_system") or "KMA_DFS").strip()
    existing = (
        await db.execute(
            select(WeatherForecastGrid).where(
                WeatherForecastGrid.grid_system == system,
                WeatherForecastGrid.nx == nx,
                WeatherForecastGrid.ny == ny,
            )
        )
    ).scalar_one_or_none()
    now = utc_now()
    if existing:
        grid = existing
        grid.grid_name = payload.get("grid_name") or grid.grid_name
        if payload.get("latitude") is not None:
            grid.latitude = payload.get("latitude")
        if payload.get("longitude") is not None:
            grid.longitude = payload.get("longitude")
        grid.active_yn = bool(payload.get("active_yn", True))
        grid.metadata_json = payload.get("metadata_json") or grid.metadata_json
        grid.updated_at = now
    else:
        grid = WeatherForecastGrid(
            forecast_grid_id=_new_id("WFG"),
            grid_system=system,
            nx=nx,
            ny=ny,
            grid_name=payload.get("grid_name"),
            latitude=payload.get("latitude"),
            longitude=payload.get("longitude"),
            active_yn=bool(payload.get("active_yn", True)),
            metadata_json=payload.get("metadata_json"),
            created_at=now,
            updated_at=now,
        )
        db.add(grid)
    await db.flush()
    return _grid_dict(grid)


async def list_observation_stations(db: AsyncSession, *, active_only: bool = True) -> list[dict[str, Any]]:
    q = select(WeatherObservationStation).order_by(WeatherObservationStation.station_code)
    if active_only:
        q = q.where(WeatherObservationStation.active_yn.is_(True))
    rows = (await db.execute(q)).scalars().all()
    return [_station_dict(r) for r in rows]


async def upsert_observation_station(db: AsyncSession, payload: dict[str, Any]) -> dict[str, Any]:
    code = (payload.get("station_code") or "").strip()
    name = (payload.get("station_name") or "").strip()
    if not code:
        raise PredictionEntityError("관측소 코드는 필수입니다.", error_code="MISSING_STATION_CODE")
    if not name:
        raise PredictionEntityError("관측소명은 필수입니다.", error_code="MISSING_STATION_NAME")
    stype = (payload.get("station_type") or "ASOS").upper()
    if stype not in STATION_TYPES:
        raise PredictionEntityError(f"지원하지 않는 관측소 유형입니다: {stype}", error_code="INVALID_STATION_TYPE")
    lat = payload.get("latitude")
    lon = payload.get("longitude")
    if lat is not None and lon is not None:
        validate_latlon(float(lat), float(lon))
    existing = (
        await db.execute(select(WeatherObservationStation).where(WeatherObservationStation.station_code == code))
    ).scalar_one_or_none()
    now = utc_now()
    if existing:
        st = existing
        st.station_name = name
        st.station_type = stype
        st.latitude = lat if lat is not None else st.latitude
        st.longitude = lon if lon is not None else st.longitude
        st.address = payload.get("address") or st.address
        st.active_yn = bool(payload.get("active_yn", True))
        st.metadata_json = payload.get("metadata_json") or st.metadata_json
        st.updated_at = now
    else:
        st = WeatherObservationStation(
            station_id=_new_id("WOS"),
            station_code=code,
            station_name=name,
            station_type=stype,
            latitude=lat,
            longitude=lon,
            address=payload.get("address"),
            active_yn=bool(payload.get("active_yn", True)),
            metadata_json=payload.get("metadata_json"),
            created_at=now,
            updated_at=now,
        )
        db.add(st)
    await db.flush()
    return _station_dict(st)


async def list_weather_mappings(db: AsyncSession, entity_id: str) -> list[dict[str, Any]]:
    await _get_entity(db, entity_id)
    rows = (
        await db.execute(
            select(PredictionEntityWeatherMapping)
            .where(PredictionEntityWeatherMapping.entity_id == entity_id)
            .order_by(PredictionEntityWeatherMapping.priority, PredictionEntityWeatherMapping.created_at.desc())
        )
    ).scalars().all()
    out = []
    for m in rows:
        grid = None
        station = None
        if m.forecast_grid_id:
            grid = (
                await db.execute(
                    select(WeatherForecastGrid).where(WeatherForecastGrid.forecast_grid_id == m.forecast_grid_id)
                )
            ).scalar_one_or_none()
        if m.station_id:
            station = (
                await db.execute(
                    select(WeatherObservationStation).where(WeatherObservationStation.station_id == m.station_id)
                )
            ).scalar_one_or_none()
        out.append(_mapping_dict(m, grid=grid, station=station))
    return out


async def create_weather_mapping(db: AsyncSession, entity_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    await _get_entity(db, entity_id)
    fg_id = payload.get("forecast_grid_id")
    st_id = payload.get("station_id")
    if not fg_id and not st_id:
        raise PredictionEntityError(
            "단기예보 격자 또는 관측소 중 하나 이상을 지정해야 합니다.",
            error_code="MISSING_MAPPING_TARGET",
        )
    mtype = (payload.get("mapping_type") or "BOTH").upper()
    if mtype not in MAPPING_TYPES:
        raise PredictionEntityError("지원하지 않는 매핑 유형입니다.", error_code="INVALID_MAPPING_TYPE")
    method = (payload.get("mapping_method") or "MANUAL").upper()
    if method not in MAPPING_METHODS:
        raise PredictionEntityError("지원하지 않는 매핑 방식입니다.", error_code="INVALID_MAPPING_METHOD")
    now = utc_now()
    mapping = PredictionEntityWeatherMapping(
        mapping_id=_new_id("PWM"),
        entity_id=entity_id,
        forecast_grid_id=fg_id,
        station_id=st_id,
        mapping_type=mtype,
        mapping_method=method,
        distance_km=payload.get("distance_km"),
        priority=int(payload.get("priority", 1)),
        valid_from=payload.get("valid_from"),
        valid_to=payload.get("valid_to"),
        active_yn=bool(payload.get("active_yn", True)),
        metadata_json=payload.get("metadata_json"),
        created_at=now,
        updated_at=now,
    )
    db.add(mapping)
    await db.flush()
    return _mapping_dict(mapping)


async def update_weather_mapping(
    db: AsyncSession, entity_id: str, mapping_id: str, payload: dict[str, Any]
) -> dict[str, Any]:
    await _get_entity(db, entity_id)
    mapping = (
        await db.execute(
            select(PredictionEntityWeatherMapping).where(
                PredictionEntityWeatherMapping.mapping_id == mapping_id,
                PredictionEntityWeatherMapping.entity_id == entity_id,
            )
        )
    ).scalar_one_or_none()
    if not mapping:
        raise PredictionEntityError("기상 매핑을 찾을 수 없습니다.", error_code="MAPPING_NOT_FOUND")
    for key in (
        "forecast_grid_id", "station_id", "mapping_type", "mapping_method",
        "distance_km", "priority", "valid_from", "valid_to", "active_yn", "metadata_json",
    ):
        if key in payload:
            setattr(mapping, key, payload[key])
    if not mapping.forecast_grid_id and not mapping.station_id:
        raise PredictionEntityError(
            "단기예보 격자 또는 관측소 중 하나 이상을 지정해야 합니다.",
            error_code="MISSING_MAPPING_TARGET",
        )
    mapping.updated_at = utc_now()
    await db.flush()
    return _mapping_dict(mapping)


async def archive_weather_mapping(db: AsyncSession, entity_id: str, mapping_id: str) -> dict[str, Any]:
    await _get_entity(db, entity_id)
    mapping = (
        await db.execute(
            select(PredictionEntityWeatherMapping).where(
                PredictionEntityWeatherMapping.mapping_id == mapping_id,
                PredictionEntityWeatherMapping.entity_id == entity_id,
            )
        )
    ).scalar_one_or_none()
    if not mapping:
        raise PredictionEntityError("기상 매핑을 찾을 수 없습니다.", error_code="MAPPING_NOT_FOUND")
    now = utc_now()
    mapping.active_yn = False
    mapping.archived_at = now
    mapping.updated_at = now
    await db.flush()
    return _mapping_dict(mapping)


async def compute_weather_readiness(db: AsyncSession, entity_id: str) -> dict[str, Any]:
    await _get_entity(db, entity_id)
    loc = await get_active_location(db, entity_id)
    location_ready = bool(
        loc and loc.latitude is not None and loc.longitude is not None
    )
    mappings = (
        await db.execute(
            select(PredictionEntityWeatherMapping).where(
                PredictionEntityWeatherMapping.entity_id == entity_id,
                PredictionEntityWeatherMapping.active_yn.is_(True),
            )
        )
    ).scalars().all()
    forecast_ready = False
    observation_ready = False
    warnings: list[str] = []
    for m in mappings:
        if m.forecast_grid_id:
            grid = (
                await db.execute(
                    select(WeatherForecastGrid).where(
                        WeatherForecastGrid.forecast_grid_id == m.forecast_grid_id,
                        WeatherForecastGrid.active_yn.is_(True),
                    )
                )
            ).scalar_one_or_none()
            if grid:
                forecast_ready = True
        if m.station_id:
            st = (
                await db.execute(
                    select(WeatherObservationStation).where(
                        WeatherObservationStation.station_id == m.station_id,
                        WeatherObservationStation.active_yn.is_(True),
                    )
                )
            ).scalar_one_or_none()
            if st:
                observation_ready = True
    if not location_ready:
        warnings.append("위치 정보(위도/경도)가 필요합니다.")
    if not forecast_ready:
        warnings.append("단기예보 격자(nx/ny) 매핑이 필요합니다.")
    if not observation_ready:
        warnings.append("ASOS 관측소 매핑이 필요합니다.")
    return {
        "entity_id": entity_id,
        "location_ready": location_ready,
        "forecast_ready": forecast_ready,
        "observation_ready": observation_ready,
        "prediction_input_ready": forecast_ready and location_ready,
        "training_weather_ready": observation_ready,
        "warnings": warnings,
    }


async def weather_mapping_preview(db: AsyncSession, entity_id: str) -> dict[str, Any]:
    readiness = await compute_weather_readiness(db, entity_id)
    loc = await get_active_location(db, entity_id)
    suggestion = None
    warnings = list(readiness.get("warnings") or [])
    if loc and loc.latitude is not None and loc.longitude is not None:
        try:
            suggestion = latlon_to_kma_grid(float(loc.latitude), float(loc.longitude))
            warnings.append("계산 결과는 예보 격자 기준이며 실제 운영 전 검토가 필요합니다.")
        except ValueError as exc:
            warnings.append(str(exc))
    return {**readiness, "grid_suggestion": suggestion, "active_location": {
        "latitude": float(loc.latitude) if loc and loc.latitude is not None else None,
        "longitude": float(loc.longitude) if loc and loc.longitude is not None else None,
        "address": loc.address if loc else None,
    }}


def convert_latlon_to_grid(latitude: float, longitude: float) -> dict[str, Any]:
    validate_latlon(latitude, longitude)
    result = latlon_to_kma_grid(latitude, longitude)
    return {
        **result,
        "latitude": latitude,
        "longitude": longitude,
        "hint": "계산 결과는 예보 격자 기준이며 실제 운영 전 검토가 필요합니다.",
    }
