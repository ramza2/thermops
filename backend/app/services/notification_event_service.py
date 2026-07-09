"""알림 이벤트 기록·규칙 매칭·장애/발송 처리."""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.time import utc_now
from app.models.entities import (
    AlertRule,
    Incident,
    NotificationChannel,
    NotificationDelivery,
    NotificationEvent,
    NotificationRecipient,
)
from app.services.incident_service import upsert_incident_for_event
from app.services.notification_delivery_service import new_delivery_id
from app.services.notification_sender_service import send_notification
from app.utils.masking import mask_params_dict, redact_text

logger = logging.getLogger(__name__)

SEVERITY_RANK = {"INFO": 10, "WARNING": 20, "ERROR": 30, "CRITICAL": 40}


class NotificationEventError(ValueError):
    def __init__(self, message: str, *, error_code: str = "NOTIFICATION_EVENT_ERROR") -> None:
        super().__init__(message)
        self.error_code = error_code


def _new_id(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex[:8].upper()}"


def severity_meets_min(severity: str, min_severity: str) -> bool:
    return SEVERITY_RANK.get(severity.upper(), 0) >= SEVERITY_RANK.get(min_severity.upper(), 20)


def evaluate_condition(condition: dict[str, Any] | None, payload: dict[str, Any] | None) -> bool:
    if not condition:
        return True
    field = condition.get("field")
    operator = str(condition.get("operator") or "eq").lower()
    expected = condition.get("value")
    if not field:
        return True
    actual = (payload or {}).get(field)
    if operator == "eq":
        return actual == expected
    if operator == "gte":
        try:
            return float(actual) >= float(expected)
        except (TypeError, ValueError):
            return False
    if operator == "contains":
        return str(expected) in str(actual or "")
    return True


def _event_dict(row: NotificationEvent) -> dict[str, Any]:
    return {
        "event_id": row.event_id,
        "event_source": row.event_source,
        "event_type": row.event_type,
        "severity": row.severity,
        "title": row.title,
        "message": row.message,
        "resource_type": row.resource_type,
        "resource_id": row.resource_id,
        "correlation_id": row.correlation_id,
        "dedup_key": row.dedup_key,
        "masked_payload_json": row.masked_payload_json,
        "occurred_at": row.occurred_at.isoformat() if row.occurred_at else None,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "metadata_json": row.metadata_json,
    }


def _delivery_dict(row: NotificationDelivery) -> dict[str, Any]:
    return {
        "delivery_id": row.delivery_id,
        "event_id": row.event_id,
        "incident_id": row.incident_id,
        "alert_rule_id": row.alert_rule_id,
        "channel_id": row.channel_id,
        "recipient_id": row.recipient_id,
        "delivery_status": row.delivery_status,
        "severity": row.severity,
        "title": row.title,
        "message": row.message,
        "destination_masked": row.destination_masked,
        "error_message": row.error_message,
        "sent_at": row.sent_at.isoformat() if row.sent_at else None,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


def _mask_payload(payload: dict[str, Any] | None) -> dict[str, Any] | None:
    if not payload:
        return None
    return mask_params_dict(payload)


def _render_message(template: str | None, *, title: str, message: str | None, payload: dict[str, Any] | None) -> str:
    if not template:
        return redact_text(message or title)
    text = template.replace("{{title}}", title).replace("{{message}}", message or "")
    if payload:
        for key, value in payload.items():
            text = text.replace(f"{{{{{key}}}}}", str(value))
    return redact_text(text)


async def is_delivery_suppressed(
    db: AsyncSession,
    *,
    dedup_key: str | None,
    alert_rule_id: str,
    dedup_window_minutes: int,
) -> bool:
    if not dedup_key or dedup_window_minutes <= 0:
        return False
    since = utc_now() - timedelta(minutes=dedup_window_minutes)
    sent_count = (
        await db.execute(
            select(func.count())
            .select_from(NotificationDelivery)
            .where(
                NotificationDelivery.alert_rule_id == alert_rule_id,
                NotificationDelivery.delivery_status == "SENT",
                NotificationDelivery.created_at >= since,
                NotificationDelivery.event_id.in_(
                    select(NotificationEvent.event_id).where(NotificationEvent.dedup_key == dedup_key)
                ),
            )
        )
    ).scalar_one()
    return int(sent_count or 0) > 0


async def list_events(
    db: AsyncSession,
    *,
    event_source: str | None = None,
    event_type: str | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    stmt = select(NotificationEvent).order_by(NotificationEvent.occurred_at.desc()).limit(limit)
    if event_source:
        stmt = stmt.where(NotificationEvent.event_source == event_source)
    if event_type:
        stmt = stmt.where(NotificationEvent.event_type == event_type)
    rows = (await db.execute(stmt)).scalars().all()
    return [_event_dict(r) for r in rows]


async def get_event(db: AsyncSession, event_id: str) -> dict[str, Any]:
    row = (await db.execute(select(NotificationEvent).where(NotificationEvent.event_id == event_id))).scalar_one_or_none()
    if not row:
        raise NotificationEventError("알림 이벤트를 찾을 수 없습니다.", error_code="NOT_FOUND")
    return _event_dict(row)


async def get_notification_summary(db: AsyncSession) -> dict[str, Any]:
    open_incidents = (
        await db.execute(
            select(func.count()).select_from(Incident).where(Incident.status.in_(("OPEN", "ACKNOWLEDGED")))
        )
    ).scalar_one()
    by_severity = {}
    for sev in ("CRITICAL", "ERROR", "WARNING", "INFO"):
        count = (
            await db.execute(
                select(func.count())
                .select_from(Incident)
                .where(Incident.status.in_(("OPEN", "ACKNOWLEDGED")), Incident.severity == sev)
            )
        ).scalar_one()
        by_severity[sev] = int(count or 0)
    recent_events = (
        await db.execute(select(func.count()).select_from(NotificationEvent))
    ).scalar_one()
    failed_deliveries = (
        await db.execute(
            select(func.count()).select_from(NotificationDelivery).where(NotificationDelivery.delivery_status == "FAILED")
        )
    ).scalar_one()
    return {
        "open_incident_count": int(open_incidents or 0),
        "severity_counts": by_severity,
        "total_event_count": int(recent_events or 0),
        "failed_delivery_count": int(failed_deliveries or 0),
    }


async def record_notification_event(
    db: AsyncSession,
    *,
    event_source: str,
    event_type: str,
    severity: str,
    title: str,
    message: str | None = None,
    resource_type: str | None = None,
    resource_id: str | None = None,
    correlation_id: str | None = None,
    dedup_key: str | None = None,
    event_payload_json: dict[str, Any] | None = None,
    metadata_json: dict[str, Any] | None = None,
    occurred_at=None,
) -> dict[str, Any]:
    now = occurred_at or utc_now()
    safe_title = redact_text(title)[:300]
    safe_message = redact_text(message)[:2000] if message else None
    masked_payload = _mask_payload(event_payload_json)

    event_row = NotificationEvent(
        event_id=_new_id("NEV"),
        event_source=event_source.upper(),
        event_type=event_type.upper(),
        severity=severity.upper(),
        title=safe_title,
        message=safe_message,
        resource_type=resource_type,
        resource_id=resource_id,
        correlation_id=correlation_id,
        dedup_key=dedup_key,
        event_payload_json=event_payload_json,
        masked_payload_json=masked_payload,
        occurred_at=now,
        created_at=utc_now(),
        metadata_json=metadata_json,
    )
    db.add(event_row)
    await db.flush()

    matched_rules = (
        await db.execute(
            select(AlertRule).where(
                AlertRule.enabled_yn.is_(True),
                AlertRule.event_source == event_source.upper(),
                AlertRule.event_type == event_type.upper(),
            )
        )
    ).scalars().all()

    incidents: list[dict[str, Any]] = []
    deliveries: list[dict[str, Any]] = []

    for rule in matched_rules:
        if not severity_meets_min(severity, rule.min_severity or "WARNING"):
            continue
        if not evaluate_condition(rule.condition_json, event_payload_json):
            continue

        incident_dict: dict[str, Any] | None = None
        if rule.create_incident_yn:
            incident_dict = await upsert_incident_for_event(
                db,
                event_id=event_row.event_id,
                alert_rule_id=rule.alert_rule_id,
                severity=severity.upper(),
                title=safe_title,
                summary=safe_message,
                resource_type=resource_type,
                resource_id=resource_id,
                dedup_key=dedup_key,
                occurred_at=now,
            )
            incidents.append(incident_dict)

        suppressed = bool(rule.suppress_yn) or await is_delivery_suppressed(
            db,
            dedup_key=dedup_key,
            alert_rule_id=rule.alert_rule_id,
            dedup_window_minutes=int(rule.dedup_window_minutes or 30),
        )

        channel_ids = rule.channel_ids_json or []
        recipient_ids = rule.recipient_ids_json or []
        if not channel_ids:
            continue
        if not recipient_ids:
            recipient_ids = [None]

        body = _render_message(
            rule.message_template,
            title=safe_title,
            message=safe_message,
            payload=masked_payload or {},
        )

        for channel_id in channel_ids:
            channel = (
                await db.execute(select(NotificationChannel).where(NotificationChannel.channel_id == channel_id))
            ).scalar_one_or_none()
            if not channel:
                continue
            for recipient_id in recipient_ids:
                recipient = None
                if recipient_id:
                    recipient = (
                        await db.execute(
                            select(NotificationRecipient).where(NotificationRecipient.recipient_id == recipient_id)
                        )
                    ).scalar_one_or_none()
                    if recipient and not recipient.enabled_yn:
                        continue

                delivery_row = NotificationDelivery(
                    delivery_id=new_delivery_id(),
                    event_id=event_row.event_id,
                    incident_id=incident_dict["incident_id"] if incident_dict else None,
                    alert_rule_id=rule.alert_rule_id,
                    channel_id=channel.channel_id,
                    recipient_id=recipient.recipient_id if recipient else None,
                    delivery_status="PENDING",
                    severity=severity.upper(),
                    title=safe_title,
                    message=body,
                    created_at=utc_now(),
                )
                db.add(delivery_row)
                await db.flush()

                if suppressed:
                    delivery_row.delivery_status = "SUPPRESSED"
                    delivery_row.error_message = "중복 알림 억제 시간 내 동일 장애"
                    deliveries.append(_delivery_dict(delivery_row))
                    continue

                send_result = await send_notification(
                    channel=channel,
                    recipient=recipient,
                    title=safe_title,
                    message=body,
                    severity=severity.upper(),
                    metadata={
                        "event_id": event_row.event_id,
                        "resource_type": resource_type,
                        "resource_id": resource_id,
                    },
                )
                delivery_row.delivery_status = send_result["delivery_status"]
                delivery_row.destination_masked = send_result.get("destination_masked")
                delivery_row.request_payload_masked = send_result.get("request_payload_masked")
                delivery_row.response_payload_masked = send_result.get("response_payload_masked")
                delivery_row.error_message = send_result.get("error_message")
                if send_result["delivery_status"] == "SENT":
                    delivery_row.sent_at = utc_now()
                deliveries.append(_delivery_dict(delivery_row))

    await db.flush()
    return {
        "event": _event_dict(event_row),
        "matched_rule_count": len(matched_rules),
        "incidents": incidents,
        "deliveries": deliveries,
    }


async def emit_notification_safe(db: AsyncSession, **kwargs: Any) -> dict[str, Any] | None:
    try:
        return await record_notification_event(db, **kwargs)
    except Exception as exc:
        logger.warning("notification emit failed: %s", exc)
        return None


async def test_match_alert_rule(
    db: AsyncSession,
    alert_rule_id: str,
    *,
    severity: str,
    event_payload_json: dict[str, Any] | None = None,
) -> dict[str, Any]:
    rule = (await db.execute(select(AlertRule).where(AlertRule.alert_rule_id == alert_rule_id))).scalar_one_or_none()
    if not rule:
        raise NotificationEventError("알림 규칙을 찾을 수 없습니다.", error_code="NOT_FOUND")
    return {
        "alert_rule_id": alert_rule_id,
        "severity_ok": severity_meets_min(severity, rule.min_severity or "WARNING"),
        "condition_ok": evaluate_condition(rule.condition_json, event_payload_json),
        "enabled_yn": rule.enabled_yn,
    }
