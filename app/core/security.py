"""
Authentication and authorisation.

- Staff: bcrypt password hashes + HS256 JWT bearer tokens.
- Kiosks: shared device keys sent as `X-Kiosk-Key` (KIOSK_DEVICE_KEYS).
  With no keys configured and ENV=dev the kiosk check is disabled.
"""

from __future__ import annotations

import hmac
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
import jwt
from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_session
from app.core.models import User

logger = logging.getLogger("kiosk.security")

JWT_ALGORITHM = "HS256"

_bearer = HTTPBearer(auto_error=False)


# ── Passwords ─────────────────────────────────────────────────────────────────

def hash_password(password: str) -> str:
    # bcrypt only uses the first 72 bytes; truncate explicitly (bcrypt>=4.1 raises otherwise)
    return bcrypt.hashpw(password.encode("utf-8")[:72], bcrypt.gensalt()).decode("ascii")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8")[:72], password_hash.encode("ascii"))
    except (ValueError, TypeError):
        return False


# ── JWT ───────────────────────────────────────────────────────────────────────

def create_access_token(user: User) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user.id),
        "username": user.username,
        "role": user.role,
        "iat": now,
        "exp": now + timedelta(minutes=settings.JWT_EXPIRE_MINUTES),
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> Optional[dict]:
    try:
        return jwt.decode(token, settings.JWT_SECRET, algorithms=[JWT_ALGORITHM], options={"require": ["exp", "sub"]})
    except jwt.PyJWTError:
        return None


def user_from_token(session: Session, token: Optional[str]) -> Optional[User]:
    """Resolve an active user from a JWT, or None."""
    if not token:
        return None
    payload = decode_access_token(token)
    if not payload:
        return None
    try:
        user_id = int(payload["sub"])
    except (KeyError, ValueError):
        return None
    user = session.get(User, user_id)
    if user is None or not user.active:
        return None
    return user


# ── Dependencies ──────────────────────────────────────────────────────────────

def _unauthorized(detail: str = "Not authenticated") -> HTTPException:
    return HTTPException(status.HTTP_401_UNAUTHORIZED, detail=detail, headers={"WWW-Authenticate": "Bearer"})


def require_staff(
    creds: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
    session: Session = Depends(get_session),
) -> User:
    if creds is None or creds.scheme.lower() != "bearer":
        raise _unauthorized()
    user = user_from_token(session, creds.credentials)
    if user is None:
        raise _unauthorized("Invalid or expired token")
    if user.role not in ("nurse", "admin"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Staff role required")
    return user


def require_admin(user: User = Depends(require_staff)) -> User:
    if user.role != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Admin role required")
    return user


def kiosk_check_enabled() -> bool:
    return bool(settings.kiosk_keys) or settings.is_prod


def is_valid_kiosk_key(key: Optional[str]) -> bool:
    if not key:
        return False
    return any(hmac.compare_digest(key.encode(), k.encode()) for k in settings.kiosk_keys)


def require_kiosk(
    x_kiosk_key: Optional[str] = Header(None, alias="X-Kiosk-Key"),
    creds: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
    session: Session = Depends(get_session),
) -> None:
    """Kiosk endpoints: valid X-Kiosk-Key, or a valid staff bearer token.

    Disabled when ENV=dev and no KIOSK_DEVICE_KEYS are configured.
    """
    if not kiosk_check_enabled():
        return
    if is_valid_kiosk_key(x_kiosk_key):
        return
    if creds is not None and user_from_token(session, creds.credentials) is not None:
        return
    raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Invalid or missing X-Kiosk-Key")
