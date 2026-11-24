"""
Departments Router — the departments table is the single source of truth for
department names, rooms, token prefixes and average wait times.

GET /departments — active departments. Public (no kiosk key / auth): the
                   waiting-room display board uses it too.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_session
from app.services.queue_service import list_departments

router = APIRouter(tags=["Departments"])


@router.get("/departments")
def get_departments(session: Session = Depends(get_session)):
    return {"departments": list_departments(session)}
