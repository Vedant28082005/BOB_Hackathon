"""AES-256-GCM encryption for PII fields stored in PostgreSQL."""
from __future__ import annotations
import base64
import os
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from config import settings


def _key() -> bytes:
    return bytes.fromhex(settings.aes_encryption_key)


def encrypt(plaintext: str) -> str:
    """Returns base64(nonce + ciphertext) for DB storage."""
    nonce = os.urandom(12)
    aesgcm = AESGCM(_key())
    ct = aesgcm.encrypt(nonce, plaintext.encode(), None)
    return base64.b64encode(nonce + ct).decode()


def decrypt(token: str) -> str:
    raw = base64.b64decode(token)
    nonce, ct = raw[:12], raw[12:]
    aesgcm = AESGCM(_key())
    return aesgcm.decrypt(nonce, ct, None).decode()


def encrypt_optional(value: str | None) -> str | None:
    return encrypt(value) if value else None


def decrypt_optional(token: str | None) -> str | None:
    return decrypt(token) if token else None
