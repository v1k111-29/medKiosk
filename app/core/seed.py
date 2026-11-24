"""
Idempotent seed data: departments (single source of truth for rooms), doctors
and demo staff users.
"""

from __future__ import annotations

import logging

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.models import Department, Doctor, User
from app.core.security import hash_password

logger = logging.getLogger("kiosk.seed")

# id, name_en, name_ta, room, prefix, avg_wait, color, icon
DEPARTMENTS = [
    ("general",   "General Medicine", "பொது மருத்துவம்",     "OPD-1", "G",  20, "#2E7D96", "🏥"),
    ("paeds",     "Paediatrics",      "குழந்தை நலம்",        "OPD-2", "P",  15, "#059669", "👶"),
    ("cardio",    "Cardiology",       "இதய நோயியல்",         "OPD-3", "C",  30, "#DC2626", "❤️"),
    ("ortho",     "Orthopaedics",     "எலும்பு சிகிச்சை",     "OPD-4", "O",  25, "#7C3AED", "🦴"),
    ("gyne",      "Gynaecology",      "மகளிர் நலம்",          "OPD-5", "GY", 20, "#DB2777", "👩"),
    ("derm",      "Dermatology",      "தோல் நோய்",           "OPD-6", "D",  15, "#D97706", "✨"),
    ("ent",       "ENT",              "காது மூக்கு தொண்டை",   "OPD-7", "E",  15, "#4F46E5", "👂"),
    ("ophthal",   "Ophthalmology",    "கண் நோய்",            "OPD-8", "OP", 20, "#2563EB", "👁️"),
    ("emergency", "Emergency",        "அவசர சிகிச்சை",        "ER-1",  "EM", 0,  "#B91C1C", "🚨"),
]

# name, dept_id, qualification  (room / dept_name come from the departments table)
DOCTORS = [
    ("Dr. Rajesh Kumar",     "general",   "MD, General Medicine"),
    ("Dr. Priya Sharma",     "general",   "MBBS, DNB"),
    ("Dr. Suresh Menon",     "cardio",    "DM Cardiology"),
    ("Dr. Anitha Rao",       "cardio",    "MD, Cardiology"),
    ("Dr. Vikram Singh",     "ortho",     "MS Ortho"),
    ("Dr. Kavitha Nair",     "ortho",     "MCh Ortho"),
    ("Dr. Meena Iyer",       "paeds",     "MD Paediatrics"),
    ("Dr. Lakshmi Devi",     "gyne",      "MS OBG"),
    ("Dr. Deepa Rajan",      "gyne",      "DGO"),
    ("Dr. Arjun Pillai",     "derm",      "MD Dermatology"),
    ("Dr. Srinivas Reddy",   "ent",       "MS ENT"),
    ("Dr. Farida Begum",     "ent",       "DNB ENT"),
    ("Dr. Ganesh Subramani", "ophthal",   "MS Ophthalmology"),
    ("Dr. Karthik Rajan",    "emergency", "MD Emergency Medicine"),
    ("Dr. Revathi Kumar",    "emergency", "MD, Critical Care"),
]

DEMO_USERS = [
    ("nurse1", "Nurse@123", "Demo Nurse", "nurse"),
    ("admin", "Admin@123", "Demo Admin", "admin"),
]


def seed_departments(session: Session) -> None:
    existing = set(session.scalars(select(Department.id)))
    added = 0
    for dept_id, name_en, name_ta, room, prefix, wait, color, icon in DEPARTMENTS:
        if dept_id in existing:
            continue
        session.add(Department(
            id=dept_id, name_en=name_en, name_ta=name_ta, room=room, token_prefix=prefix,
            avg_wait_mins=wait, color=color, icon=icon, active=True,
        ))
        added += 1
    session.flush()
    if added:
        logger.info("[Seed] Added %d departments", added)


def seed_doctors(session: Session) -> None:
    depts = {d.id: d for d in session.scalars(select(Department))}
    if session.scalar(select(func.count()).select_from(Doctor)) == 0:
        for name, dept_id, qual in DOCTORS:
            d = depts[dept_id]
            session.add(Doctor(name=name, dept_id=dept_id, dept_name=d.name_en,
                               qualification=qual, available=True, room=d.room))
        logger.info("[Seed] Added %d doctors", len(DOCTORS))
    # Keep doctor rooms / dept names in sync with the departments table.
    for d in depts.values():
        session.execute(
            update(Doctor)
            .where(Doctor.dept_id == d.id, (Doctor.room != d.room) | (Doctor.dept_name != d.name_en))
            .values(room=d.room, dept_name=d.name_en)
        )
    session.flush()


def seed_demo_users(session: Session) -> None:
    if not settings.SEED_DEMO_USERS:
        return
    if session.scalar(select(func.count()).select_from(User)) > 0:
        return
    for username, password, full_name, role in DEMO_USERS:
        session.add(User(username=username, password_hash=hash_password(password),
                         full_name=full_name, role=role, active=True))
    session.flush()
    if settings.is_prod:
        logger.warning(
            "[Seed] Demo users (nurse1, admin) created in PRODUCTION with well-known passwords. "
            "Change their passwords or deactivate them now, and set SEED_DEMO_USERS=false."
        )
    else:
        logger.info("[Seed] Demo users created: nurse1 (nurse), admin (admin)")


def seed_all(session: Session) -> None:
    seed_departments(session)
    seed_doctors(session)
    seed_demo_users(session)
