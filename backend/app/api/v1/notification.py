"""R10-S9 알림 / 장애 통보 API."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.response import ok
from app.schemas.api import (
    AlertRuleCreate,
    AlertRuleTestMatchRequest,
    AlertRuleUpdate,
    IncidentAcknowledgeRequest,
    IncidentResolveRequest,
    NotificationChannelCreate,
    NotificationChannelUpdate,
    NotificationEventTestRequest,
    NotificationRecipientCreate,
    NotificationRecipientUpdate,
)
from app.services.alert_rule_service import (
    AlertRuleError,
    create_alert_rule,
    create_channel,
    create_recipient,
    get_alert_rule,
    get_channel,
    get_recipient,
    list_alert_rules,
    list_channels,
    list_recipients,
    set_alert_rule_enabled,
    set_channel_enabled,
    set_recipient_enabled,
    update_alert_rule,
    update_channel,
    update_recipient,
)
from app.services.incident_service import (
    IncidentError,
    acknowledge_incident,
    close_incident,
    get_incident,
    list_incidents,
    resolve_incident,
)
from app.services.notification_delivery_service import DeliveryError, get_delivery, list_deliveries, retry_delivery
from app.services.notification_event_service import (
    NotificationEventError,
    get_event,
    get_notification_summary,
    list_events,
    record_notification_event,
    test_match_alert_rule,
)
from app.services.notification_sender_service import send_notification
from app.models.entities import NotificationChannel, NotificationRecipient
from sqlalchemy import select

router = APIRouter(tags=["notifications"])


@router.get("/notifications/summary")
async def get_notifications_summary(db: AsyncSession = Depends(get_db)):
    return ok(await get_notification_summary(db))


# Channels
@router.get("/notifications/channels")
async def get_notification_channels(db: AsyncSession = Depends(get_db)):
    return ok(await list_channels(db))


@router.post("/notifications/channels")
async def post_notification_channel(body: NotificationChannelCreate, db: AsyncSession = Depends(get_db)):
    try:
        item = await create_channel(db, body.model_dump())
    except AlertRuleError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ok(item, message="알림 채널이 등록되었습니다.")


@router.get("/notifications/channels/{channel_id}")
async def get_notification_channel(channel_id: str, db: AsyncSession = Depends(get_db)):
    try:
        item = await get_channel(db, channel_id)
    except AlertRuleError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ok(item)


@router.put("/notifications/channels/{channel_id}")
async def put_notification_channel(
    channel_id: str, body: NotificationChannelUpdate, db: AsyncSession = Depends(get_db)
):
    try:
        item = await update_channel(db, channel_id, body.model_dump(exclude_unset=True))
    except AlertRuleError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ok(item, message="알림 채널이 수정되었습니다.")


@router.post("/notifications/channels/{channel_id}/activate")
async def post_notification_channel_activate(channel_id: str, db: AsyncSession = Depends(get_db)):
    try:
        item = await set_channel_enabled(db, channel_id, True)
    except AlertRuleError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ok(item, message="알림 채널이 활성화되었습니다.")


@router.post("/notifications/channels/{channel_id}/deactivate")
async def post_notification_channel_deactivate(channel_id: str, db: AsyncSession = Depends(get_db)):
    try:
        item = await set_channel_enabled(db, channel_id, False)
    except AlertRuleError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ok(item, message="알림 채널이 비활성화되었습니다.")


@router.post("/notifications/channels/{channel_id}/test")
async def post_notification_channel_test(channel_id: str, db: AsyncSession = Depends(get_db)):
    channel = (
        await db.execute(select(NotificationChannel).where(NotificationChannel.channel_id == channel_id))
    ).scalar_one_or_none()
    if not channel:
        raise HTTPException(status_code=404, detail="알림 채널을 찾을 수 없습니다.")
    result = await send_notification(
        channel=channel,
        recipient=None,
        title="THERMOps 알림 채널 테스트",
        message="MOCK 채널 테스트 발송입니다.",
        severity="INFO",
    )
    return ok(result, message="채널 테스트가 완료되었습니다.")


# Recipients
@router.get("/notifications/recipients")
async def get_notification_recipients(db: AsyncSession = Depends(get_db)):
    return ok(await list_recipients(db))


@router.post("/notifications/recipients")
async def post_notification_recipient(body: NotificationRecipientCreate, db: AsyncSession = Depends(get_db)):
    try:
        item = await create_recipient(db, body.model_dump())
    except AlertRuleError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ok(item, message="수신 대상이 등록되었습니다.")


@router.get("/notifications/recipients/{recipient_id}")
async def get_notification_recipient(recipient_id: str, db: AsyncSession = Depends(get_db)):
    try:
        item = await get_recipient(db, recipient_id)
    except AlertRuleError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ok(item)


@router.put("/notifications/recipients/{recipient_id}")
async def put_notification_recipient(
    recipient_id: str, body: NotificationRecipientUpdate, db: AsyncSession = Depends(get_db)
):
    try:
        item = await update_recipient(db, recipient_id, body.model_dump(exclude_unset=True))
    except AlertRuleError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ok(item, message="수신 대상이 수정되었습니다.")


@router.post("/notifications/recipients/{recipient_id}/activate")
async def post_notification_recipient_activate(recipient_id: str, db: AsyncSession = Depends(get_db)):
    try:
        item = await set_recipient_enabled(db, recipient_id, True)
    except AlertRuleError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ok(item, message="수신 대상이 활성화되었습니다.")


@router.post("/notifications/recipients/{recipient_id}/deactivate")
async def post_notification_recipient_deactivate(recipient_id: str, db: AsyncSession = Depends(get_db)):
    try:
        item = await set_recipient_enabled(db, recipient_id, False)
    except AlertRuleError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ok(item, message="수신 대상이 비활성화되었습니다.")


# Alert rules
@router.get("/notifications/alert-rules")
async def get_alert_rules(
    event_source: str | None = None,
    event_type: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    return ok(await list_alert_rules(db, event_source=event_source, event_type=event_type))


@router.post("/notifications/alert-rules")
async def post_alert_rule(body: AlertRuleCreate, db: AsyncSession = Depends(get_db)):
    try:
        item = await create_alert_rule(db, body.model_dump())
    except AlertRuleError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ok(item, message="알림 규칙이 등록되었습니다.")


@router.get("/notifications/alert-rules/{rule_id}")
async def get_alert_rule_detail(rule_id: str, db: AsyncSession = Depends(get_db)):
    try:
        item = await get_alert_rule(db, rule_id)
    except AlertRuleError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ok(item)


@router.put("/notifications/alert-rules/{rule_id}")
async def put_alert_rule(rule_id: str, body: AlertRuleUpdate, db: AsyncSession = Depends(get_db)):
    try:
        item = await update_alert_rule(db, rule_id, body.model_dump(exclude_unset=True))
    except AlertRuleError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ok(item, message="알림 규칙이 수정되었습니다.")


@router.post("/notifications/alert-rules/{rule_id}/activate")
async def post_alert_rule_activate(rule_id: str, db: AsyncSession = Depends(get_db)):
    try:
        item = await set_alert_rule_enabled(db, rule_id, True)
    except AlertRuleError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ok(item, message="알림 규칙이 활성화되었습니다.")


@router.post("/notifications/alert-rules/{rule_id}/deactivate")
async def post_alert_rule_deactivate(rule_id: str, db: AsyncSession = Depends(get_db)):
    try:
        item = await set_alert_rule_enabled(db, rule_id, False)
    except AlertRuleError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ok(item, message="알림 규칙이 비활성화되었습니다.")


@router.post("/notifications/alert-rules/{rule_id}/test-match")
async def post_alert_rule_test_match(
    rule_id: str, body: AlertRuleTestMatchRequest, db: AsyncSession = Depends(get_db)
):
    try:
        item = await test_match_alert_rule(
            db, rule_id, severity=body.severity, event_payload_json=body.event_payload_json
        )
    except NotificationEventError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ok(item)


# Events
@router.get("/notifications/events")
async def get_notification_events(
    event_source: str | None = None,
    event_type: str | None = None,
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
):
    return ok(await list_events(db, event_source=event_source, event_type=event_type, limit=limit))


@router.get("/notifications/events/{event_id}")
async def get_notification_event(event_id: str, db: AsyncSession = Depends(get_db)):
    try:
        item = await get_event(db, event_id)
    except NotificationEventError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ok(item)


@router.post("/notifications/events/test")
async def post_notification_event_test(body: NotificationEventTestRequest, db: AsyncSession = Depends(get_db)):
    item = await record_notification_event(db, **body.model_dump())
    return ok(item, message="테스트 알림 이벤트가 기록되었습니다.")


# Incidents
@router.get("/notifications/incidents")
async def get_incidents(
    status: str | None = None,
    severity: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    return ok(await list_incidents(db, status=status, severity=severity))


@router.get("/notifications/incidents/{incident_id}")
async def get_incident_detail(incident_id: str, db: AsyncSession = Depends(get_db)):
    try:
        item = await get_incident(db, incident_id)
    except IncidentError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ok(item)


@router.post("/notifications/incidents/{incident_id}/acknowledge")
async def post_incident_acknowledge(
    incident_id: str, body: IncidentAcknowledgeRequest, db: AsyncSession = Depends(get_db)
):
    try:
        item = await acknowledge_incident(db, incident_id, acknowledged_by=body.acknowledged_by)
    except IncidentError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ok(item, message="장애 확인 처리가 완료되었습니다.")


@router.post("/notifications/incidents/{incident_id}/resolve")
async def post_incident_resolve(
    incident_id: str, body: IncidentResolveRequest, db: AsyncSession = Depends(get_db)
):
    try:
        item = await resolve_incident(
            db, incident_id, resolved_by=body.resolved_by, resolution_note=body.resolution_note
        )
    except IncidentError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ok(item, message="장애 해결 처리가 완료되었습니다.")


@router.post("/notifications/incidents/{incident_id}/close")
async def post_incident_close(incident_id: str, db: AsyncSession = Depends(get_db)):
    try:
        item = await close_incident(db, incident_id)
    except IncidentError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ok(item, message="장애가 종료되었습니다.")


# Deliveries
@router.get("/notifications/deliveries")
async def get_notification_deliveries(
    event_id: str | None = None,
    delivery_status: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    return ok(await list_deliveries(db, event_id=event_id, delivery_status=delivery_status))


@router.get("/notifications/deliveries/{delivery_id}")
async def get_notification_delivery(delivery_id: str, db: AsyncSession = Depends(get_db)):
    try:
        item = await get_delivery(db, delivery_id)
    except DeliveryError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ok(item)


@router.post("/notifications/deliveries/{delivery_id}/retry")
async def post_notification_delivery_retry(delivery_id: str, db: AsyncSession = Depends(get_db)):
    try:
        item = await retry_delivery(db, delivery_id)
    except DeliveryError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ok(item, message="발송 재시도가 완료되었습니다.")
