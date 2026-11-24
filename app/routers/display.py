"""
Public waiting-room display board. NEVER returns patient data.

GET /display/now-serving?dept_id= → last 10 called tokens today + waiting counts
"""

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_session
from app.core.models import Appointment, today_local
from app.services.queue_service import display_entry, waiting_counts

router = APIRouter(prefix="/display", tags=["Display"])


def now_serving(session: Session, dept_id: Optional[str] = None) -> dict:
    stmt = (
        select(Appointment)
        .where(Appointment.queue_date == today_local(), Appointment.status == "called")
        .order_by(Appointment.called_at.desc(), Appointment.id.desc())
        .limit(10)
    )
    if dept_id:
        stmt = stmt.where(Appointment.dept_id == dept_id)
    return {
        "now_serving": [display_entry(session, a) for a in session.scalars(stmt)],
        "waiting_counts": waiting_counts(session),
    }


@router.get("/now-serving")
def get_now_serving(dept_id: Optional[str] = Query(None), session: Session = Depends(get_session)):
    return now_serving(session, dept_id)
