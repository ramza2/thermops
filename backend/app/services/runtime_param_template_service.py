"""Runtime params template 렌더링 (R10-S6)."""

from __future__ import annotations

import re
from datetime import datetime, timedelta
from typing import Any

from app.utils.masking import mask_params_dict

TOKEN_RE = re.compile(r"\{\{([^}]+)\}\}")
SECRET_KEYS = frozenset({"servicekey", "api_key", "apikey", "secret", "password", "token"})


def _format_token(fmt: str, dt: datetime) -> str:
    mapping = {
        "YYYYMMDD": dt.strftime("%Y%m%d"),
        "YYYY-MM-DD": dt.strftime("%Y-%m-%d"),
        "YYYY-MM-DDTHH:mm:ss": dt.strftime("%Y-%m-%dT%H:%M:%S"),
        "HHmm": dt.strftime("%H%M"),
        "HH:mm": dt.strftime("%H:%M"),
    }
    return mapping.get(fmt, dt.isoformat())


def _resolve_token(name: str, context: dict[str, Any]) -> str:
    now: datetime = context["now"]
    key = name.strip()
    lower = key.lower()
    if lower == "last_success_at":
        val = context.get("last_success_at")
        return val.isoformat() if isinstance(val, datetime) else (str(val) if val else "")
    if lower == "window_start":
        val = context.get("window_start")
        return val.isoformat() if isinstance(val, datetime) else (str(val) if val else "")
    if lower == "window_end":
        val = context.get("window_end")
        return val.isoformat() if isinstance(val, datetime) else (str(val) if val else "")
    if ":" in key:
        prefix, fmt = key.split(":", 1)
        prefix_l = prefix.strip().lower()
        if prefix_l == "today":
            return _format_token(fmt.strip(), now)
        if prefix_l == "yesterday":
            return _format_token(fmt.strip(), now - timedelta(days=1))
        if prefix_l == "now":
            return _format_token(fmt.strip(), now)
    return ""


def _render_string(value: str, context: dict[str, Any]) -> str:
    def repl(match: re.Match[str]) -> str:
        return _resolve_token(match.group(1), context)

    return TOKEN_RE.sub(repl, value)


def _render_value(value: Any, context: dict[str, Any]) -> Any:
    if isinstance(value, str):
        return _render_string(value, context)
    if isinstance(value, dict):
        return {k: _render_value(v, context) for k, v in value.items()}
    if isinstance(value, list):
        return [_render_value(v, context) for v in value]
    return value


def build_load_window(
    *,
    load_window_type: str,
    now: datetime,
    last_success_at: datetime | None,
    start_at: datetime | None,
    window_offset_minutes: int | None,
) -> tuple[datetime | None, datetime | None]:
    window_type = (load_window_type or "NONE").upper()
    if window_type == "NONE":
        return None, None
    if window_type == "LAST_SUCCESS_TO_NOW":
        ws = last_success_at or start_at or (now - timedelta(days=1))
        return ws, now
    if window_type == "FIXED_OFFSET":
        minutes = int(window_offset_minutes or 60)
        return now - timedelta(minutes=minutes), now
    return None, None


def resolve_runtime_params(
    template: dict[str, Any] | None,
    *,
    now: datetime,
    last_success_at: datetime | None = None,
    start_at: datetime | None = None,
    load_window_type: str = "NONE",
    window_offset_minutes: int | None = None,
    manual_params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if (load_window_type or "").upper() == "MANUAL_PARAMS" and manual_params:
        base = dict(manual_params)
    else:
        base = dict(template or {})

    window_start, window_end = build_load_window(
        load_window_type=load_window_type,
        now=now,
        last_success_at=last_success_at,
        start_at=start_at,
        window_offset_minutes=window_offset_minutes,
    )
    context = {
        "now": now,
        "last_success_at": last_success_at,
        "window_start": window_start,
        "window_end": window_end,
    }
    rendered = _render_value(base, context)
    if window_start and "start_at" not in rendered:
        rendered["start_at"] = window_start.isoformat()
    if window_end and "end_at" not in rendered:
        rendered["end_at"] = window_end.isoformat()
    return rendered


def mask_runtime_params(params: dict[str, Any] | None) -> dict[str, Any]:
    masked = mask_params_dict(params or {})
    for key in list(masked.keys()):
        if key.lower() in SECRET_KEYS:
            masked[key] = "****"
    return masked
