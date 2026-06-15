"""OAuth2 token endpoint + user management."""
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel

from security.auth import (
    hash_password, verify_password, create_access_token,
    create_refresh_token, decode_token,
)
from storage.redis_client import rate_limit_check

router = APIRouter()

# Max failed-or-total login attempts per minute, keyed by client IP + username.
_LOGIN_RATE_LIMIT = 10

# In production: load from PostgreSQL users table via SQLModel
_DEV_USERS = {
    "analyst@trustlayer.in":  {"password": hash_password("analyst123"),  "role": "analyst"},
    "admin@trustlayer.in":    {"password": hash_password("admin123"),    "role": "admin"},
    "auditor@trustlayer.in":  {"password": hash_password("auditor123"),  "role": "auditor"},
}


@router.post("/token")
async def login(request: Request, form: OAuth2PasswordRequestForm = Depends()):
    # Throttle brute-force attempts, keyed by client IP + attempted username.
    client_ip = request.client.host if request.client else "unknown"
    if not await rate_limit_check(f"login:{client_ip}:{form.username}", _LOGIN_RATE_LIMIT):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS,
                            "Too many login attempts — try again in a minute")
    user = _DEV_USERS.get(form.username)
    if not user or not verify_password(form.password, user["password"]):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid credentials",
                            headers={"WWW-Authenticate": "Bearer"})
    access = create_access_token(form.username, user["role"])
    refresh = create_refresh_token(form.username)
    return {
        "access_token": access,
        "refresh_token": refresh,
        "token_type": "bearer",
        "role": user["role"],
    }


class RefreshRequest(BaseModel):
    refresh_token: str


@router.post("/refresh")
async def refresh(req: RefreshRequest):
    payload = decode_token(req.refresh_token)
    if payload.get("type") != "refresh":
        raise HTTPException(400, "Not a refresh token")
    sub = payload["sub"]
    user = _DEV_USERS.get(sub)
    if not user:
        raise HTTPException(401, "User not found")
    access = create_access_token(sub, user["role"])
    return {"access_token": access, "token_type": "bearer"}
