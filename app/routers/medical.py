"""
Medical Vitals Router — store and retrieve patient vitals.

  POST /vitals                     — save new vitals reading
  GET  /vitals/{patient_id}        — full history (newest first)
  GET  /vitals/{patient_id}/latest — most recent reading only
"""

import logging

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_session
from app.core.errors import KioskError
from app.core.models import Patient, Vital, iso_z
from app.core.schemas import VitalsCreate
from app.core.security import require_kiosk
from app.services.clinical_rules import news2
from app.services.vitals import compute_flags

logger = logging.getLogger("kiosk.medical")

router = APIRouter(tags=["Medical Vitals"], dependencies=[Depends(require_kiosk)])

VITAL_FIELDS = ("height", "weight", "bp_sys", "bp_dia", "spo2", "diabetes", "hypertension",
                "pulse", "temperature", "resp_rate", "glucose")


def _vital_dict(v: Vital) -> dict:
    data = {"id": v.id, "patient_id": v.patient_id, "created_at": iso_z(v.created_at)}
    for f in VITAL_FIELDS:
        data[f] = getattr(v, f)
    data["diabetes"] = bool(v.diabetes)
    data["hypertension"] = bool(v.hypertension)
    data.update(compute_flags(data))
    data["news2"] = news2(data)
    return data


def _get_patient(session: Session, patient_id: int) -> Patient:
    patient = session.get(Patient, patient_id)
    if patient is None:
        raise KioskError(f"Patient {patient_id} not found.", "நோயாளி கண்டறியப்படவில்லை.", status_code=404)
    return patient


@router.post("/vitals")
def store_vitals(vitals: VitalsCreate, session: Session = Depends(get_session)):
    """Store patient vitals, linked to patient by patient_id FK."""
    _get_patient(session, vitals.patient_id)
    row = Vital(patient_id=vitals.patient_id, **{f: getattr(vitals, f) for f in VITAL_FIELDS})
    session.add(row)
    session.commit()

    flags_data = compute_flags(vitals.model_dump())
    logger.info("[Vitals] Saved id=%s patient_id=%s flags=%d", row.id, vitals.patient_id, len(flags_data["flags"]))
    return {
        "status": "success",
        "vitals_id": row.id,
        "patient_id": vitals.patient_id,
        "bmi": flags_data["bmi"],
        "flags": flags_data["flags"],
        "news2": news2(vitals.model_dump()),
        "message": "Vitals stored successfully",
    }


@router.get("/vitals/{patient_id}/latest")
def get_latest_vitals(patient_id: int, session: Session = Depends(get_session)):
    patient = _get_patient(session, patient_id)
    row = session.scalars(
        select(Vital).where(Vital.patient_id == patient_id)
        .order_by(Vital.created_at.desc(), Vital.id.desc()).limit(1)
    ).first()
    if row is None:
        return {"patient_id": patient_id, "vitals": None}
    return {"patient_id": patient_id, "patient_name": patient.name, "vitals": _vital_dict(row)}


@router.get("/vitals/{patient_id}")
def get_vitals_history(patient_id: int, session: Session = Depends(get_session)):
    patient = _get_patient(session, patient_id)
    rows = session.scalars(
        select(Vital).where(Vital.patient_id == patient_id).order_by(Vital.created_at.desc(), Vital.id.desc())
    ).all()
    history = [_vital_dict(r) for r in rows]
    return {"patient_id": patient_id, "patient_name": patient.name, "count": len(history), "history": history}
