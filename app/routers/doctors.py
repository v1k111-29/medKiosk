"""
Doctors Router — list and query doctors.

GET /doctors           — list all (optionally filter by dept_id)
GET /doctors/{id}      — get single doctor
"""

import logging
from fastapi import APIRouter, Query
from typing import Optional

from app.core.database import get_db
from app.core.errors import KioskError

logger = logging.getLogger("kiosk.doctors")

router = APIRouter(prefix="/doctors", tags=["Doctors"])


@router.get("")
async def list_doctors(dept_id: Optional[str] = Query(None, description="Filter by department")):
    """List all doctors, optionally filtered by department."""
    with get_db() as conn:
        if dept_id:
            rows = conn.execute(
                "SELECT * FROM doctors WHERE dept_id = ? ORDER BY name",
                (dept_id,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM doctors ORDER BY dept_id, name"
            ).fetchall()

        return {
            "doctors": [dict(r) for r in rows],
            "total": len(rows),
        }


@router.get("/{doctor_id}")
async def get_doctor(doctor_id: int):
    """Get a single doctor by ID."""
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM doctors WHERE id = ?", (doctor_id,)
        ).fetchone()

        if not row:
            raise KioskError(
                f"Doctor {doctor_id} not found.",
                "மருத்துவர் கண்டறியப்படவில்லை.",
                status_code=404,
            )

        return dict(row)
