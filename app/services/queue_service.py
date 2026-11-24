"""
Queue domain logic shared by booking, the staff queue, the display board and websockets.
"""

from __future__ import annotations

from datetime import date, datetime, time, timezone
from typing import Iterable, Optional

from sqlalchemy import case, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from app.core.models import Appointment, Department, Patient, TokenCounter, Vital, iso_z, today_local
from app.services.realtime import DISPLAY, STAFF, hub
from app.services.sms import mask_phone
from app.services.vitals import compute_flags

URGENCY_RANK = case(
    (Appointment.urgency == "emergency", 0),
    (Appointment.urgency == "urgent", 1),
    else_=2,
)

# Allowed source statuses for each action → target status
TRANSITIONS: dict[str, tuple[tuple[str, ...], str]] = {
    "call":     (("waiting", "called"), "called"),
    "start":    (("waiting", "called"), "in_consult"),
    "complete": (("called", "in_consult"), "done"),
    "no-show":  (("waiting", "called"), "no_show"),
    "requeue":  (("called", "in_consult", "no_show"), "waiting"),
}


# ── Departments ───────────────────────────────────────────────────────────────

def departments_map(session: Session, active_only: bool = False) -> dict[str, Department]:
    stmt = select(Department)
    if active_only:
        stmt = stmt.where(Department.active.is_(True))
    return {d.id: d for d in session.scalars(stmt)}


def list_departments(session: Session) -> list[dict]:
    rows = session.scalars(
        select(Department)
        .where(Department.active.is_(True))
        .order_by(case((Department.id == "emergency", 1), else_=0), Department.room)
    )
    return [d.to_dict() for d in rows]


# ── Tokens ────────────────────────────────────────────────────────────────────

def next_token_number(session: Session, dept_id: str, queue_date: date) -> int:
    """Atomically increment and return the per-department daily counter.

    Single `INSERT .. ON CONFLICT DO UPDATE .. RETURNING` statement: row-locked on
    Postgres; on SQLite the write lock serialises it for the transaction.
    """
    dialect = session.get_bind().dialect.name
    ins = pg_insert if dialect == "postgresql" else sqlite_insert
    stmt = ins(TokenCounter).values(dept_id=dept_id, queue_date=queue_date, last_number=1)
    stmt = stmt.on_conflict_do_update(
        index_elements=[TokenCounter.dept_id, TokenCounter.queue_date],
        set_={"last_number": TokenCounter.last_number + 1},
    ).returning(TokenCounter.last_number)
    return int(session.execute(stmt).scalar_one())


def format_token(prefix: str, number: int) -> str:
    return f"{prefix}-{number:03d}"


def queue_position(session: Session, appt: Appointment) -> int:
    ahead = session.scalar(
        select(func.count()).select_from(Appointment).where(
            Appointment.dept_id == appt.dept_id,
            Appointment.queue_date == appt.queue_date,
            Appointment.status == "waiting",
            Appointment.id < appt.id,
        )
    )
    return int(ahead or 0) + 1


def waiting_counts(session: Session, queue_date: Optional[date] = None) -> dict[str, int]:
    queue_date = queue_date or today_local()
    counts = {d: 0 for d in departments_map(session, active_only=True)}
    rows = session.execute(
        select(Appointment.dept_id, func.count())
        .where(Appointment.queue_date == queue_date, Appointment.status == "waiting")
        .group_by(Appointment.dept_id)
    )
    for dept_id, n in rows:
        counts[dept_id] = int(n)
    return counts


def status_counts(session: Session, queue_date: date, dept_id: Optional[str] = None) -> dict[str, int]:
    counts = {s: 0 for s in ("waiting", "called", "in_consult", "done", "no_show")}
    stmt = (
        select(Appointment.status, func.count())
        .where(Appointment.queue_date == queue_date)
        .group_by(Appointment.status)
    )
    if dept_id:
        stmt = stmt.where(Appointment.dept_id == dept_id)
    for st, n in session.execute(stmt):
        if st in counts:
            counts[st] = int(n)
    return counts


def local_day_start_utc(day: date) -> datetime:
    """Naive-UTC instant at which the local calendar day `day` starts."""
    return datetime.combine(day, time.min).astimezone(timezone.utc).replace(tzinfo=None)


# ── Serialisation ─────────────────────────────────────────────────────────────

def _latest_vitals_today(session: Session, patient_ids: Iterable[int], queue_date: date) -> dict[int, Vital]:
    ids = list(set(patient_ids))
    if not ids:
        return {}
    rows = session.scalars(
        select(Vital)
        .where(Vital.patient_id.in_(ids), Vital.created_at >= local_day_start_utc(queue_date))
        .order_by(Vital.created_at.desc(), Vital.id.desc())
    )
    latest: dict[int, Vital] = {}
    for v in rows:
        latest.setdefault(v.patient_id, v)
    return latest


def _vitals_dict(v: Optional[Vital]) -> Optional[dict]:
    if v is None:
        return None
    raw = {c: getattr(v, c) for c in (
        "height", "weight", "bp_sys", "bp_dia", "spo2", "pulse", "temperature",
        "resp_rate", "glucose", "diabetes", "hypertension")}
    return {
        "bp_sys": v.bp_sys, "bp_dia": v.bp_dia, "spo2": v.spo2, "pulse": v.pulse,
        "temperature": v.temperature, "glucose": v.glucose,
        "flags": compute_flags(raw)["flags"],
    }


def _patient_dict(p: Optional[Patient]) -> Optional[dict]:
    if p is None:
        return None
    return {"id": p.id, "name": p.name, "age": p.age, "gender": p.gender, "phone_masked": mask_phone(p.phone)}


def serialize_items(session: Session, appts: list[Appointment]) -> list[dict]:
    depts = departments_map(session)
    by_date: dict[date, list[int]] = {}
    for a in appts:
        by_date.setdefault(a.queue_date or today_local(), []).append(a.patient_id)
    vitals: dict[tuple[date, int], Vital] = {}
    for qd, pids in by_date.items():
        for pid, v in _latest_vitals_today(session, pids, qd).items():
            vitals[(qd, pid)] = v
    items = []
    for a in appts:
        d = depts.get(a.dept_id)
        items.append({
            "appointment_id": a.id,
            "token": a.token,
            "dept_id": a.dept_id,
            "dept_name": d.name_en if d else a.dept_name,
            "room": d.room if d else a.room,
            "status": a.status,
            "urgency": a.urgency,
            "symptoms": a.symptoms,
            "created_at": iso_z(a.created_at),
            "called_at": iso_z(a.called_at),
            "patient": _patient_dict(a.patient),
            "vitals": _vitals_dict(vitals.get((a.queue_date or today_local(), a.patient_id))),
        })
    return items


def serialize_item(session: Session, appt: Appointment) -> dict:
    return serialize_items(session, [appt])[0]


def display_entry(session: Session, appt: Appointment) -> dict:
    """Public (no PII) representation for the waiting-room board."""
    d = session.get(Department, appt.dept_id)
    return {
        "token": appt.token,
        "room": d.room if d else appt.room,
        "dept_id": appt.dept_id,
        "dept_name": d.name_en if d else appt.dept_name,
        "called_at": iso_z(appt.called_at),
    }


# ── Queries ───────────────────────────────────────────────────────────────────

def queue_query(queue_date: date, dept_id: Optional[str] = None, statuses: Optional[list[str]] = None):
    stmt = select(Appointment).where(Appointment.queue_date == queue_date)
    if dept_id:
        stmt = stmt.where(Appointment.dept_id == dept_id)
    if statuses:
        stmt = stmt.where(Appointment.status.in_(statuses))
    return stmt.order_by(URGENCY_RANK, Appointment.token_number, Appointment.id)


# ── Broadcasting ──────────────────────────────────────────────────────────────

def broadcast_change(session: Session, appt: Appointment, called: bool = False) -> None:
    """Publish queue.updated (staff), token.called (display, on call) and counts (display)."""
    hub.publish(STAFF, {"type": "queue.updated", "data": serialize_item(session, appt)})
    if called:
        hub.publish(DISPLAY, {"type": "token.called", "data": display_entry(session, appt)})
    hub.publish(DISPLAY, {"type": "counts", "data": waiting_counts(session)})
