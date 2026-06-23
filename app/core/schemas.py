"""
Pydantic schemas for request/response validation.
"""

from pydantic import BaseModel, Field
from typing import Optional


# ── Face Recognition Schemas ───────────────────────────────────────────────

class IdentifyRequest(BaseModel):
    image: str = Field(..., description="Base64 encoded image data URL")


class PatientRegister(BaseModel):
    name: str
    gender: str = "Unknown"
    age: Optional[int] = None
    phone: Optional[str] = None
    blood_group: Optional[str] = None
    city: Optional[str] = None
    embedding: Optional[str] = Field(
        None, description="Hex-encoded raw float32 embedding bytes"
    )


class PatientRead(BaseModel):
    id: int
    name: str
    gender: Optional[str] = None
    age: Optional[int] = None
    phone: Optional[str] = None
    blood_group: Optional[str] = None
    visit_count: int
    created_at: str


# ── Voice Transcription Schemas ──────────────────────────────────────────────

class TranscriptionResponse(BaseModel):
    transcription: str
    status: str
    language: str


# ── Medical Vitals Schemas ──────────────────────────────────────────────────

class VitalsCreate(BaseModel):
    patient_id: int
    height: Optional[float] = None
    weight: Optional[float] = None
    bp_sys: Optional[int] = None
    bp_dia: Optional[int] = None
    spo2: Optional[float] = None
    diabetes: bool = False
    hypertension: bool = False
