"""외부 코드 매핑 및 코드 변환(resolve) 서비스."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.time import utc_now
from app.services.notification_event_service import emit_notification_safe
from app.models.entities import (
    CommonCode,
    ExternalCodeMapping,
    PredictionEntity,
    StandardDatasetType,
    UnmappedExternalCode,
    WeatherForecastGrid,
    WeatherObservationStation,
)

TARGET_TYPES = frozenset({
    "PREDICTION_ENTITY",
    "FORECAST_GRID",
    "OBSERVATION_STATION",
    "STANDARD_DATASET",
    "COMMON_CODE",
    "CUSTOM",
})
MAPPING_STATUSES = frozenset({"ACTIVE", "INACTIVE", "PENDING_REVIEW", "ARCHIVED"})
MAPPING_METHODS = frozenset({"MANUAL", "IMPORTED", "AUTO_SUGGESTED", "API_DISCOVERED"})
REVIEW_STATUSES = frozenset({"NEW", "REVIEWING", "MAPPED", "IGNORED", "ARCHIVED"})


class ExternalCodeMappingError(Exception):
    def __init__(self, message: str, *, error_code: str = "EXTERNAL_CODE_MAPPING_ERROR"):
        super().__init__(message)
        self.error_code = error_code


def _new_id(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex[:8].upper()}"


def _mapping_dict(m: ExternalCodeMapping) -> dict[str, Any]:
    return {
        "mapping_id": m.mapping_id,
        "source_system": m.source_system,
        "source_operation_id": m.source_operation_id,
        "external_code_group": m.external_code_group,
        "external_code": m.external_code,
        "external_code_name": m.external_code_name,
        "external_code_description": m.external_code_description,
        "target_type": m.target_type,
        "target_id": m.target_id,
        "target_display_name": m.target_display_name,
        "mapping_status": m.mapping_status,
        "mapping_method": m.mapping_method,
        "confidence_score": float(m.confidence_score) if m.confidence_score is not None else None,
        "priority": m.priority,
        "valid_from": m.valid_from.isoformat() if m.valid_from else None,
        "valid_to": m.valid_to.isoformat() if m.valid_to else None,
        "active_yn": bool(m.active_yn),
        "archived_at": m.archived_at.isoformat() if m.archived_at else None,
        "archived_reason": m.archived_reason,
        "metadata_json": m.metadata_json,
        "created_at": m.created_at.isoformat() if m.created_at else None,
        "updated_at": m.updated_at.isoformat() if m.updated_at else None,
    }


def _unmapped_dict(u: UnmappedExternalCode) -> dict[str, Any]:
    return {
        "unmapped_id": u.unmapped_id,
        "source_system": u.source_system,
        "source_operation_id": u.source_operation_id,
        "external_code_group": u.external_code_group,
        "external_code": u.external_code,
        "external_code_name": u.external_code_name,
        "first_seen_at": u.first_seen_at.isoformat() if u.first_seen_at else None,
        "last_seen_at": u.last_seen_at.isoformat() if u.last_seen_at else None,
        "seen_count": u.seen_count,
        "sample_payload_json": u.sample_payload_json,
        "suggested_target_type": u.suggested_target_type,
        "suggested_target_id": u.suggested_target_id,
        "suggested_target_name": u.suggested_target_name,
        "review_status": u.review_status,
        "ignored_reason": u.ignored_reason,
        "resolved_mapping_id": u.resolved_mapping_id,
        "metadata_json": u.metadata_json,
        "created_at": u.created_at.isoformat() if u.created_at else None,
        "updated_at": u.updated_at.isoformat() if u.updated_at else None,
    }


def _parse_at_date(at_date: date | str | None) -> date | None:
    if at_date is None:
        return None
    if isinstance(at_date, date):
        return at_date
    return date.fromisoformat(str(at_date)[:10])


def _date_in_range(valid_from: date | None, valid_to: date | None, at: date) -> bool:
    if valid_from and at < valid_from:
        return False
    if valid_to and at > valid_to:
        return False
    return True


async def _validate_target(db: AsyncSession, target_type: str, target_id: str) -> str:
    tt = target_type.upper()
    if tt not in TARGET_TYPES:
        raise ExternalCodeMappingError("지원하지 않는 내부 연결 대상 유형입니다.")
    if tt == "CUSTOM":
        return target_id
    if tt == "PREDICTION_ENTITY":
        row = (
            await db.execute(select(PredictionEntity).where(PredictionEntity.entity_id == target_id))
        ).scalar_one_or_none()
        if not row:
            raise ExternalCodeMappingError("연결할 예측 대상을 찾을 수 없습니다.")
        return row.entity_name
    if tt == "FORECAST_GRID":
        row = (
            await db.execute(select(WeatherForecastGrid).where(WeatherForecastGrid.forecast_grid_id == target_id))
        ).scalar_one_or_none()
        if not row:
            raise ExternalCodeMappingError("연결할 단기예보 격자를 찾을 수 없습니다.")
        return row.grid_name or f"nx={row.nx}, ny={row.ny}"
    if tt == "OBSERVATION_STATION":
        row = (
            await db.execute(
                select(WeatherObservationStation).where(WeatherObservationStation.station_id == target_id)
            )
        ).scalar_one_or_none()
        if not row:
            raise ExternalCodeMappingError("연결할 ASOS 관측소를 찾을 수 없습니다.")
        return row.station_name
    if tt == "STANDARD_DATASET":
        row = (
            await db.execute(
                select(StandardDatasetType).where(StandardDatasetType.dataset_type_id == target_id)
            )
        ).scalar_one_or_none()
        if not row:
            raise ExternalCodeMappingError("연결할 표준 데이터셋을 찾을 수 없습니다.")
        return row.dataset_type_name
    if tt == "COMMON_CODE":
        if "|" not in target_id:
            raise ExternalCodeMappingError("공통코드 target_id는 code_group|code 형식이어야 합니다.")
        code_group, code = target_id.split("|", 1)
        row = (
            await db.execute(
                select(CommonCode).where(CommonCode.code_group == code_group, CommonCode.code == code)
            )
        ).scalar_one_or_none()
        if not row:
            raise ExternalCodeMappingError("연결할 공통코드를 찾을 수 없습니다.")
        return row.code_name
    return target_id


async def _check_active_duplicate(
    db: AsyncSession,
    *,
    source_system: str,
    external_code_group: str,
    external_code: str,
    target_type: str,
    exclude_mapping_id: str | None = None,
) -> None:
    q = select(ExternalCodeMapping).where(
        ExternalCodeMapping.source_system == source_system,
        ExternalCodeMapping.external_code_group == external_code_group,
        ExternalCodeMapping.external_code == external_code,
        ExternalCodeMapping.target_type == target_type,
        ExternalCodeMapping.active_yn.is_(True),
        ExternalCodeMapping.mapping_status == "ACTIVE",
        ExternalCodeMapping.archived_at.is_(None),
    )
    if exclude_mapping_id:
        q = q.where(ExternalCodeMapping.mapping_id != exclude_mapping_id)
    existing = (await db.execute(q)).scalar_one_or_none()
    if existing:
        raise ExternalCodeMappingError(
            "동일한 외부 코드에 대해 이미 활성 매핑이 있습니다. 우선순위를 조정하거나 기존 매핑을 비활성화하세요."
        )


async def list_mappings(
    db: AsyncSession,
    *,
    source_system: str | None = None,
    external_code_group: str | None = None,
    external_code: str | None = None,
    target_type: str | None = None,
    mapping_status: str | None = None,
    active_yn: bool | None = None,
    keyword: str | None = None,
) -> list[dict[str, Any]]:
    q = select(ExternalCodeMapping).order_by(
        ExternalCodeMapping.source_system,
        ExternalCodeMapping.external_code_group,
        ExternalCodeMapping.external_code,
        ExternalCodeMapping.priority,
    )
    if source_system:
        q = q.where(ExternalCodeMapping.source_system == source_system)
    if external_code_group:
        q = q.where(ExternalCodeMapping.external_code_group == external_code_group)
    if external_code:
        q = q.where(ExternalCodeMapping.external_code == external_code)
    if target_type:
        q = q.where(ExternalCodeMapping.target_type == target_type.upper())
    if mapping_status:
        q = q.where(ExternalCodeMapping.mapping_status == mapping_status.upper())
    if active_yn is not None:
        q = q.where(ExternalCodeMapping.active_yn.is_(active_yn))
    if keyword:
        like = f"%{keyword}%"
        q = q.where(
            or_(
                ExternalCodeMapping.external_code.ilike(like),
                ExternalCodeMapping.external_code_name.ilike(like),
                ExternalCodeMapping.target_display_name.ilike(like),
            )
        )
    rows = (await db.execute(q)).scalars().all()
    return [_mapping_dict(r) for r in rows]


async def get_mapping(db: AsyncSession, mapping_id: str) -> dict[str, Any]:
    row = (
        await db.execute(select(ExternalCodeMapping).where(ExternalCodeMapping.mapping_id == mapping_id))
    ).scalar_one_or_none()
    if not row:
        raise ExternalCodeMappingError("외부 코드 매핑을 찾을 수 없습니다.", error_code="MAPPING_NOT_FOUND")
    return _mapping_dict(row)


async def create_mapping(db: AsyncSession, payload: dict[str, Any]) -> dict[str, Any]:
    source_system = (payload.get("source_system") or "").strip()
    external_code_group = (payload.get("external_code_group") or "").strip()
    external_code = (payload.get("external_code") or "").strip()
    target_type = (payload.get("target_type") or "").strip().upper()
    target_id = (payload.get("target_id") or "").strip()
    if not source_system:
        raise ExternalCodeMappingError("외부 시스템은 필수입니다.")
    if not external_code_group:
        raise ExternalCodeMappingError("외부 코드 그룹은 필수입니다.")
    if not external_code:
        raise ExternalCodeMappingError("외부 코드는 필수입니다.")
    if not target_id:
        raise ExternalCodeMappingError("내부 대상 ID는 필수입니다.")
    mapping_status = (payload.get("mapping_status") or "ACTIVE").upper()
    if mapping_status not in MAPPING_STATUSES:
        raise ExternalCodeMappingError("지원하지 않는 매핑 상태입니다.")
    mapping_method = (payload.get("mapping_method") or "MANUAL").upper()
    if mapping_method not in MAPPING_METHODS:
        raise ExternalCodeMappingError("지원하지 않는 매핑 방식입니다.")
    valid_from = payload.get("valid_from")
    valid_to = payload.get("valid_to")
    vf = date.fromisoformat(valid_from) if valid_from else None
    vt = date.fromisoformat(valid_to) if valid_to else None
    if vf and vt and vf > vt:
        raise ExternalCodeMappingError("유효 시작일은 종료일보다 늦을 수 없습니다.")
    display = payload.get("target_display_name") or await _validate_target(db, target_type, target_id)
    active_yn = bool(payload.get("active_yn", True))
    if active_yn and mapping_status == "ACTIVE":
        await _check_active_duplicate(
            db,
            source_system=source_system,
            external_code_group=external_code_group,
            external_code=external_code,
            target_type=target_type,
        )
    now = utc_now()
    m = ExternalCodeMapping(
        mapping_id=_new_id("ECM"),
        source_system=source_system,
        source_operation_id=payload.get("source_operation_id"),
        external_code_group=external_code_group,
        external_code=external_code,
        external_code_name=payload.get("external_code_name"),
        external_code_description=payload.get("external_code_description"),
        target_type=target_type,
        target_id=target_id,
        target_display_name=display,
        mapping_status=mapping_status,
        mapping_method=mapping_method,
        confidence_score=payload.get("confidence_score"),
        priority=int(payload.get("priority") or 1),
        valid_from=vf,
        valid_to=vt,
        active_yn=active_yn,
        metadata_json=payload.get("metadata_json"),
        created_at=now,
        updated_at=now,
    )
    db.add(m)
    await db.flush()
    return _mapping_dict(m)


async def update_mapping(db: AsyncSession, mapping_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    row = (
        await db.execute(select(ExternalCodeMapping).where(ExternalCodeMapping.mapping_id == mapping_id))
    ).scalar_one_or_none()
    if not row:
        raise ExternalCodeMappingError("외부 코드 매핑을 찾을 수 없습니다.", error_code="MAPPING_NOT_FOUND")
    target_type = (payload.get("target_type") or row.target_type).upper()
    target_id = (payload.get("target_id") or row.target_id).strip()
    if "target_type" in payload or "target_id" in payload:
        display = payload.get("target_display_name") or await _validate_target(db, target_type, target_id)
        row.target_type = target_type
        row.target_id = target_id
        row.target_display_name = display
    for key in (
        "source_system",
        "source_operation_id",
        "external_code_group",
        "external_code",
        "external_code_name",
        "external_code_description",
        "mapping_status",
        "mapping_method",
        "confidence_score",
        "priority",
        "active_yn",
        "metadata_json",
    ):
        if key in payload and payload[key] is not None:
            val = payload[key]
            if key in ("mapping_status", "mapping_method") and isinstance(val, str):
                val = val.upper()
            setattr(row, key, val)
    if "valid_from" in payload:
        row.valid_from = date.fromisoformat(payload["valid_from"]) if payload["valid_from"] else None
    if "valid_to" in payload:
        row.valid_to = date.fromisoformat(payload["valid_to"]) if payload["valid_to"] else None
    if row.valid_from and row.valid_to and row.valid_from > row.valid_to:
        raise ExternalCodeMappingError("유효 시작일은 종료일보다 늦을 수 없습니다.")
    if row.active_yn and row.mapping_status == "ACTIVE" and not row.archived_at:
        await _check_active_duplicate(
            db,
            source_system=row.source_system,
            external_code_group=row.external_code_group,
            external_code=row.external_code,
            target_type=row.target_type,
            exclude_mapping_id=mapping_id,
        )
    row.updated_at = utc_now()
    await db.flush()
    return _mapping_dict(row)


async def archive_mapping(db: AsyncSession, mapping_id: str, reason: str | None = None) -> dict[str, Any]:
    row = (
        await db.execute(select(ExternalCodeMapping).where(ExternalCodeMapping.mapping_id == mapping_id))
    ).scalar_one_or_none()
    if not row:
        raise ExternalCodeMappingError("외부 코드 매핑을 찾을 수 없습니다.", error_code="MAPPING_NOT_FOUND")
    now = utc_now()
    row.mapping_status = "ARCHIVED"
    row.active_yn = False
    row.archived_at = now
    row.archived_reason = reason
    row.updated_at = now
    await db.flush()
    return _mapping_dict(row)


async def activate_mapping(db: AsyncSession, mapping_id: str) -> dict[str, Any]:
    row = (
        await db.execute(select(ExternalCodeMapping).where(ExternalCodeMapping.mapping_id == mapping_id))
    ).scalar_one_or_none()
    if not row:
        raise ExternalCodeMappingError("외부 코드 매핑을 찾을 수 없습니다.", error_code="MAPPING_NOT_FOUND")
    await _check_active_duplicate(
        db,
        source_system=row.source_system,
        external_code_group=row.external_code_group,
        external_code=row.external_code,
        target_type=row.target_type,
        exclude_mapping_id=mapping_id,
    )
    row.active_yn = True
    row.mapping_status = "ACTIVE"
    row.archived_at = None
    row.archived_reason = None
    row.updated_at = utc_now()
    await db.flush()
    return _mapping_dict(row)


async def deactivate_mapping(db: AsyncSession, mapping_id: str) -> dict[str, Any]:
    row = (
        await db.execute(select(ExternalCodeMapping).where(ExternalCodeMapping.mapping_id == mapping_id))
    ).scalar_one_or_none()
    if not row:
        raise ExternalCodeMappingError("외부 코드 매핑을 찾을 수 없습니다.", error_code="MAPPING_NOT_FOUND")
    row.active_yn = False
    row.mapping_status = "INACTIVE"
    row.updated_at = utc_now()
    await db.flush()
    return _mapping_dict(row)


async def _find_resolvable_mappings(
    db: AsyncSession,
    *,
    source_system: str,
    external_code_group: str,
    external_code: str,
    target_type: str | None,
    at_date: date | None,
) -> list[ExternalCodeMapping]:
    q = select(ExternalCodeMapping).where(
        ExternalCodeMapping.source_system == source_system,
        ExternalCodeMapping.external_code_group == external_code_group,
        ExternalCodeMapping.external_code == external_code,
        ExternalCodeMapping.active_yn.is_(True),
        ExternalCodeMapping.mapping_status == "ACTIVE",
        ExternalCodeMapping.archived_at.is_(None),
    )
    if target_type:
        q = q.where(ExternalCodeMapping.target_type == target_type.upper())
    rows = (await db.execute(q.order_by(ExternalCodeMapping.priority.asc(), ExternalCodeMapping.created_at.desc()))).scalars().all()
    if not at_date:
        return list(rows)
    return [r for r in rows if _date_in_range(r.valid_from, r.valid_to, at_date)]


async def resolve_external_code(
    db: AsyncSession,
    *,
    source_system: str,
    external_code_group: str,
    external_code: str,
    target_type: str | None = None,
    at_date: date | str | None = None,
) -> dict[str, Any]:
    at = _parse_at_date(at_date) or utc_now().date()
    candidates = await _find_resolvable_mappings(
        db,
        source_system=source_system.strip(),
        external_code_group=external_code_group.strip(),
        external_code=external_code.strip(),
        target_type=target_type,
        at_date=at,
    )
    if not candidates:
        return {"resolved": False, "warnings": ["등록되지 않은 외부 코드입니다. 외부 코드 매핑 화면에서 내부 대상과 연결하세요."]}
    if len(candidates) > 1:
        warnings = [f"우선순위 {candidates[0].priority} 매핑을 선택했습니다. 후보 {len(candidates)}건."]
    else:
        warnings = []
    best = candidates[0]
    return {
        "resolved": True,
        "target_type": best.target_type,
        "target_id": best.target_id,
        "target_display_name": best.target_display_name,
        "mapping_id": best.mapping_id,
        "warnings": warnings,
    }


async def resolve_external_codes_batch(
    db: AsyncSession,
    items: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    results = []
    for item in items:
        result = await resolve_or_log_unmapped(
            db,
            source_system=item["source_system"],
            external_code_group=item["external_code_group"],
            external_code=item["external_code"],
            target_type=item.get("target_type"),
            at_date=item.get("at_date"),
        )
        results.append({**item, **result})
    return results


async def log_unmapped_external_code(
    db: AsyncSession,
    *,
    source_system: str,
    external_code_group: str,
    external_code: str,
    external_code_name: str | None = None,
    source_operation_id: str | None = None,
    sample_payload_json: dict | None = None,
    suggested_target_type: str | None = None,
    suggested_target_id: str | None = None,
    suggested_target_name: str | None = None,
) -> dict[str, Any]:
    now = utc_now()
    existing = (
        await db.execute(
            select(UnmappedExternalCode).where(
                UnmappedExternalCode.source_system == source_system,
                UnmappedExternalCode.external_code_group == external_code_group,
                UnmappedExternalCode.external_code == external_code,
            )
        )
    ).scalar_one_or_none()
    if existing:
        if existing.review_status in ("IGNORED", "ARCHIVED", "MAPPED"):
            return _unmapped_dict(existing)
        existing.last_seen_at = now
        existing.seen_count = (existing.seen_count or 0) + 1
        if external_code_name:
            existing.external_code_name = external_code_name
        if sample_payload_json:
            existing.sample_payload_json = sample_payload_json
        if source_operation_id:
            existing.source_operation_id = source_operation_id
        existing.updated_at = now
        await db.flush()
        result = _unmapped_dict(existing)
        await emit_notification_safe(
            db,
            event_source="SYSTEM",
            event_type="UNMAPPED_CODE_DETECTED",
            severity="WARNING",
            title=f"미매핑 코드 재발견: {source_system}/{external_code}",
            message=f"seen_count={existing.seen_count}",
            resource_type="unmapped_code",
            resource_id=existing.unmapped_id,
            dedup_key=f"{source_system}:{external_code_group}:{external_code}",
            event_payload_json={
                "source_system": source_system,
                "external_code_group": external_code_group,
                "external_code": external_code,
                "seen_count": existing.seen_count,
            },
        )
        return result
    row = UnmappedExternalCode(
        unmapped_id=_new_id("UEC"),
        source_system=source_system,
        source_operation_id=source_operation_id,
        external_code_group=external_code_group,
        external_code=external_code,
        external_code_name=external_code_name,
        first_seen_at=now,
        last_seen_at=now,
        seen_count=1,
        sample_payload_json=sample_payload_json,
        suggested_target_type=suggested_target_type,
        suggested_target_id=suggested_target_id,
        suggested_target_name=suggested_target_name,
        review_status="NEW",
        created_at=now,
        updated_at=now,
    )
    db.add(row)
    await db.flush()
    result = _unmapped_dict(row)
    await emit_notification_safe(
        db,
        event_source="SYSTEM",
        event_type="UNMAPPED_CODE_DETECTED",
        severity="WARNING",
        title=f"미매핑 코드 발생: {source_system}/{external_code}",
        message=external_code_name or external_code,
        resource_type="unmapped_code",
        resource_id=row.unmapped_id,
        dedup_key=f"{source_system}:{external_code_group}:{external_code}",
        event_payload_json={
            "source_system": source_system,
            "external_code_group": external_code_group,
            "external_code": external_code,
            "seen_count": 1,
        },
    )
    return result


async def resolve_or_log_unmapped(
    db: AsyncSession,
    *,
    source_system: str,
    external_code_group: str,
    external_code: str,
    target_type: str | None = None,
    at_date: date | str | None = None,
    external_code_name: str | None = None,
    source_operation_id: str | None = None,
    sample_payload_json: dict | None = None,
) -> dict[str, Any]:
    resolved = await resolve_external_code(
        db,
        source_system=source_system,
        external_code_group=external_code_group,
        external_code=external_code,
        target_type=target_type,
        at_date=at_date,
    )
    if resolved.get("resolved"):
        return resolved
    unmapped = await log_unmapped_external_code(
        db,
        source_system=source_system,
        external_code_group=external_code_group,
        external_code=external_code,
        external_code_name=external_code_name,
        source_operation_id=source_operation_id,
        sample_payload_json=sample_payload_json,
    )
    return {
        "resolved": False,
        "unmapped_id": unmapped["unmapped_id"],
        "warnings": resolved.get("warnings", []),
    }


async def list_unmapped(
    db: AsyncSession,
    *,
    source_system: str | None = None,
    external_code_group: str | None = None,
    review_status: str | None = None,
    keyword: str | None = None,
) -> list[dict[str, Any]]:
    q = select(UnmappedExternalCode).order_by(UnmappedExternalCode.last_seen_at.desc())
    if source_system:
        q = q.where(UnmappedExternalCode.source_system == source_system)
    if external_code_group:
        q = q.where(UnmappedExternalCode.external_code_group == external_code_group)
    if review_status:
        q = q.where(UnmappedExternalCode.review_status == review_status.upper())
    if keyword:
        like = f"%{keyword}%"
        q = q.where(
            or_(
                UnmappedExternalCode.external_code.ilike(like),
                UnmappedExternalCode.external_code_name.ilike(like),
            )
        )
    rows = (await db.execute(q)).scalars().all()
    return [_unmapped_dict(r) for r in rows]


async def get_unmapped(db: AsyncSession, unmapped_id: str) -> dict[str, Any]:
    row = (
        await db.execute(select(UnmappedExternalCode).where(UnmappedExternalCode.unmapped_id == unmapped_id))
    ).scalar_one_or_none()
    if not row:
        raise ExternalCodeMappingError("미매핑 코드를 찾을 수 없습니다.", error_code="UNMAPPED_NOT_FOUND")
    return _unmapped_dict(row)


async def assign_unmapped(db: AsyncSession, unmapped_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    row = (
        await db.execute(select(UnmappedExternalCode).where(UnmappedExternalCode.unmapped_id == unmapped_id))
    ).scalar_one_or_none()
    if not row:
        raise ExternalCodeMappingError("미매핑 코드를 찾을 수 없습니다.", error_code="UNMAPPED_NOT_FOUND")
    mapping_payload = {
        "source_system": row.source_system,
        "source_operation_id": row.source_operation_id,
        "external_code_group": row.external_code_group,
        "external_code": row.external_code,
        "external_code_name": row.external_code_name or payload.get("external_code_name"),
        "target_type": payload["target_type"],
        "target_id": payload["target_id"],
        "target_display_name": payload.get("target_display_name"),
        "mapping_method": payload.get("mapping_method", "MANUAL"),
        "mapping_status": "ACTIVE",
        "active_yn": True,
        "priority": payload.get("priority", 1),
        "valid_from": payload.get("valid_from"),
        "valid_to": payload.get("valid_to"),
        "metadata_json": payload.get("metadata_json"),
    }
    mapping = await create_mapping(db, mapping_payload)
    now = utc_now()
    row.review_status = "MAPPED"
    row.resolved_mapping_id = mapping["mapping_id"]
    row.updated_at = now
    await db.flush()
    return {"mapping": mapping, "unmapped": _unmapped_dict(row)}


async def ignore_unmapped(db: AsyncSession, unmapped_id: str, reason: str | None = None) -> dict[str, Any]:
    row = (
        await db.execute(select(UnmappedExternalCode).where(UnmappedExternalCode.unmapped_id == unmapped_id))
    ).scalar_one_or_none()
    if not row:
        raise ExternalCodeMappingError("미매핑 코드를 찾을 수 없습니다.", error_code="UNMAPPED_NOT_FOUND")
    row.review_status = "IGNORED"
    row.ignored_reason = reason
    row.updated_at = utc_now()
    await db.flush()
    return _unmapped_dict(row)


async def archive_unmapped(db: AsyncSession, unmapped_id: str) -> dict[str, Any]:
    row = (
        await db.execute(select(UnmappedExternalCode).where(UnmappedExternalCode.unmapped_id == unmapped_id))
    ).scalar_one_or_none()
    if not row:
        raise ExternalCodeMappingError("미매핑 코드를 찾을 수 없습니다.", error_code="UNMAPPED_NOT_FOUND")
    row.review_status = "ARCHIVED"
    row.updated_at = utc_now()
    await db.flush()
    return _unmapped_dict(row)


async def get_options(db: AsyncSession) -> dict[str, Any]:
    systems = (
        await db.execute(select(ExternalCodeMapping.source_system).distinct().order_by(ExternalCodeMapping.source_system))
    ).scalars().all()
    unmapped_systems = (
        await db.execute(select(UnmappedExternalCode.source_system).distinct())
    ).scalars().all()
    groups = (
        await db.execute(select(ExternalCodeMapping.external_code_group).distinct().order_by(ExternalCodeMapping.external_code_group))
    ).scalars().all()
    unmapped_groups = (
        await db.execute(select(UnmappedExternalCode.external_code_group).distinct())
    ).scalars().all()
    return {
        "source_systems": sorted(set(systems) | set(unmapped_systems)),
        "external_code_groups": sorted(set(groups) | set(unmapped_groups)),
        "target_types": sorted(TARGET_TYPES),
        "mapping_statuses": sorted(MAPPING_STATUSES),
        "review_statuses": sorted(REVIEW_STATUSES),
        "mapping_methods": sorted(MAPPING_METHODS),
    }


async def search_target_candidates(
    db: AsyncSession,
    *,
    target_type: str,
    keyword: str | None = None,
    limit: int = 30,
) -> list[dict[str, Any]]:
    tt = target_type.upper()
    if tt not in TARGET_TYPES:
        raise ExternalCodeMappingError("지원하지 않는 내부 연결 대상 유형입니다.")
    like = f"%{keyword}%" if keyword else None
    if tt == "PREDICTION_ENTITY":
        q = select(PredictionEntity).where(PredictionEntity.active_yn.is_(True)).order_by(PredictionEntity.entity_name)
        if like:
            q = q.where(or_(PredictionEntity.entity_code.ilike(like), PredictionEntity.entity_name.ilike(like)))
        rows = (await db.execute(q.limit(limit))).scalars().all()
        return [
            {"target_id": r.entity_id, "target_display_name": r.entity_name, "target_type": tt, "subtitle": r.entity_code}
            for r in rows
        ]
    if tt == "FORECAST_GRID":
        q = select(WeatherForecastGrid).where(WeatherForecastGrid.active_yn.is_(True))
        if like:
            q = q.where(or_(WeatherForecastGrid.grid_name.ilike(like), WeatherForecastGrid.forecast_grid_id.ilike(like)))
        rows = (await db.execute(q.limit(limit))).scalars().all()
        return [
            {
                "target_id": r.forecast_grid_id,
                "target_display_name": r.grid_name or f"nx={r.nx}, ny={r.ny}",
                "target_type": tt,
                "subtitle": f"nx={r.nx}, ny={r.ny}",
            }
            for r in rows
        ]
    if tt == "OBSERVATION_STATION":
        q = select(WeatherObservationStation).where(WeatherObservationStation.active_yn.is_(True))
        if like:
            q = q.where(
                or_(
                    WeatherObservationStation.station_code.ilike(like),
                    WeatherObservationStation.station_name.ilike(like),
                )
            )
        rows = (await db.execute(q.limit(limit))).scalars().all()
        return [
            {
                "target_id": r.station_id,
                "target_display_name": r.station_name,
                "target_type": tt,
                "subtitle": r.station_code,
            }
            for r in rows
        ]
    if tt == "STANDARD_DATASET":
        q = select(StandardDatasetType).where(StandardDatasetType.active_yn == "Y", StandardDatasetType.status == "ACTIVE")
        if like:
            q = q.where(
                or_(
                    StandardDatasetType.dataset_type_name.ilike(like),
                    StandardDatasetType.dataset_type_code.ilike(like),
                    StandardDatasetType.target_table.ilike(like),
                )
            )
        rows = (await db.execute(q.limit(limit))).scalars().all()
        return [
            {
                "target_id": r.dataset_type_id,
                "target_display_name": r.dataset_type_name,
                "target_type": tt,
                "subtitle": r.target_table,
            }
            for r in rows
        ]
    if tt == "COMMON_CODE":
        q = select(CommonCode).where(CommonCode.active_yn == "Y").order_by(CommonCode.code_group, CommonCode.sort_order)
        if like:
            q = q.where(or_(CommonCode.code.ilike(like), CommonCode.code_name.ilike(like), CommonCode.code_group.ilike(like)))
        rows = (await db.execute(q.limit(limit))).scalars().all()
        return [
            {
                "target_id": f"{r.code_group}|{r.code}",
                "target_display_name": r.code_name,
                "target_type": tt,
                "subtitle": r.code_group,
            }
            for r in rows
        ]
    return []


async def scan_items_for_code_mappings(
    db: AsyncSession,
    *,
    items: list[dict[str, Any]],
    code_mappings: list[dict[str, Any]],
    source_operation_id: str | None = None,
) -> dict[str, Any]:
    """API Connector metadata_json.code_mappings 기반 미매핑 코드 수집 (optional hook)."""
    unmapped_codes: list[dict[str, Any]] = []
    resolved_count = 0
    for cfg in code_mappings:
        field = cfg.get("field")
        source_system = cfg.get("source_system")
        external_code_group = cfg.get("external_code_group")
        target_type = cfg.get("target_type")
        if not field or not source_system or not external_code_group:
            continue
        seen: set[str] = set()
        for item in items:
            raw = item.get(field)
            if raw is None or raw == "":
                continue
            code = str(raw).strip()
            key = f"{source_system}:{external_code_group}:{code}"
            if key in seen:
                continue
            seen.add(key)
            name_field = cfg.get("name_field")
            ext_name = str(item.get(name_field)) if name_field and item.get(name_field) is not None else None
            result = await resolve_or_log_unmapped(
                db,
                source_system=source_system,
                external_code_group=external_code_group,
                external_code=code,
                target_type=target_type,
                external_code_name=ext_name,
                source_operation_id=source_operation_id,
                sample_payload_json=item if isinstance(item, dict) else None,
            )
            if result.get("resolved"):
                resolved_count += 1
            else:
                unmapped_codes.append(
                    {
                        "field": field,
                        "external_code": code,
                        "unmapped_id": result.get("unmapped_id"),
                    }
                )
    return {
        "code_mapping_scan": True,
        "resolved_count": resolved_count,
        "unmapped_count": len(unmapped_codes),
        "unmapped_codes": unmapped_codes[:50],
    }
