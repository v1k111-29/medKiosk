"""
Appointment Router — book and retrieve patient appointments.

POST /appointment/book                 — create appointment with a sequential token
GET  /appointment/{id}                 — get appointment details
GET  /appointment/patient/{patient_id} — list a patient's appointments
"""

from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Literal, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import get_session
from app.core.errors import KioskError
from app.core.models import Appointment, Department, Doctor, Patient, iso_z, today_local
from app.core.security import require_kiosk
from app.services.queue_service import broadcast_change, format_token, next_token_number, queue_position
from app.services.sms import send_token_sms

logger = logging.getLogger("kiosk.appointment")

router = APIRouter(prefix="/appointment", tags=["Appointments"], dependencies=[Depends(require_kiosk)])


# ── Schemas ───────────────────────────────────────────────────────────────────

class BookAppointmentRequest(BaseModel):
    patient_id: int = Field(..., description="Registered patient ID")
    dept_id: str = Field(..., description="Department key e.g. 'general', 'cardio'")
    dept_name: Optional[str] = Field(None, description="Ignored — server uses the departments table")
    room: Optional[str] = Field(None, description="Ignored — server uses the departments table")
    symptoms: Optional[str] = None
    service: str = Field("symptoms", description="'symptoms' | 'appointment' | 'followup' | 'emergency'")
    wait_mins: Optional[int] = Field(None, description="Ignored — computed by the server")
    doctor_id: Optional[int] = Field(None, description="Selected doctor ID")
    doctor_name: Optional[str] = Field(None, description="Ignored — taken from the doctors table")
    urgency: Literal["normal", "urgent", "emergency"] = "normal"
    sms_opt_in: bool = False


class BookAppointmentResponse(BaseModel):
    appointment_id: int
    token: str
    token_number: int
    dept_id: str
    dept_name: str
    room: Optional[str]
    queue_position: int
    wait_mins: int
    service: str
    symptoms: Optional[str]
    urgency: str
    doctor_id: Optional[int] = None
    doctor_name: Optional[str] = None
    sms_status: str
    created_at: str
    status: str = "success"


def _appointment_dict(a: Appointment) -> dict:
    out = {}
    for col in Appointment.__table__.columns:
        v = getattr(a, col.key)
        if isinstance(v, datetime):
            v = iso_z(v)
        elif isinstance(v, date):
            v = v.isoformat()
        out[col.key] = v
    return out


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/book", response_model=BookAppointmentResponse)
def book_appointment(req: BookAppointmentRequest, session: Session = Depends(get_session)):
    """Book an appointment: sequential per-department daily token, queue position, optional SMS."""
    patient = session.get(Patient, req.patient_id)
    if patient is None:
        raise KioskError(f"Patient ID {req.patient_id} not found.", "நோயாளி கண்டறியப்படவில்லை.", status_code=404)

    dept = session.get(Department, req.dept_id)
    if dept is None or not dept.active:
        raise KioskError(f"Unknown department '{req.dept_id}'.", "துறை கண்டறியப்படவில்லை.", status_code=400)

    urgency = "emergency" if dept.id == "emergency" else req.urgency

    doctor_id, doctor_name = None, None
    if req.doctor_id is not None:
        doc = session.get(Doctor, req.doctor_id)
        if doc is not None and doc.dept_id == dept.id:
            doctor_id, doctor_name = doc.id, doc.name
        else:
            logger.warning("[Appointment] Ignoring doctor_id=%s (not in dept %s)", req.doctor_id, dept.id)

    queue_date = today_local()
    appt: Optional[Appointment] = None
    for attempt in range(3):
        try:
            number = next_token_number(session, dept.id, queue_date)
            appt = Appointment(
                patient_id=patient.id,
                token=format_token(dept.token_prefix, number),
                token_number=number,
                queue_date=queue_date,
                dept_id=dept.id,
                dept_name=dept.name_en,
                room=dept.room,
                symptoms=req.symptoms,
                service=req.service,
                status="waiting",
                urgency=urgency,
                doctor_id=doctor_id,
                doctor_name=doctor_name,
                sms_opt_in=req.sms_opt_in,
                sms_status="not_requested",
            )
            session.add(appt)
            session.flush()
            position = queue_position(session, appt)
            wait = 0 if (dept.id == "emergency" or urgency == "emergency") else (position - 1) * dept.avg_wait_mins
            appt.wait_mins = wait
            session.commit()
            break
        except IntegrityError:
            session.rollback()
            logger.warning("[Appointment] Token collision in %s (attempt %d) — retrying", dept.id, attempt + 1)
            appt = None
    if appt is None:
        raise KioskError("Could not allocate a token. Please try again.", "டோக்கன் ஒதுக்க முடியவில்லை.", 503)

    # SMS after commit — never holds a DB lock during the HTTP call, never fails booking.
    if req.sms_opt_in:
        appt.sms_status = send_token_sms(patient.phone, appt.token, dept.room, dept.name_en, appt.wait_mins)
        session.commit()

    logger.info("[Appointment] Booked id=%s token=%s dept=%s pos=%s patient_id=%s",
                appt.id, appt.token, dept.id, position, patient.id)

    try:
        broadcast_change(session, appt)
    except Exception as e:  # realtime is best-effort
        logger.warning("[Appointment] Broadcast failed: %s", e)

    return BookAppointmentResponse(
        appointment_id=appt.id,
        token=appt.token,
        token_number=appt.token_number,
        dept_id=dept.id,
        dept_name=dept.name_en,
        room=dept.room,
        queue_position=position,
        wait_mins=appt.wait_mins,
        service=appt.service,
        symptoms=appt.symptoms,
        urgency=appt.urgency,
        doctor_id=appt.doctor_id,
        doctor_name=appt.doctor_name,
        sms_status=appt.sms_status,
        created_at=iso_z(appt.created_at),
    )


@router.get("/patient/{patient_id}")
def get_patient_appointments(patient_id: int, session: Session = Depends(get_session)):
    """Last 20 appointments for a patient, newest first."""
    rows = session.scalars(
        select(Appointment)
        .where(Appointment.patient_id == patient_id)
        .order_by(Appointment.created_at.desc(), Appointment.id.desc())
        .limit(20)
    ).all()
    appts = []
    for a in rows:
        d = _appointment_dict(a)
        d["patient_name"] = a.patient.name if a.patient else None
        appts.append(d)
    return {"patient_id": patient_id, "appointments": appts, "total": len(appts)}


@router.get("/{appointment_id}")
def get_appointment(appointment_id: int, session: Session = Depends(get_session)):
    a = session.get(Appointment, appointment_id)
    if a is None:
        raise KioskError(f"Appointment {appointment_id} not found.", "சந்திப்பு கண்டறியப்படவில்லை.", status_code=404)
    d = _appointment_dict(a)
    d["patient_name"] = a.patient.name if a.patient else None
    d["patient_phone"] = a.patient.phone if a.patient else None
    return d
