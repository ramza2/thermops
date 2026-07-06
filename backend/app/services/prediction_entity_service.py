"""예측 대상(Prediction Entity) 및 위치 정보 서비스."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from sqlalchemy import or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.time import utc_now
from app.models.entities import PredictionEntity, PredictionEntityLocation
from app.utils.kma_grid import validate_latlon

ENTITY_TYPES = frozenset({"SITE", "BRANCH", "FACILITY", "REGION", "ZONE", "CUSTOM"})
LOCATION_SOURCES = frozenset({"MANUAL", "GEOCODED", "IMPORTED"})


class PredictionEntityError(Exception):
    def __init__(self, message: str, *, error_code: str = "PREDICTION_ENTITY_ERROR"):
        super().__init__(message)
        self.error_code = error_code


def _new_id(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex[:8].upper()}"


def _entity_dict(e: PredictionEntity) -> dict[str, Any]:
    return {
        "entity_id": e.entity_id,
        "entity_code": e.entity_code,
        "entity_name": e.entity_name,
        "entity_type": e.entity_type,
        "business_domain": e.business_domain,
        "description": e.description,
        "active_yn": bool(e.active_yn),
        "archived_at": e.archived_at.isoformat() if e.archived_at else None,
        "metadata_json": e.metadata_json,
        "created_at": e.created_at.isoformat() if e.created_at else None,
        "updated_at": e.updated_at.isoformat() if e.updated_at else None,
    }


def _location_dict(loc: PredictionEntityLocation) -> dict[str, Any]:
    return {
        "location_id": loc.location_id,
        "entity_id": loc.entity_id,
        "address": loc.address,
        "latitude": float(loc.latitude) if loc.latitude is not None else None,
        "longitude": float(loc.longitude) if loc.longitude is not None else None,
        "location_source": loc.location_source,
        "valid_from": loc.valid_from.isoformat() if loc.valid_from else None,
        "valid_to": loc.valid_to.isoformat() if loc.valid_to else None,
        "active_yn": bool(loc.active_yn),
        "metadata_json": loc.metadata_json,
        "created_at": loc.created_at.isoformat() if loc.created_at else None,
        "updated_at": loc.updated_at.isoformat() if loc.updated_at else None,
    }


async def _get_entity(db: AsyncSession, entity_id: str) -> PredictionEntity:
    row = (
        await db.execute(select(PredictionEntity).where(PredictionEntity.entity_id == entity_id))
    ).scalar_one_or_none()
    if not row:
        raise PredictionEntityError("예측 대상을 찾을 수 없습니다.", error_code="ENTITY_NOT_FOUND")
    return row


async def list_entities(
    db: AsyncSession,
    *,
    entity_type: str | None = None,
    business_domain: str | None = None,
    active_yn: bool | None = True,
    keyword: str | None = None,
) -> list[dict[str, Any]]:
    q = select(PredictionEntity).order_by(PredictionEntity.entity_name)
    if active_yn is not None:
        q = q.where(PredictionEntity.active_yn.is_(active_yn))
    if entity_type:
        q = q.where(PredictionEntity.entity_type == entity_type)
    if business_domain:
        q = q.where(PredictionEntity.business_domain == business_domain)
    if keyword:
        like = f"%{keyword}%"
        q = q.where(
            or_(
                PredictionEntity.entity_code.ilike(like),
                PredictionEntity.entity_name.ilike(like),
            )
        )
    rows = (await db.execute(q)).scalars().all()
    return [_entity_dict(r) for r in rows]


async def get_entity_detail(db: AsyncSession, entity_id: str) -> dict[str, Any]:
    entity = await _get_entity(db, entity_id)
    locs = (
        await db.execute(
            select(PredictionEntityLocation)
            .where(PredictionEntityLocation.entity_id == entity_id)
            .order_by(PredictionEntityLocation.active_yn.desc(), PredictionEntityLocation.created_at.desc())
        )
    ).scalars().all()
    return {**_entity_dict(entity), "locations": [_location_dict(l) for l in locs]}


async def create_entity(db: AsyncSession, payload: dict[str, Any]) -> dict[str, Any]:
    code = (payload.get("entity_code") or "").strip()
    name = (payload.get("entity_name") or "").strip()
    etype = (payload.get("entity_type") or "SITE").strip().upper()
    if not code:
        raise PredictionEntityError("예측 대상 코드는 필수입니다.", error_code="MISSING_CODE")
    if not name:
        raise PredictionEntityError("예측 대상명은 필수입니다.", error_code="MISSING_NAME")
    if etype not in ENTITY_TYPES:
        raise PredictionEntityError(f"지원하지 않는 유형입니다: {etype}", error_code="INVALID_TYPE")
    existing = (
        await db.execute(select(PredictionEntity).where(PredictionEntity.entity_code == code))
    ).scalar_one_or_none()
    if existing:
        raise PredictionEntityError("이미 사용 중인 예측 대상 코드입니다.", error_code="DUPLICATE_CODE")
    now = utc_now()
    entity = PredictionEntity(
        entity_id=_new_id("PE"),
        entity_code=code,
        entity_name=name,
        entity_type=etype,
        business_domain=payload.get("business_domain"),
        description=payload.get("description"),
        active_yn=bool(payload.get("active_yn", True)),
        metadata_json=payload.get("metadata_json"),
        created_at=now,
        updated_at=now,
    )
    db.add(entity)
    await db.flush()
    return _entity_dict(entity)


async def update_entity(db: AsyncSession, entity_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    entity = await _get_entity(db, entity_id)
    if "entity_code" in payload and payload["entity_code"] != entity.entity_code:
        dup = (
            await db.execute(
                select(PredictionEntity).where(
                    PredictionEntity.entity_code == payload["entity_code"],
                    PredictionEntity.entity_id != entity_id,
                )
            )
        ).scalar_one_or_none()
        if dup:
            raise PredictionEntityError("이미 사용 중인 예측 대상 코드입니다.", error_code="DUPLICATE_CODE")
    for key in ("entity_code", "entity_name", "entity_type", "business_domain", "description", "active_yn", "metadata_json"):
        if key in payload and payload[key] is not None:
            if key == "entity_type" and payload[key] not in ENTITY_TYPES:
                raise PredictionEntityError(f"지원하지 않는 유형입니다: {payload[key]}", error_code="INVALID_TYPE")
            setattr(entity, key, payload[key])
    entity.updated_at = utc_now()
    await db.flush()
    return _entity_dict(entity)


async def archive_entity(db: AsyncSession, entity_id: str) -> dict[str, Any]:
    entity = await _get_entity(db, entity_id)
    now = utc_now()
    entity.active_yn = False
    entity.archived_at = now
    entity.updated_at = now
    await db.flush()
    return _entity_dict(entity)


async def list_locations(db: AsyncSession, entity_id: str) -> list[dict[str, Any]]:
    await _get_entity(db, entity_id)
    rows = (
        await db.execute(
            select(PredictionEntityLocation)
            .where(PredictionEntityLocation.entity_id == entity_id)
            .order_by(PredictionEntityLocation.active_yn.desc(), PredictionEntityLocation.created_at.desc())
        )
    ).scalars().all()
    return [_location_dict(l) for l in rows]


async def create_location(db: AsyncSession, entity_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    await _get_entity(db, entity_id)
    lat = payload.get("latitude")
    lon = payload.get("longitude")
    if lat is not None and lon is not None:
        try:
            validate_latlon(float(lat), float(lon))
        except ValueError as exc:
            raise PredictionEntityError(str(exc)) from exc
    src = (payload.get("location_source") or "MANUAL").upper()
    if src not in LOCATION_SOURCES:
        raise PredictionEntityError("지원하지 않는 위치 출처입니다.", error_code="INVALID_SOURCE")
    now = utc_now()
    loc = PredictionEntityLocation(
        location_id=_new_id("PEL"),
        entity_id=entity_id,
        address=payload.get("address"),
        latitude=lat,
        longitude=lon,
        location_source=src,
        valid_from=payload.get("valid_from"),
        valid_to=payload.get("valid_to"),
        active_yn=bool(payload.get("active_yn", True)),
        metadata_json=payload.get("metadata_json"),
        created_at=now,
        updated_at=now,
    )
    if loc.active_yn:
        await db.execute(
            update(PredictionEntityLocation)
            .where(PredictionEntityLocation.entity_id == entity_id, PredictionEntityLocation.active_yn.is_(True))
            .values(active_yn=False, updated_at=now)
        )
    db.add(loc)
    await db.flush()
    return _location_dict(loc)


async def update_location(
    db: AsyncSession, entity_id: str, location_id: str, payload: dict[str, Any]
) -> dict[str, Any]:
    await _get_entity(db, entity_id)
    loc = (
        await db.execute(
            select(PredictionEntityLocation).where(
                PredictionEntityLocation.location_id == location_id,
                PredictionEntityLocation.entity_id == entity_id,
            )
        )
    ).scalar_one_or_none()
    if not loc:
        raise PredictionEntityError("위치 정보를 찾을 수 없습니다.", error_code="LOCATION_NOT_FOUND")
    lat = payload.get("latitude", loc.latitude)
    lon = payload.get("longitude", loc.longitude)
    if lat is not None and lon is not None:
        try:
            validate_latlon(float(lat), float(lon))
        except ValueError as exc:
            raise PredictionEntityError(str(exc)) from exc
    for key in ("address", "latitude", "longitude", "location_source", "valid_from", "valid_to", "active_yn", "metadata_json"):
        if key in payload:
            setattr(loc, key, payload[key])
    loc.updated_at = utc_now()
    await db.flush()
    return _location_dict(loc)


async def activate_location(db: AsyncSession, entity_id: str, location_id: str) -> dict[str, Any]:
    await _get_entity(db, entity_id)
    now = utc_now()
    await db.execute(
        update(PredictionEntityLocation)
        .where(PredictionEntityLocation.entity_id == entity_id)
        .values(active_yn=False, updated_at=now)
    )
    loc = (
        await db.execute(
            select(PredictionEntityLocation).where(
                PredictionEntityLocation.location_id == location_id,
                PredictionEntityLocation.entity_id == entity_id,
            )
        )
    ).scalar_one_or_none()
    if not loc:
        raise PredictionEntityError("위치 정보를 찾을 수 없습니다.", error_code="LOCATION_NOT_FOUND")
    loc.active_yn = True
    loc.updated_at = now
    await db.flush()
    return _location_dict(loc)


async def get_active_location(db: AsyncSession, entity_id: str) -> PredictionEntityLocation | None:
    return (
        await db.execute(
            select(PredictionEntityLocation).where(
                PredictionEntityLocation.entity_id == entity_id,
                PredictionEntityLocation.active_yn.is_(True),
            )
        )
    ).scalar_one_or_none()
