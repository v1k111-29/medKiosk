"""
Doctors Router — list and query doctors.

GET /doctors           — list all (optionally filter by dept_id)
GET /doctors/{id}      — get single doctor
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_session
from app.core.errors import KioskError
from app.core.models import Doctor, iso_z
from app.core.security import require_kiosk

logger = logging.getLogger("kiosk.doctors")

router = APIRouter(prefix="/doctors", tags=["Doctors"], dependencies=[Depends(require_kiosk)])


def _doctor_dict(d: Doctor) -> dict:
    return {
        "id": d.id,
        "name": d.name,
        "dept_id": d.dept_id,
        "dept_name": d.dept_name,
        "qualification": d.qualification,
        "available": bool(d.available),
        "room": d.room,
        "created_at": iso_z(d.created_at),
    }


@router.get("")
def list_doctors(
    dept_id: Optional[str] = Query(None, description="Filter by department"),
    session: Session = Depends(get_session),
):
    stmt = select(Doctor)
    if dept_id:
        stmt = stmt.where(Doctor.dept_id == dept_id).order_by(Doctor.name)
    else:
        stmt = stmt.order_by(Doctor.dept_id, Doctor.name)
    rows = session.scalars(stmt).all()
    return {"doctors": [_doctor_dict(d) for d in rows], "total": len(rows)}


@router.get("/{doctor_id}")
def get_doctor(doctor_id: int, session: Session = Depends(get_session)):
    d = session.get(Doctor, doctor_id)
    if d is None:
        raise KioskError(f"Doctor {doctor_id} not found.", "மருத்துவர் கண்டறியப்படவில்லை.", status_code=404)
    return _doctor_dict(d)
