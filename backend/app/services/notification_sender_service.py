"""알림 발송 채널 — MOCK 확정, 기타는 설정 저장 + SKIPPED/NOT_IMPLEMENTED."""

from __future__ import annotations

import json
import logging
from typing import Any

import httpx

from app.models.entities import NotificationChannel, NotificationRecipient
from app.utils.masking import mask_params_dict, redact_text
from app.utils.secret_crypto import decrypt_secret

logger = logging.getLogger(__name__)

IMPLEMENTED_CHANNEL_TYPES = {"MOCK", "WEBHOOK"}
NOT_IMPLEMENTED_CHANNEL_TYPES = {"EMAIL", "SLACK_WEBHOOK", "SMS"}


class NotificationSendError(Exception):
    def __init__(self, message: str, *, error_code: str = "SEND_FAILED") -> None:
        super().__init__(message)
        self.error_code = error_code


def _channel_secret(channel: NotificationChannel) -> dict[str, Any]:
    if not channel.secret_config_encrypted:
        return {}
    try:
        raw = decrypt_secret(channel.secret_config_encrypted)
        return json.loads(raw) if raw.startswith("{") else {"value": raw}
    except Exception:
        return {}


async def send_notification(
    *,
    channel: NotificationChannel,
    recipient: NotificationRecipient | None,
    title: str,
    message: str | None,
    severity: str,
    metadata: dict[str, Any] | None = None,
    http_client: Any | None = None,
) -> dict[str, Any]:
    if not channel.enabled_yn:
        return {
            "delivery_status": "SKIPPED",
            "destination_masked": recipient.address_masked if recipient else None,
            "request_payload_masked": {"reason": "channel_disabled"},
            "response_payload_masked": None,
            "error_message": "채널이 비활성화되어 발송을 건너뜁니다.",
        }

    channel_type = (channel.channel_type or "").upper()
    safe_title = redact_text(title)
    safe_message = redact_text(message or "")
    base_request = mask_params_dict(
        {
            "title": safe_title,
            "message": safe_message,
            "severity": severity,
            "channel_type": channel_type,
            **(metadata or {}),
        }
    )

    if channel_type == "MOCK":
        return {
            "delivery_status": "SENT",
            "destination_masked": recipient.address_masked if recipient else "mock://local",
            "request_payload_masked": base_request,
            "response_payload_masked": {"mock": True, "accepted": True},
            "error_message": None,
        }

    if channel_type in NOT_IMPLEMENTED_CHANNEL_TYPES:
        return {
            "delivery_status": "SKIPPED",
            "destination_masked": recipient.address_masked if recipient else None,
            "request_payload_masked": base_request,
            "response_payload_masked": {"not_implemented": channel_type},
            "error_message": f"{channel_type} 채널은 아직 발송 구현 전입니다.",
        }

    if channel_type == "WEBHOOK":
        config = channel.config_json or {}
        secret = _channel_secret(channel)
        url = secret.get("webhook_url") or config.get("webhook_url")
        if not url:
            return {
                "delivery_status": "FAILED",
                "destination_masked": "****",
                "request_payload_masked": base_request,
                "response_payload_masked": None,
                "error_message": "webhook_url이 설정되지 않았습니다.",
            }
        payload = {
            "title": safe_title,
            "message": safe_message,
            "severity": severity,
            "metadata": mask_params_dict(metadata or {}),
        }
        masked_url = redact_text(str(url))
        try:
            client = http_client or httpx.AsyncClient(timeout=15.0)
            close_client = http_client is None
            resp = await client.post(url, json=payload)
            if close_client:
                await client.aclose()
            if resp.status_code >= 400:
                raise NotificationSendError(f"Webhook HTTP {resp.status_code}")
            body = resp.text[:500] if resp.text else ""
            return {
                "delivery_status": "SENT",
                "destination_masked": masked_url,
                "request_payload_masked": mask_params_dict(payload),
                "response_payload_masked": {"status_code": resp.status_code, "body": redact_text(body)},
                "error_message": None,
            }
        except Exception as exc:
            logger.warning("webhook send failed: %s", exc)
            return {
                "delivery_status": "FAILED",
                "destination_masked": masked_url,
                "request_payload_masked": mask_params_dict(payload),
                "response_payload_masked": None,
                "error_message": redact_text(str(exc))[:500],
            }

    return {
        "delivery_status": "SKIPPED",
        "destination_masked": recipient.address_masked if recipient else None,
        "request_payload_masked": base_request,
        "response_payload_masked": None,
        "error_message": f"지원하지 않는 채널 유형입니다: {channel_type}",
    }
