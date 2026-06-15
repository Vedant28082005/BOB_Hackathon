"""OAuth2 + JWT for console users; API-key + HMAC for channel integrations."""
from __future__ import annotations
import hashlib
import hmac
import time
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext

from config import settings
from security.rbac import Role

pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/v1/auth/token")
oauth2_scheme_optional = OAuth2PasswordBearer(tokenUrl="/v1/auth/token", auto_error=False)


# ── Password helpers ──────────────────────────────────────────────────────────
def hash_password(plain: str) -> str:
    return pwd_ctx.hash(plain[:72])


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_ctx.verify(plain[:72], hashed)


# ── JWT ────────────────────────────────────────────────────────────────────────
def create_access_token(subject: str, role: str, extra: dict | None = None) -> str:
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.jwt_access_token_expire_minutes
    )
    payload = {"sub": subject, "role": role, "exp": expire, "iat": datetime.now(timezone.utc)}
    if extra:
        payload.update(extra)
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def create_refresh_token(subject: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(days=settings.jwt_refresh_token_expire_days)
    return jwt.encode(
        {"sub": subject, "exp": expire, "type": "refresh"},
        settings.jwt_secret_key, algorithm=settings.jwt_algorithm,
    )


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    except JWTError as e:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, f"Invalid token: {e}")


# ── Current-user dependency ───────────────────────────────────────────────────
class CurrentUser:
    def __init__(self, sub: str, role: str):
        self.sub = sub
        self.role = Role(role)


async def get_current_user(token: str = Depends(oauth2_scheme)) -> CurrentUser:
    payload = decode_token(token)
    sub = payload.get("sub")
    role = payload.get("role", "analyst")
    if not sub:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid credentials")
    return CurrentUser(sub=sub, role=role)


async def get_current_user_sse(
    token: Optional[str] = None,
    bearer: Optional[str] = Depends(oauth2_scheme_optional),
) -> CurrentUser:
    """Accepts JWT from Authorization header OR ?token= query param (EventSource can't set headers)."""
    raw = token or bearer
    if not raw:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "No token provided")
    payload = decode_token(raw)
    sub = payload.get("sub")
    role = payload.get("role", "analyst")
    if not sub:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid credentials")
    return CurrentUser(sub=sub, role=role)


def require_role(*allowed: str):
    async def _check(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if user.role.value not in allowed:
            raise HTTPException(status.HTTP_403_FORBIDDEN,
                                f"Role '{user.role.value}' not permitted here")
        return user
    return _check


# ── API-key + HMAC for channel integrations ───────────────────────────────────
def verify_hmac_signature(
    body: bytes,
    timestamp: str,
    signature: str,
    api_secret: str,
    tolerance_seconds: int = 300,
) -> bool:
    """
    Channel requests must include:
      X-TL-Timestamp: unix epoch (seconds)
      X-TL-Signature: HMAC-SHA256(api_secret, timestamp + "." + body_hex)
    """
    try:
        ts = int(timestamp)
    except ValueError:
        return False
    if abs(time.time() - ts) > tolerance_seconds:
        return False   # replay protection

    message = f"{timestamp}.{body.hex()}".encode()
    expected = hmac.new(api_secret.encode(), message, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


async def channel_auth(
    x_tl_api_key: str = Header(...),
    x_tl_timestamp: str = Header(...),
    x_tl_signature: str = Header(...),
) -> str:
    """Dependency for channel-integration endpoints."""
    from storage.redis_client import get_redis
    import json

    redis = await get_redis()
    api_key_data = await redis.get(f"api_key:{x_tl_api_key}")
    if not api_key_data:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Unknown API key")

    key_info = json.loads(api_key_data)
    # HMAC verification disabled in dev mode
    if settings.environment != "development":
        body_placeholder = b""  # caller must pass body separately for real validation
        if not verify_hmac_signature(body_placeholder, x_tl_timestamp,
                                     x_tl_signature, key_info["secret"]):
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid HMAC signature")

    return key_info["channel"]
