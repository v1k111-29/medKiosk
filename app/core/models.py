"""
SQLAlchemy 2.0 ORM models. Schema changes must go through an Alembic migration.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Optional

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
    false,
    text,
    true,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utcnow() -> datetime:
    """Naive UTC timestamp. All DateTime columns store UTC."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def iso_z(dt: Optional[datetime]) -> Optional[str]:
    """Serialise a stored (naive UTC) datetime as ISO 8601 with a Z suffix."""
    if dt is None:
        return None
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt.replace(microsecond=0).isoformat() + "Z"


def today_local() -> date:
    """Queue business date: the hospital's local calendar day (server clock)."""
    return datetime.now().date()


class Base(DeclarativeBase):
    pass


URGENCY_VALUES = ("normal", "urgent", "emergency")
STATUS_VALUES = ("waiting", "called", "in_consult", "done", "no_show")
SMS_STATUS_VALUES = ("not_requested", "sent", "failed", "mocked")
ROLE_VALUES = ("nurse", "admin")


class Department(Base):
    __tablename__ = "departments"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    name_en: Mapped[str] = mapped_column(Text, nullable=False)
    name_ta: Mapped[str] = mapped_column(Text, nullable=False)
    room: Mapped[str] = mapped_column(Text, nullable=False)
    token_prefix: Mapped[str] = mapped_column(String(8), nullable=False)
    avg_wait_mins: Mapped[int] = mapped_column(Integer, nullable=False, default=15)
    color: Mapped[Optional[str]] = mapped_column(Text)
    icon: Mapped[Optional[str]] = mapped_column(Text)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=true())

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name_en": self.name_en,
            "name_ta": self.name_ta,
            "room": self.room,
            "token_prefix": self.token_prefix,
            "avg_wait_mins": self.avg_wait_mins,
            "color": self.color,
            "icon": self.icon,
            "active": bool(self.active),
        }


class Patient(Base):
    __tablename__ = "patients"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    gender: Mapped[Optional[str]] = mapped_column(Text)
    age: Mapped[Optional[int]] = mapped_column(Integer)
    phone: Mapped[Optional[str]] = mapped_column(Text)
    blood_group: Mapped[Optional[str]] = mapped_column(Text)
    city: Mapped[Optional[str]] = mapped_column(Text)
    embedding: Mapped[Optional[bytes]] = mapped_column(LargeBinary)
    consent_given: Mapped[Optional[bool]] = mapped_column(Boolean, default=False, server_default=false())
    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, default=utcnow, server_default=text("CURRENT_TIMESTAMP")
    )
    visit_count: Mapped[Optional[int]] = mapped_column(Integer, default=1, server_default=text("1"))
    face_consent: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=false())
    consent_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    consent_version: Mapped[Optional[str]] = mapped_column(Text)


class Vital(Base):
    __tablename__ = "vitals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    patient_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("patients.id", ondelete="CASCADE"), nullable=False
    )
    height: Mapped[Optional[float]] = mapped_column(Float)
    weight: Mapped[Optional[float]] = mapped_column(Float)
    bp_sys: Mapped[Optional[int]] = mapped_column(Integer)
    bp_dia: Mapped[Optional[int]] = mapped_column(Integer)
    spo2: Mapped[Optional[float]] = mapped_column(Float)
    diabetes: Mapped[Optional[bool]] = mapped_column(Boolean, default=False, server_default=false())
    hypertension: Mapped[Optional[bool]] = mapped_column(Boolean, default=False, server_default=false())
    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, default=utcnow, server_default=text("CURRENT_TIMESTAMP")
    )
    pulse: Mapped[Optional[int]] = mapped_column(Integer)
    temperature: Mapped[Optional[float]] = mapped_column(Float)
    resp_rate: Mapped[Optional[int]] = mapped_column(Integer)
    glucose: Mapped[Optional[float]] = mapped_column(Float)


class FaceEmbedding(Base):
    __tablename__ = "face_embeddings"
    __table_args__ = (Index("idx_face_emb_patient", "patient_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    patient_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("patients.id", ondelete="CASCADE"), nullable=False
    )
    embedding: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    angle_hint: Mapped[Optional[str]] = mapped_column(Text)
    quality: Mapped[Optional[float]] = mapped_column(Float)
    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, default=utcnow, server_default=text("CURRENT_TIMESTAMP")
    )


class Doctor(Base):
    __tablename__ = "doctors"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    dept_id: Mapped[str] = mapped_column(Text, nullable=False)
    dept_name: Mapped[str] = mapped_column(Text, nullable=False)
    qualification: Mapped[Optional[str]] = mapped_column(Text)
    available: Mapped[Optional[bool]] = mapped_column(Boolean, default=True, server_default=true())
    room: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, default=utcnow, server_default=text("CURRENT_TIMESTAMP")
    )


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    full_name: Mapped[str] = mapped_column(Text, nullable=False)
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=true())
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=utcnow, server_default=text("CURRENT_TIMESTAMP")
    )

    def to_public(self) -> dict:
        return {
            "id": self.id,
            "username": self.username,
            "full_name": self.full_name,
            "role": self.role,
        }

    def to_admin(self) -> dict:
        return {
            **self.to_public(),
            "active": bool(self.active),
            "created_at": iso_z(self.created_at),
        }


class TokenCounter(Base):
    __tablename__ = "token_counters"

    dept_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    queue_date: Mapped[date] = mapped_column(Date, primary_key=True)
    last_number: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text("0"))


class Appointment(Base):
    __tablename__ = "appointments"
    __table_args__ = (
        UniqueConstraint("dept_id", "queue_date", "token_number", name="uq_appointments_dept_date_token"),
        Index("ix_appointments_queue", "queue_date", "dept_id", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    patient_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("patients.id", ondelete="CASCADE"), nullable=False
    )
    token: Mapped[str] = mapped_column(Text, nullable=False)
    dept_id: Mapped[str] = mapped_column(Text, nullable=False)
    dept_name: Mapped[str] = mapped_column(Text, nullable=False)
    room: Mapped[Optional[str]] = mapped_column(Text)
    symptoms: Mapped[Optional[str]] = mapped_column(Text)
    service: Mapped[Optional[str]] = mapped_column(Text, default="symptoms", server_default=text("'symptoms'"))
    status: Mapped[Optional[str]] = mapped_column(Text, default="waiting", server_default=text("'waiting'"))
    wait_mins: Mapped[Optional[int]] = mapped_column(Integer, default=15, server_default=text("15"))
    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, default=utcnow, server_default=text("CURRENT_TIMESTAMP")
    )
    doctor_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("doctors.id"))
    doctor_name: Mapped[Optional[str]] = mapped_column(Text)

    token_number: Mapped[Optional[int]] = mapped_column(Integer)
    queue_date: Mapped[Optional[date]] = mapped_column(Date)
    urgency: Mapped[str] = mapped_column(
        String(16), nullable=False, default="normal", server_default=text("'normal'")
    )
    called_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    handled_by: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id", name="fk_appointments_handled_by"))
    sms_opt_in: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=false())
    sms_status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="not_requested", server_default=text("'not_requested'")
    )
    # JSON-encoded list[str] of why the server raised urgency (red flags, NEWS2, LLM).
    escalation_reasons: Mapped[Optional[str]] = mapped_column(Text)

    patient: Mapped[Patient] = relationship(lazy="joined")


class PhoneOtp(Base):
    """One-time codes for phone identification (patients who decline face recognition).

    Only a keyed hash of the code is stored. Rows are short-lived; old rows can be purged.
    """

    __tablename__ = "phone_otps"
    __table_args__ = (Index("ix_phone_otps_phone_created", "phone", "created_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    phone: Mapped[str] = mapped_column(String(16), nullable=False)  # E.164
    otp_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=utcnow, server_default=text("CURRENT_TIMESTAMP")
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text("0"))
    consumed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
