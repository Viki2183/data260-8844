"""JWT authentication and role authorization for DATA260 HW7.

The legacy cookie/session implementation remains in ``auth_hw4.py`` for
historical homework compatibility.  HW7 routes use this module exclusively.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
from typing import Any, Callable

import bcrypt
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

try:
    from . import models
    from .database import get_db
except ImportError:  # pragma: no cover - supports direct uvicorn execution
    import models
    from database import get_db


JWT_SECRET = os.getenv("HW7_JWT_SECRET", "data260-hw7-local-secret")
JWT_TTL_SECONDS = int(os.getenv("HW7_JWT_TTL_SECONDS", "3600"))
ALLOWED_ROLES = {"reader", "writer", "moderator"}
bearer = HTTPBearer(auto_error=False)


class LoginPayload(BaseModel):
    username: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=1)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class IdentityResponse(BaseModel):
    username: str
    role: str


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _unb64(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def create_access_token(username: str, role: str, now: int | None = None) -> str:
    """Create a compact HMAC-SHA256 JWT without adding a runtime dependency."""
    if role not in ALLOWED_ROLES:
        raise ValueError("unsupported role")
    issued = int(time.time() if now is None else now)
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {
        "sub": username,
        "username": username,
        "role": role,
        "iat": issued,
        "exp": issued + JWT_TTL_SECONDS,
    }
    encoded_header = _b64(json.dumps(header, separators=(",", ":")).encode())
    encoded_payload = _b64(json.dumps(payload, separators=(",", ":")).encode())
    encoded = f"{encoded_header}.{encoded_payload}"
    signature = hmac.new(
        JWT_SECRET.encode("utf-8"), encoded.encode("ascii"), hashlib.sha256
    ).digest()
    return f"{encoded}.{_b64(signature)}"


def decode_access_token(token: str, now: int | None = None) -> dict[str, Any]:
    """Validate signature, shape, role, and expiration of one JWT."""
    try:
        encoded_header, encoded_payload, encoded_signature = token.split(".")
        signed = f"{encoded_header}.{encoded_payload}".encode("ascii")
        expected = hmac.new(
            JWT_SECRET.encode("utf-8"), signed, hashlib.sha256
        ).digest()
        if not hmac.compare_digest(expected, _unb64(encoded_signature)):
            raise ValueError("invalid signature")
        header = json.loads(_unb64(encoded_header))
        payload = json.loads(_unb64(encoded_payload))
        if header.get("alg") != "HS256" or header.get("typ") != "JWT":
            raise ValueError("invalid header")
        if not isinstance(payload.get("username"), str):
            raise ValueError("missing username")
        if payload.get("role") not in ALLOWED_ROLES:
            raise ValueError("invalid role")
        if int(payload.get("exp", 0)) <= int(time.time() if now is None else now):
            raise ValueError("expired token")
        return payload
    except (ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        return False


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
) -> models.UserDB:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Bearer token required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    claims = decode_access_token(credentials.credentials)
    user = (
        db.query(models.UserDB)
        .filter(models.UserDB.username == claims["username"])
        .first()
    )
    if user is None or user.role != claims["role"]:
        raise HTTPException(status_code=401, detail="User is not available")
    return user


def require_roles(*roles: str) -> Callable[..., models.UserDB]:
    allowed = set(roles)
    if not allowed or not allowed.issubset(ALLOWED_ROLES):
        raise ValueError("require_roles received an unsupported role")

    def dependency(user: models.UserDB = Depends(get_current_user)) -> models.UserDB:
        if user.role not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient role for this operation",
            )
        return user

    return dependency


router = APIRouter(prefix="/auth", tags=["HW7 JWT authentication"])


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginPayload, db: Session = Depends(get_db)) -> TokenResponse:
    user = (
        db.query(models.UserDB)
        .filter(models.UserDB.username == payload.username.strip())
        .first()
    )
    if user is None or user.role not in ALLOWED_ROLES or not verify_password(
        payload.password, user.password_hash
    ):
        raise HTTPException(status_code=401, detail="Invalid username or password")
    return TokenResponse(access_token=create_access_token(user.username, user.role))


@router.get("/me", response_model=IdentityResponse)
def me(user: models.UserDB = Depends(get_current_user)) -> IdentityResponse:
    return IdentityResponse(username=user.username, role=user.role)
