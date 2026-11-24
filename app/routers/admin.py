"""
Admin — staff user management (admin role only).

GET   /admin/users        → {"users": [...]}
POST  /admin/users        {username, password, full_name, role}
PATCH /admin/users/{id}   {active?, password?, full_name?, role?}
"""

import logging
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_session
from app.core.models import User
from app.core.security import hash_password, require_admin

logger = logging.getLogger("kiosk.admin")

router = APIRouter(prefix="/admin", tags=["Admin"])


class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=64, pattern=r"^[A-Za-z0-9_.-]+$")
    password: str = Field(..., min_length=8, max_length=128)
    full_name: str = Field(..., min_length=1, max_length=200)
    role: Literal["nurse", "admin"]


class UserUpdate(BaseModel):
    active: Optional[bool] = None
    password: Optional[str] = Field(None, min_length=8, max_length=128)
    full_name: Optional[str] = Field(None, min_length=1, max_length=200)
    role: Optional[Literal["nurse", "admin"]] = None


@router.get("/users")
def list_users(_: User = Depends(require_admin), session: Session = Depends(get_session)):
    users = session.scalars(select(User).order_by(User.id)).all()
    return {"users": [u.to_admin() for u in users]}


@router.post("/users", status_code=status.HTTP_201_CREATED)
def create_user(req: UserCreate, admin: User = Depends(require_admin), session: Session = Depends(get_session)):
    username = req.username.strip()
    if session.scalars(select(User).where(User.username == username)).first():
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Username already exists")
    user = User(username=username, password_hash=hash_password(req.password),
                full_name=req.full_name.strip(), role=req.role, active=True)
    session.add(user)
    session.commit()
    logger.info("[Admin] user_id=%s created user_id=%s role=%s", admin.id, user.id, user.role)
    return user.to_admin()


@router.patch("/users/{user_id}")
def update_user(user_id: int, req: UserUpdate, admin: User = Depends(require_admin),
                session: Session = Depends(get_session)):
    user = session.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="User not found")
    if user.id == admin.id and (req.active is False or (req.role is not None and req.role != "admin")):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="You cannot deactivate or demote yourself")
    if req.active is not None:
        user.active = req.active
    if req.password is not None:
        user.password_hash = hash_password(req.password)
    if req.full_name is not None:
        user.full_name = req.full_name.strip()
    if req.role is not None:
        user.role = req.role
    session.commit()
    logger.info("[Admin] user_id=%s updated user_id=%s fields=%s", admin.id, user.id,
                sorted(req.model_dump(exclude_none=True).keys()))
    return user.to_admin()
