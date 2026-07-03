"""민감 정보 마스킹 — API Key/serviceKey 노출 방지."""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

_SECRET_KEY_NAMES = frozenset({
    "servicekey", "service_key", "api_key", "apikey", "authorization", "token", "secret", "password",
})
_MASK = "****"


def mask_secret_value(value: str | None, *, visible_edges: int = 4) -> str | None:
    if value is None or value == "":
        return None
    text = str(value)
    if len(text) <= visible_edges * 2:
        return _MASK
    return f"{text[:visible_edges]}{'*' * max(3, len(text) - visible_edges * 2)}{text[-visible_edges:]}"


def is_secret_param(name: str) -> bool:
    return (name or "").strip().lower().replace("-", "_") in _SECRET_KEY_NAMES


def mask_params_dict(params: dict[str, Any] | None) -> dict[str, Any]:
    if not params:
        return {}
    out: dict[str, Any] = {}
    for key, val in params.items():
        if is_secret_param(key) or (isinstance(val, str) and len(val) > 20 and "key" in key.lower()):
            out[key] = _MASK
        else:
            out[key] = val
    return out


def mask_url(url: str) -> str:
    if not url:
        return url
    try:
        parsed = urlparse(url)
        pairs = parse_qsl(parsed.query, keep_blank_values=True)
        masked_pairs = []
        for k, v in pairs:
            if is_secret_param(k):
                masked_pairs.append((k, _MASK))
            else:
                masked_pairs.append((k, v))
        new_query = urlencode(masked_pairs)
        return urlunparse(parsed._replace(query=new_query))
    except Exception:
        return re.sub(r"(serviceKey|api_key|apikey|token)=([^&]+)", r"\1=****", url, flags=re.IGNORECASE)


def redact_text(text: str) -> str:
    if not text:
        return text
    out = re.sub(
        r'(["\']?(?:serviceKey|api_key|apikey|authorization|token|secret)["\']?\s*[:=]\s*["\']?)([^"\'&\s,}]+)',
        r"\1****",
        text,
        flags=re.IGNORECASE,
    )
    return out
