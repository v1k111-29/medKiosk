"""
Appointment Router — book and retrieve patient appointments.

POST /appointment/book   — create appointment, generate token, store in DB
GET  /appointment/{id}   — get appointment details
GET  /appointment/patient/{patient_id} — list patient's appointments
"""

import random
import string
import logging
from datetime import datetime
from fastapi import APIRouter
from pydantic import BaseModel, Field
from typing import Optional

from app.core.database import get_db
from app.core.errors import KioskError

logger = logging.getLogger("kiosk.appointment")

router = APIRouter(prefix="/appointment", tags=["Appointments"])


# ── Helpers ───────────────────────────────────────────────────────────────────

DEPT_PREFIX = {
    "general":  "G",
    "cardio":   "C",
    "ortho":    "O",
    "paeds":    "P",
    "gyne":     "GY",
    "derm":     "D",
    "ent":      "E",
    "ophthal":  "OP",
    "emergency":"EM",
}

def _generate_token(dept_id: str) -> str:
    """Generate a human-readable token like C-07, G-23, OP-04."""
    prefix = DEPT_PREFIX.get(dept_id, "T")
    number = random.randint(1, 99)
    return f"{prefix}-{number:02d}"


# ── Schemas ───────────────────────────────────────────────────────────────────

class BookAppointmentRequest(BaseModel):
    patient_id: int = Field(..., description="Registered patient ID")
    dept_id:    str = Field(..., description="Department key e.g. 'general', 'cardio'")
    dept_name:  str = Field(..., description="Department display name")
    room:       Optional[str] = None
    symptoms:   Optional[str] = None
    service:    str = Field("symptoms", description="'symptoms' | 'appointment' | 'followup' | 'emergency'")
    wait_mins:  int = Field(15, description="Estimated wait in minutes")
    doctor_id:  Optional[int] = Field(None, description="Selected doctor ID")
    doctor_name: Optional[str] = Field(None, description="Selected doctor name")


class BookAppointmentResponse(BaseModel):
    appointment_id: int
    token:     str
    dept_id:   str
    dept_name: str
    room:      Optional[str]
    wait_mins: int
    service:   str
    symptoms:  Optional[str]
    doctor_id:   Optional[int] = None
    doctor_name: Optional[str] = None
    created_at: str
    status:    str = "success"


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/book", response_model=BookAppointmentResponse)
async def book_appointment(req: BookAppointmentRequest):
    """
    Book an appointment for a registered patient.
    Generates a unique token, stores in DB, returns full appointment details.
    """
    with get_db() as conn:
        # Verify patient exists and fetch their details
        patient = conn.execute(
            "SELECT id, name FROM patients WHERE id = ?", (req.patient_id,)
        ).fetchone()

        if not patient:
            raise KioskError(
                f"Patient ID {req.patient_id} not found.",
                "நோயாளி கண்டறியப்படவில்லை.",
                status_code=404,
            )

        # Generate a unique token (retry if collision)
        token = _generate_token(req.dept_id)
        for _ in range(5):
            existing = conn.execute(
                "SELECT id FROM appointments WHERE token = ? AND DATE(created_at) = DATE('now')",
                (token,)
            ).fetchone()
            if not existing:
                break
            token = _generate_token(req.dept_id)

        # Insert appointment
        cursor = conn.execute(
            """
            INSERT INTO appointments
                (patient_id, token, dept_id, dept_name, room, symptoms, service, wait_mins, doctor_id, doctor_name)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                req.patient_id,
                token,
                req.dept_id,
                req.dept_name,
                req.room,
                req.symptoms,
                req.service,
                req.wait_mins,
                req.doctor_id,
                req.doctor_name,
            ),
        )
        conn.commit()
        appt_id = cursor.lastrowid

        logger.info(
            f"[Appointment] Booked: token={token}, patient={patient['name']}, "
            f"dept={req.dept_name}, id={appt_id}"
        )

        return BookAppointmentResponse(
            appointment_id=appt_id,
            token=token,
            dept_id=req.dept_id,
            dept_name=req.dept_name,
            room=req.room,
            wait_mins=req.wait_mins,
            service=req.service,
            symptoms=req.symptoms,
            doctor_id=req.doctor_id,
            doctor_name=req.doctor_name,
            created_at=datetime.now().isoformat(),
        )


@router.get("/patient/{patient_id}")
async def get_patient_appointments(patient_id: int):
    """Get all appointments for a patient (today's first, then historical)."""
    with get_db() as conn:
        rows = conn.execute(
            """
            SELECT a.*, p.name as patient_name
            FROM appointments a
            JOIN patients p ON p.id = a.patient_id
            WHERE a.patient_id = ?
            ORDER BY a.created_at DESC
            LIMIT 20
            """,
            (patient_id,),
        ).fetchall()

        return {
            "patient_id": patient_id,
            "appointments": [dict(r) for r in rows],
            "total": len(rows),
        }


@router.get("/{appointment_id}")
async def get_appointment(appointment_id: int):
    """Get a single appointment by ID."""
    with get_db() as conn:
        row = conn.execute(
            """
            SELECT a.*, p.name as patient_name, p.phone as patient_phone
            FROM appointments a
            JOIN patients p ON p.id = a.patient_id
            WHERE a.id = ?
            """,
            (appointment_id,),
        ).fetchone()

        if not row:
            raise KioskError(
                f"Appointment {appointment_id} not found.",
                "சந்திப்பு கண்டறியப்படவில்லை.",
                status_code=404,
            )

        return dict(row)
