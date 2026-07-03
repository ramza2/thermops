"""간단 secret 저장 — 평문 DB 저장 방지 (KMS 미구현 환경용)."""

from __future__ import annotations

import base64
import hashlib
import os

from app.utils.masking import mask_secret_value

_DEFAULT_KEY = "thermops-dev-secret-key-change-in-production"


def _fernet_key() -> bytes:
    raw = os.environ.get("THERMOOPS_SECRET_ENCRYPTION_KEY", _DEFAULT_KEY).encode()
    return base64.urlsafe_b64encode(hashlib.sha256(raw).digest())


def encrypt_secret(plain: str) -> str:
    if not plain:
        return ""
    key = _fernet_key()
    data = plain.encode("utf-8")
    xored = bytes(b ^ key[i % len(key)] for i, b in enumerate(data))
    return base64.urlsafe_b64encode(xored).decode("ascii")


def decrypt_secret(encrypted: str) -> str:
    if not encrypted:
        return ""
    key = _fernet_key()
    data = base64.urlsafe_b64decode(encrypted.encode("ascii"))
    plain = bytes(b ^ key[i % len(key)] for i, b in enumerate(data))
    return plain.decode("utf-8")


def store_secret(plain: str) -> tuple[str, str]:
    enc = encrypt_secret(plain)
    masked = mask_secret_value(plain) or "****"
    return enc, masked
