"""알림 규칙·채널·수신 대상 CRUD."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.time import utc_now
from app.models.entities import AlertRule, NotificationChannel, NotificationRecipient
from app.utils.secret_crypto import store_secret

SEVERITIES = ("INFO", "WARNING", "ERROR", "CRITICAL")
EVENT_SOURCES = (
    "API_CONNECTOR",
    "DATA_LOAD_SCHEDULE",
    "DATA_LOAD_SCHEDULE_RUN",
    "FORECAST_PROVIDER",
    "PREDICTION_JOB",
    "PIPELINE_RUN",
    "UPSERT_DEDUP",
    "SYSTEM",
)


class AlertRuleError(ValueError):
    def __init__(self, message: str, *, error_code: str = "ALERT_RULE_ERROR") -> None:
        super().__init__(message)
        self.error_code = error_code


def _new_id(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex[:8].upper()}"


def _str_list(value: Any) -> list[str]:
    if not value:
        return []
    if isinstance(value, list):
        return [str(x) for x in value if x]
    return []


def _channel_dict(row: NotificationChannel) -> dict[str, Any]:
    config = row.config_json or {}
    masked_config = {k: v for k, v in config.items() if k not in {"webhook_url", "smtp_password"}}
    return {
        "channel_id": row.channel_id,
        "channel_name": row.channel_name,
        "channel_type": row.channel_type,
        "enabled_yn": row.enabled_yn,
        "config_json": masked_config,
        "has_secret": bool(row.secret_config_encrypted),
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        "metadata_json": row.metadata_json,
    }


def _recipient_dict(row: NotificationRecipient) -> dict[str, Any]:
    return {
        "recipient_id": row.recipient_id,
        "recipient_name": row.recipient_name,
        "recipient_type": row.recipient_type,
        "address_masked": row.address_masked,
        "enabled_yn": row.enabled_yn,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        "metadata_json": row.metadata_json,
    }


def _rule_dict(row: AlertRule) -> dict[str, Any]:
    return {
        "alert_rule_id": row.alert_rule_id,
        "rule_name": row.rule_name,
        "rule_description": row.rule_description,
        "enabled_yn": row.enabled_yn,
        "event_source": row.event_source,
        "event_type": row.event_type,
        "min_severity": row.min_severity,
        "condition_json": row.condition_json,
        "dedup_window_minutes": row.dedup_window_minutes,
        "suppress_yn": row.suppress_yn,
        "create_incident_yn": row.create_incident_yn,
        "channel_ids_json": row.channel_ids_json or [],
        "recipient_ids_json": row.recipient_ids_json or [],
        "message_template": row.message_template,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        "metadata_json": row.metadata_json,
    }


async def list_channels(db: AsyncSession) -> list[dict[str, Any]]:
    rows = (await db.execute(select(NotificationChannel).order_by(NotificationChannel.created_at.desc()))).scalars().all()
    return [_channel_dict(r) for r in rows]


async def get_channel(db: AsyncSession, channel_id: str) -> dict[str, Any]:
    row = (
        await db.execute(select(NotificationChannel).where(NotificationChannel.channel_id == channel_id))
    ).scalar_one_or_none()
    if not row:
        raise AlertRuleError("알림 채널을 찾을 수 없습니다.", error_code="NOT_FOUND")
    return _channel_dict(row)


async def create_channel(db: AsyncSession, payload: dict[str, Any]) -> dict[str, Any]:
    now = utc_now()
    secret_plain = payload.pop("secret_value", None)
    enc = None
    if secret_plain:
        enc, _ = store_secret(str(secret_plain))
    row = NotificationChannel(
        channel_id=_new_id("NCH"),
        channel_name=payload["channel_name"],
        channel_type=str(payload.get("channel_type") or "MOCK").upper(),
        enabled_yn=bool(payload.get("enabled_yn", True)),
        config_json=payload.get("config_json"),
        secret_config_encrypted=enc,
        mask_policy_json=payload.get("mask_policy_json"),
        created_at=now,
        updated_at=now,
        metadata_json=payload.get("metadata_json"),
    )
    db.add(row)
    await db.flush()
    return _channel_dict(row)


async def update_channel(db: AsyncSession, channel_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    row = (
        await db.execute(select(NotificationChannel).where(NotificationChannel.channel_id == channel_id))
    ).scalar_one_or_none()
    if not row:
        raise AlertRuleError("알림 채널을 찾을 수 없습니다.", error_code="NOT_FOUND")
    secret_plain = payload.pop("secret_value", None)
    if secret_plain:
        enc, _ = store_secret(str(secret_plain))
        row.secret_config_encrypted = enc
    for key in ("channel_name", "channel_type", "enabled_yn", "config_json", "mask_policy_json", "metadata_json"):
        if key in payload and payload[key] is not None:
            setattr(row, key, payload[key])
    row.updated_at = utc_now()
    await db.flush()
    return _channel_dict(row)


async def set_channel_enabled(db: AsyncSession, channel_id: str, enabled: bool) -> dict[str, Any]:
    row = (
        await db.execute(select(NotificationChannel).where(NotificationChannel.channel_id == channel_id))
    ).scalar_one_or_none()
    if not row:
        raise AlertRuleError("알림 채널을 찾을 수 없습니다.", error_code="NOT_FOUND")
    row.enabled_yn = enabled
    row.updated_at = utc_now()
    await db.flush()
    return _channel_dict(row)


async def list_recipients(db: AsyncSession) -> list[dict[str, Any]]:
    rows = (await db.execute(select(NotificationRecipient).order_by(NotificationRecipient.created_at.desc()))).scalars().all()
    return [_recipient_dict(r) for r in rows]


async def get_recipient(db: AsyncSession, recipient_id: str) -> dict[str, Any]:
    row = (
        await db.execute(select(NotificationRecipient).where(NotificationRecipient.recipient_id == recipient_id))
    ).scalar_one_or_none()
    if not row:
        raise AlertRuleError("수신 대상을 찾을 수 없습니다.", error_code="NOT_FOUND")
    return _recipient_dict(row)


async def create_recipient(db: AsyncSession, payload: dict[str, Any]) -> dict[str, Any]:
    now = utc_now()
    address = payload.get("address")
    enc = None
    masked = None
    if address:
        enc, masked = store_secret(str(address))
    row = NotificationRecipient(
        recipient_id=_new_id("NRC"),
        recipient_name=payload["recipient_name"],
        recipient_type=str(payload.get("recipient_type") or "CUSTOM").upper(),
        address_masked=masked,
        address_encrypted=enc,
        enabled_yn=bool(payload.get("enabled_yn", True)),
        created_at=now,
        updated_at=now,
        metadata_json=payload.get("metadata_json"),
    )
    db.add(row)
    await db.flush()
    return _recipient_dict(row)


async def update_recipient(db: AsyncSession, recipient_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    row = (
        await db.execute(select(NotificationRecipient).where(NotificationRecipient.recipient_id == recipient_id))
    ).scalar_one_or_none()
    if not row:
        raise AlertRuleError("수신 대상을 찾을 수 없습니다.", error_code="NOT_FOUND")
    address = payload.pop("address", None)
    if address:
        enc, masked = store_secret(str(address))
        row.address_encrypted = enc
        row.address_masked = masked
    for key in ("recipient_name", "recipient_type", "enabled_yn", "metadata_json"):
        if key in payload and payload[key] is not None:
            setattr(row, key, payload[key])
    row.updated_at = utc_now()
    await db.flush()
    return _recipient_dict(row)


async def set_recipient_enabled(db: AsyncSession, recipient_id: str, enabled: bool) -> dict[str, Any]:
    row = (
        await db.execute(select(NotificationRecipient).where(NotificationRecipient.recipient_id == recipient_id))
    ).scalar_one_or_none()
    if not row:
        raise AlertRuleError("수신 대상을 찾을 수 없습니다.", error_code="NOT_FOUND")
    row.enabled_yn = enabled
    row.updated_at = utc_now()
    await db.flush()
    return _recipient_dict(row)


async def list_alert_rules(
    db: AsyncSession,
    *,
    event_source: str | None = None,
    event_type: str | None = None,
    enabled_only: bool = False,
) -> list[dict[str, Any]]:
    stmt = select(AlertRule).order_by(AlertRule.created_at.desc())
    if event_source:
        stmt = stmt.where(AlertRule.event_source == event_source)
    if event_type:
        stmt = stmt.where(AlertRule.event_type == event_type)
    if enabled_only:
        stmt = stmt.where(AlertRule.enabled_yn.is_(True))
    rows = (await db.execute(stmt)).scalars().all()
    return [_rule_dict(r) for r in rows]


async def get_alert_rule(db: AsyncSession, alert_rule_id: str) -> dict[str, Any]:
    row = (await db.execute(select(AlertRule).where(AlertRule.alert_rule_id == alert_rule_id))).scalar_one_or_none()
    if not row:
        raise AlertRuleError("알림 규칙을 찾을 수 없습니다.", error_code="NOT_FOUND")
    return _rule_dict(row)


async def create_alert_rule(db: AsyncSession, payload: dict[str, Any]) -> dict[str, Any]:
    now = utc_now()
    row = AlertRule(
        alert_rule_id=_new_id("ARU"),
        rule_name=payload["rule_name"],
        rule_description=payload.get("rule_description"),
        enabled_yn=bool(payload.get("enabled_yn", True)),
        event_source=str(payload["event_source"]).upper(),
        event_type=str(payload["event_type"]).upper(),
        min_severity=str(payload.get("min_severity") or "WARNING").upper(),
        condition_json=payload.get("condition_json"),
        dedup_window_minutes=int(payload.get("dedup_window_minutes") or 30),
        suppress_yn=bool(payload.get("suppress_yn", False)),
        create_incident_yn=bool(payload.get("create_incident_yn", True)),
        channel_ids_json=_str_list(payload.get("channel_ids_json")),
        recipient_ids_json=_str_list(payload.get("recipient_ids_json")),
        message_template=payload.get("message_template"),
        created_at=now,
        updated_at=now,
        metadata_json=payload.get("metadata_json"),
    )
    db.add(row)
    await db.flush()
    return _rule_dict(row)


async def update_alert_rule(db: AsyncSession, alert_rule_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    row = (await db.execute(select(AlertRule).where(AlertRule.alert_rule_id == alert_rule_id))).scalar_one_or_none()
    if not row:
        raise AlertRuleError("알림 규칙을 찾을 수 없습니다.", error_code="NOT_FOUND")
    for key in (
        "rule_name",
        "rule_description",
        "enabled_yn",
        "event_source",
        "event_type",
        "min_severity",
        "condition_json",
        "dedup_window_minutes",
        "suppress_yn",
        "create_incident_yn",
        "message_template",
        "metadata_json",
    ):
        if key in payload and payload[key] is not None:
            setattr(row, key, payload[key])
    if "channel_ids_json" in payload and payload["channel_ids_json"] is not None:
        row.channel_ids_json = _str_list(payload["channel_ids_json"])
    if "recipient_ids_json" in payload and payload["recipient_ids_json"] is not None:
        row.recipient_ids_json = _str_list(payload["recipient_ids_json"])
    row.updated_at = utc_now()
    await db.flush()
    return _rule_dict(row)


async def set_alert_rule_enabled(db: AsyncSession, alert_rule_id: str, enabled: bool) -> dict[str, Any]:
    row = (await db.execute(select(AlertRule).where(AlertRule.alert_rule_id == alert_rule_id))).scalar_one_or_none()
    if not row:
        raise AlertRuleError("알림 규칙을 찾을 수 없습니다.", error_code="NOT_FOUND")
    row.enabled_yn = enabled
    row.updated_at = utc_now()
    await db.flush()
    return _rule_dict(row)
