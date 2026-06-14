from fastapi import APIRouter
from app.core.database import get_med_db
from app.core.schemas import VitalsCreate
from app.core.errors import KioskError

router = APIRouter(tags=["Medical Vitals"])

@router.post("/vitals")
async def store_vitals(vitals: VitalsCreate):
    try:
        conn = get_med_db()
        conn.execute("""
            INSERT INTO vitals (patient_id, height, weight, bp_sys, bp_dia, spo2, diabetes, hypertension)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            vitals.patient_id,
            vitals.height,
            vitals.weight,
            vitals.bp_sys,
            vitals.bp_dia,
            vitals.spo2,
            vitals.diabetes,
            vitals.hypertension
        ))
        conn.commit()
        conn.close()
        return {"status": "success", "message": "Vitals stored"}
    except Exception as e:
        raise KioskError(
            "Failed to save medical records. Please try again.",
            "மருத்துவ பதிவுகளைச் சேமிக்க முடியவில்லை. மீண்டும் முயற்சிக்கவும்.",
            status_code=500
        )
