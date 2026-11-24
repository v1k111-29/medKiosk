"""
Staff queue (Bearer token, role nurse or admin).

GET  /queue?dept_id=&status=           today's items, by urgency then token number
POST /queue/{id}/call|start|complete|no-show|requeue
POST /queue/call-next?dept_id=X        call the highest-priority waiting item

Transitions (invalid → 409):
  call     waiting|called            → called   (recall allowed; sets called_at, handled_by)
  start    waiting|called            → in_consult (sets started_at)
  complete called|in_consult         → done     (sets completed_at)
  no-show  waiting|called            → no_show
  requeue  called|in_consult|no_show → waiting
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import update
from sqlalchemy.orm import Session

from app.core.database import get_session
from app.core.models import STATUS_VALUES, Appointment, User, today_local, utcnow
from app.core.security import require_staff
from app.services.queue_service import (
    TRANSITIONS,
    broadcast_change,
    queue_query,
    serialize_item,
    serialize_items,
    status_counts,
)

logger = logging.getLogger("kiosk.queue")

router = APIRouter(prefix="/queue", tags=["Queue"])


@router.get("")
def get_queue(
    dept_id: Optional[str] = Query(None),
    status_: Optional[str] = Query(None, alias="status", description="Status or comma-separated statuses"),
    _: User = Depends(require_staff),
    session: Session = Depends(get_session),
):
    statuses = [s.strip() for s in status_.split(",") if s.strip()] if status_ else None
    if statuses and any(s not in STATUS_VALUES for s in statuses):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"status must be one of {STATUS_VALUES}")
    qd = today_local()
    appts = session.scalars(queue_query(qd, dept_id, statuses)).all()
    return {
        "date": qd.isoformat(),
        "items": serialize_items(session, list(appts)),
        "counts": status_counts(session, qd, dept_id),
    }


def _transition(session: Session, appt_id: int, action: str, user: User) -> Appointment:
    sources, target = TRANSITIONS[action]
    now = utcnow()
    values: dict = {"status": target}
    if action == "call":
        values.update(called_at=now, handled_by=user.id)
    elif action == "start":
        values.update(started_at=now, handled_by=user.id)
    elif action == "complete":
        values.update(completed_at=now)
    elif action == "requeue":
        values.update(called_at=None, started_at=None, completed_at=None)

    # Conditional update: concurrent nurses cannot both win the same transition.
    result = session.execute(
        update(Appointment)
        .where(Appointment.id == appt_id, Appointment.status.in_(sources))
        .values(**values)
        .execution_options(synchronize_session=False)
    )
    if result.rowcount != 1:
        session.rollback()
        appt = session.get(Appointment, appt_id)
        if appt is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Appointment not found")
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail=f"Cannot {action} an appointment with status '{appt.status}'",
        )
    session.commit()
    appt = session.get(Appointment, appt_id, populate_existing=True)
    logger.info("[Queue] %s id=%s token=%s by user_id=%s", action, appt.id, appt.token, user.id)
    broadcast_change(session, appt, called=(action == "call"))
    return appt


@router.post("/call-next")
def call_next(
    dept_id: str = Query(...),
    user: User = Depends(require_staff),
    session: Session = Depends(get_session),
):
    qd = today_local()
    for _ in range(5):
        appt = session.scalars(queue_query(qd, dept_id, ["waiting"]).limit(1)).first()
        if appt is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="No waiting patients in this department")
        try:
            return serialize_item(session, _transition(session, appt.id, "call", user))
        except HTTPException as e:
            if e.status_code != status.HTTP_409_CONFLICT:
                raise
            # Someone else called it first — pick the next one.
    raise HTTPException(status.HTTP_409_CONFLICT, detail="Queue is busy, please retry")


def _make_action(action: str):
    def endpoint(appointment_id: int, user: User = Depends(require_staff), session: Session = Depends(get_session)):
        return serialize_item(session, _transition(session, appointment_id, action, user))

    endpoint.__name__ = f"queue_{action.replace('-', '_')}"
    return endpoint


for _action in TRANSITIONS:
    router.add_api_route(f"/{{appointment_id}}/{_action}", _make_action(_action), methods=["POST"])
