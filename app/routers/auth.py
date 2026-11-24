"""
Staff authentication.

POST /auth/login — {"username","password"} → bearer JWT + user
GET  /auth/me    — current user
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_session
from app.core.models import User
from app.core.security import create_access_token, hash_password, require_staff, verify_password

logger = logging.getLogger("kiosk.auth")

router = APIRouter(prefix="/auth", tags=["Auth"])

# Used to equalise timing when the username does not exist.
_DUMMY_HASH = hash_password("dummy-password-for-timing")


class LoginRequest(BaseModel):
    username: str
    password: str


@router.post("/login")
def login(req: LoginRequest, session: Session = Depends(get_session)):
    user = session.scalars(select(User).where(User.username == req.username.strip())).first()
    if user is None:
        verify_password(req.password, _DUMMY_HASH)
        ok = False
    else:
        ok = verify_password(req.password, user.password_hash) and bool(user.active)
    if not ok:
        logger.info("[Auth] Failed login for username_len=%d", len(req.username))
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Invalid username or password")
    logger.info("[Auth] Login user_id=%s role=%s", user.id, user.role)
    return {"access_token": create_access_token(user), "token_type": "bearer", "user": user.to_public()}


@router.get("/me")
def me(user: User = Depends(require_staff)):
    return user.to_public()
