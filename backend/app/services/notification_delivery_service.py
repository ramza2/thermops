"""알림 발송 이력 조회·재시도."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.time import utc_now
from app.models.entities import NotificationChannel, NotificationDelivery, NotificationRecipient
from app.services.notification_sender_service import send_notification


class DeliveryError(ValueError):
    def __init__(self, message: str, *, error_code: str = "DELIVERY_ERROR") -> None:
        super().__init__(message)
        self.error_code = error_code


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
        "request_payload_masked": row.request_payload_masked,
        "response_payload_masked": row.response_payload_masked,
        "error_message": row.error_message,
        "sent_at": row.sent_at.isoformat() if row.sent_at else None,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "metadata_json": row.metadata_json,
    }


async def list_deliveries(
    db: AsyncSession,
    *,
    event_id: str | None = None,
    delivery_status: str | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    stmt = select(NotificationDelivery).order_by(NotificationDelivery.created_at.desc()).limit(limit)
    if event_id:
        stmt = stmt.where(NotificationDelivery.event_id == event_id)
    if delivery_status:
        stmt = stmt.where(NotificationDelivery.delivery_status == delivery_status.upper())
    rows = (await db.execute(stmt)).scalars().all()
    return [_delivery_dict(r) for r in rows]


async def get_delivery(db: AsyncSession, delivery_id: str) -> dict[str, Any]:
    row = (
        await db.execute(select(NotificationDelivery).where(NotificationDelivery.delivery_id == delivery_id))
    ).scalar_one_or_none()
    if not row:
        raise DeliveryError("발송 이력을 찾을 수 없습니다.", error_code="NOT_FOUND")
    return _delivery_dict(row)


async def retry_delivery(db: AsyncSession, delivery_id: str) -> dict[str, Any]:
    row = (
        await db.execute(select(NotificationDelivery).where(NotificationDelivery.delivery_id == delivery_id))
    ).scalar_one_or_none()
    if not row:
        raise DeliveryError("발송 이력을 찾을 수 없습니다.", error_code="NOT_FOUND")
    if not row.channel_id:
        raise DeliveryError("채널 정보가 없어 재시도할 수 없습니다.", error_code="NO_CHANNEL")

    channel = (
        await db.execute(select(NotificationChannel).where(NotificationChannel.channel_id == row.channel_id))
    ).scalar_one_or_none()
    if not channel:
        raise DeliveryError("알림 채널을 찾을 수 없습니다.", error_code="CHANNEL_NOT_FOUND")

    recipient = None
    if row.recipient_id:
        recipient = (
            await db.execute(select(NotificationRecipient).where(NotificationRecipient.recipient_id == row.recipient_id))
        ).scalar_one_or_none()

    result = await send_notification(
        channel=channel,
        recipient=recipient,
        title=row.title,
        message=row.message,
        severity=row.severity,
        metadata={"retry_of": delivery_id},
    )
    row.delivery_status = result["delivery_status"]
    row.destination_masked = result.get("destination_masked")
    row.request_payload_masked = result.get("request_payload_masked")
    row.response_payload_masked = result.get("response_payload_masked")
    row.error_message = result.get("error_message")
    if result["delivery_status"] == "SENT":
        row.sent_at = utc_now()
    await db.flush()
    return _delivery_dict(row)


def new_delivery_id() -> str:
    return f"NDL-{uuid4().hex[:8].upper()}"
