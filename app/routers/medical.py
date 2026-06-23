"""
Medical Vitals Router — store and retrieve patient vitals.

All vitals are stored in patients.db, linked to the patient via patient_id FK.
Endpoints:
  POST /vitals              — save new vitals reading
  GET  /vitals/{patient_id} — full history (newest first)
  GET  /vitals/{patient_id}/latest — most recent reading only
"""

from fastapi import APIRouter
from typing import Optional
import logging

from app.core.database import get_db
from app.core.schemas import VitalsCreate
from app.core.errors import KioskError

logger = logging.getLogger("kiosk.medical")

router = APIRouter(tags=["Medical Vitals"])


# ── Helpers ───────────────────────────────────────────────────────────────────

def _compute_flags(vitals: dict) -> dict:
    """Compute clinical flags from raw vitals values."""
    flags = []
    bmi = None

    h = vitals.get("height")
    w = vitals.get("weight")
    if h and w and h > 0:
        bmi = round(w / ((h / 100) ** 2), 1)
        if bmi < 18.5:
            flags.append("Underweight")
        elif bmi >= 30:
            flags.append("Obese")
        elif bmi >= 25:
            flags.append("Overweight")

    bp_sys = vitals.get("bp_sys")
    bp_dia = vitals.get("bp_dia")
    if bp_sys:
        if bp_sys >= 180 or (bp_dia and bp_dia >= 120):
            flags.append("Hypertensive Crisis")
        elif bp_sys >= 140 or (bp_dia and bp_dia >= 90):
            flags.append("Stage 2 Hypertension")
        elif bp_sys >= 130 or (bp_dia and bp_dia >= 80):
            flags.append("Stage 1 Hypertension")
        elif bp_sys < 90:
            flags.append("Low BP")

    spo2 = vitals.get("spo2")
    if spo2:
        if spo2 < 90:
            flags.append("Critical SpO₂ — Needs Oxygen")
        elif spo2 < 95:
            flags.append("Low SpO₂")

    if vitals.get("diabetes"):
        flags.append("Known Diabetic")
    if vitals.get("hypertension"):
        flags.append("Known Hypertensive")

    return {"bmi": bmi, "flags": flags}


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/vitals")
async def store_vitals(vitals: VitalsCreate):
    """Store patient vitals, linked to patient by patient_id FK."""
    try:
        with get_db() as conn:
            # Verify patient exists
            patient = conn.execute(
                "SELECT id, name FROM patients WHERE id = ?",
                (vitals.patient_id,),
            ).fetchone()
            if not patient:
                raise KioskError(
                    f"Patient ID {vitals.patient_id} not found.",
                    "நோயாளி எண் கிடைக்கவில்லை.",
                    status_code=404,
                )

            cur = conn.execute(
                """
                INSERT INTO vitals
                    (patient_id, height, weight, bp_sys, bp_dia,
                     spo2, diabetes, hypertension)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    vitals.patient_id,
                    vitals.height,
                    vitals.weight,
                    vitals.bp_sys,
                    vitals.bp_dia,
                    vitals.spo2,
                    vitals.diabetes,
                    vitals.hypertension,
                ),
            )
            conn.commit()
            vitals_id = cur.lastrowid

        # Compute clinical flags
        flags_data = _compute_flags(vitals.model_dump())
        logger.info(
            f"[Vitals] Saved id={vitals_id} patient={patient['name']} "
            f"BMI={flags_data['bmi']} flags={flags_data['flags']}"
        )

        return {
            "status":    "success",
            "vitals_id": vitals_id,
            "patient_id": vitals.patient_id,
            "bmi":       flags_data["bmi"],
            "flags":     flags_data["flags"],
            "message":   "Vitals stored successfully",
        }

    except KioskError:
        raise
    except Exception as e:
        logger.error(f"Vitals save error: {e}")
        raise KioskError(
            "Failed to save vitals. Please try again.",
            "அளவீடுகளைச் சேமிக்க முடியவில்லை.",
            status_code=500,
        )


@router.get("/vitals/{patient_id}/latest")
async def get_latest_vitals(patient_id: int):
    """Get the most recent vitals reading for a patient."""
    with get_db() as conn:
        # Verify patient
        patient = conn.execute(
            "SELECT id, name FROM patients WHERE id = ?", (patient_id,)
        ).fetchone()
        if not patient:
            raise KioskError(
                f"Patient {patient_id} not found.", "நோயாளி கண்டறியப்படவில்லை.",
                status_code=404,
            )

        row = conn.execute(
            """
            SELECT * FROM vitals
            WHERE patient_id = ?
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (patient_id,),
        ).fetchone()

    if not row:
        return {"patient_id": patient_id, "vitals": None}

    data = dict(row)
    data.update(_compute_flags(data))
    return {"patient_id": patient_id, "patient_name": patient["name"], "vitals": data}


@router.get("/vitals/{patient_id}")
async def get_vitals_history(patient_id: int):
    """Get full vitals history for a patient, newest first."""
    with get_db() as conn:
        patient = conn.execute(
            "SELECT id, name FROM patients WHERE id = ?", (patient_id,)
        ).fetchone()
        if not patient:
            raise KioskError(
                f"Patient {patient_id} not found.", "நோயாளி கண்டறியப்படவில்லை.",
                status_code=404,
            )

        rows = conn.execute(
            "SELECT * FROM vitals WHERE patient_id = ? ORDER BY created_at DESC",
            (patient_id,),
        ).fetchall()

    history = []
    for row in rows:
        data = dict(row)
        data.update(_compute_flags(data))
        history.append(data)

    return {
        "patient_id":   patient_id,
        "patient_name": patient["name"],
        "count":        len(history),
        "history":      history,
    }
