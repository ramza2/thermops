"""장애(Incident) 조회·확인·해결."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.time import utc_now
from app.models.entities import Incident


class IncidentError(ValueError):
    def __init__(self, message: str, *, error_code: str = "INCIDENT_ERROR") -> None:
        super().__init__(message)
        self.error_code = error_code


def _incident_dict(row: Incident) -> dict[str, Any]:
    return {
        "incident_id": row.incident_id,
        "event_id": row.event_id,
        "alert_rule_id": row.alert_rule_id,
        "severity": row.severity,
        "status": row.status,
        "title": row.title,
        "summary": row.summary,
        "resource_type": row.resource_type,
        "resource_id": row.resource_id,
        "dedup_key": row.dedup_key,
        "first_occurred_at": row.first_occurred_at.isoformat() if row.first_occurred_at else None,
        "last_occurred_at": row.last_occurred_at.isoformat() if row.last_occurred_at else None,
        "occurrence_count": row.occurrence_count,
        "acknowledged_at": row.acknowledged_at.isoformat() if row.acknowledged_at else None,
        "acknowledged_by": row.acknowledged_by,
        "resolved_at": row.resolved_at.isoformat() if row.resolved_at else None,
        "resolved_by": row.resolved_by,
        "resolution_note": row.resolution_note,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        "metadata_json": row.metadata_json,
    }


async def list_incidents(
    db: AsyncSession,
    *,
    status: str | None = None,
    severity: str | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    stmt = select(Incident).order_by(Incident.last_occurred_at.desc()).limit(limit)
    if status:
        stmt = stmt.where(Incident.status == status.upper())
    if severity:
        stmt = stmt.where(Incident.severity == severity.upper())
    rows = (await db.execute(stmt)).scalars().all()
    return [_incident_dict(r) for r in rows]


async def get_incident(db: AsyncSession, incident_id: str) -> dict[str, Any]:
    row = (await db.execute(select(Incident).where(Incident.incident_id == incident_id))).scalar_one_or_none()
    if not row:
        raise IncidentError("장애를 찾을 수 없습니다.", error_code="NOT_FOUND")
    return _incident_dict(row)


async def find_open_incident(
    db: AsyncSession,
    *,
    dedup_key: str | None,
    alert_rule_id: str | None,
) -> Incident | None:
    if not dedup_key:
        return None
    stmt = select(Incident).where(
        Incident.dedup_key == dedup_key,
        Incident.status.in_(("OPEN", "ACKNOWLEDGED")),
    )
    if alert_rule_id:
        stmt = stmt.where(Incident.alert_rule_id == alert_rule_id)
    stmt = stmt.order_by(Incident.last_occurred_at.desc()).limit(1)
    return (await db.execute(stmt)).scalar_one_or_none()


async def upsert_incident_for_event(
    db: AsyncSession,
    *,
    event_id: str,
    alert_rule_id: str | None,
    severity: str,
    title: str,
    summary: str | None,
    resource_type: str | None,
    resource_id: str | None,
    dedup_key: str | None,
    occurred_at,
) -> dict[str, Any]:
    existing = await find_open_incident(db, dedup_key=dedup_key, alert_rule_id=alert_rule_id)
    now = utc_now()
    if existing:
        existing.event_id = event_id
        existing.last_occurred_at = occurred_at
        existing.occurrence_count = int(existing.occurrence_count or 0) + 1
        existing.summary = summary
        existing.updated_at = now
        await db.flush()
        return _incident_dict(existing)

    from uuid import uuid4

    row = Incident(
        incident_id=f"INC-{uuid4().hex[:8].upper()}",
        event_id=event_id,
        alert_rule_id=alert_rule_id,
        severity=severity,
        status="OPEN",
        title=title,
        summary=summary,
        resource_type=resource_type,
        resource_id=resource_id,
        dedup_key=dedup_key,
        first_occurred_at=occurred_at,
        last_occurred_at=occurred_at,
        occurrence_count=1,
        created_at=now,
        updated_at=now,
    )
    db.add(row)
    await db.flush()
    return _incident_dict(row)


async def acknowledge_incident(
    db: AsyncSession,
    incident_id: str,
    *,
    acknowledged_by: str | None = None,
) -> dict[str, Any]:
    row = (await db.execute(select(Incident).where(Incident.incident_id == incident_id))).scalar_one_or_none()
    if not row:
        raise IncidentError("장애를 찾을 수 없습니다.", error_code="NOT_FOUND")
    if row.status == "RESOLVED":
        raise IncidentError("이미 해결된 장애입니다.", error_code="ALREADY_RESOLVED")
    row.status = "ACKNOWLEDGED"
    row.acknowledged_at = utc_now()
    row.acknowledged_by = acknowledged_by or "operator"
    row.updated_at = utc_now()
    await db.flush()
    return _incident_dict(row)


async def resolve_incident(
    db: AsyncSession,
    incident_id: str,
    *,
    resolved_by: str | None = None,
    resolution_note: str | None = None,
) -> dict[str, Any]:
    row = (await db.execute(select(Incident).where(Incident.incident_id == incident_id))).scalar_one_or_none()
    if not row:
        raise IncidentError("장애를 찾을 수 없습니다.", error_code="NOT_FOUND")
    row.status = "RESOLVED"
    row.resolved_at = utc_now()
    row.resolved_by = resolved_by or "operator"
    row.resolution_note = resolution_note
    row.updated_at = utc_now()
    await db.flush()
    return _incident_dict(row)


async def close_incident(db: AsyncSession, incident_id: str) -> dict[str, Any]:
    row = (await db.execute(select(Incident).where(Incident.incident_id == incident_id))).scalar_one_or_none()
    if not row:
        raise IncidentError("장애를 찾을 수 없습니다.", error_code="NOT_FOUND")
    row.status = "CLOSED"
    row.updated_at = utc_now()
    await db.flush()
    return _incident_dict(row)
