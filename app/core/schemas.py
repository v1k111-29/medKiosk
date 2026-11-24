"""
Pydantic schemas for request/response validation.
"""

from pydantic import BaseModel, Field
from typing import Optional


# ── Face Recognition Schemas ───────────────────────────────────────────────

class IdentifyRequest(BaseModel):
    image: str = Field(..., description="Base64 encoded image data URL")
    match_only: bool = Field(
        False,
        description="Only look for a returning (face-consented) patient. For a non-match the response is "
                    "just {\"status\":\"new\"}: no embedding or gender is returned. Used by the kiosk "
                    "before the visitor has given face consent.",
    )


class PhoneStartRequest(BaseModel):
    phone: str = Field(..., min_length=10, max_length=20)


class PhoneVerifyRequest(BaseModel):
    phone: str = Field(..., min_length=10, max_length=20)
    otp: str = Field(..., min_length=4, max_length=8)


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
    face_consent: bool = Field(
        ...,
        description="Required. True only if the visitor agreed on the face-consent screen; the "
                    "embedding is stored only when true.",
    )
    consent_version: Optional[str] = Field(
        None, description="Ignored — the server records its current consent text version"
    )
    phone_verification_token: Optional[str] = Field(
        None,
        description="From POST /identify/phone/verify. Required unless face_consent=true with an "
                    "embedding; `phone` must be the verified number.",
    )


class PatientRead(BaseModel):
    id: int
    name: str
    gender: Optional[str] = None
    age: Optional[int] = None
    phone: Optional[str] = None
    blood_group: Optional[str] = None
    visit_count: Optional[int] = None
    created_at: Optional[str] = None
    face_consent: bool = False


# ── Voice Transcription Schemas ──────────────────────────────────────────────

class TranscriptionResponse(BaseModel):
    transcription: str
    status: str
    language: str


# ── Medical Vitals Schemas ──────────────────────────────────────────────────

class VitalsCreate(BaseModel):
    """All optional. Ranges reject obvious typos, not clinically extreme values."""
    patient_id: int
    height: Optional[float] = Field(None, ge=30, le=250, description="cm")
    weight: Optional[float] = Field(None, ge=1, le=350, description="kg")
    bp_sys: Optional[int] = Field(None, ge=50, le=300)
    bp_dia: Optional[int] = Field(None, ge=20, le=200)
    spo2: Optional[float] = Field(None, ge=50, le=100)
    diabetes: bool = False
    hypertension: bool = False
    pulse: Optional[int] = Field(None, ge=20, le=250, description="beats/min")
    temperature: Optional[float] = Field(None, ge=30, le=45, description="Body temperature in °C")
    resp_rate: Optional[int] = Field(None, ge=4, le=60, description="breaths/min")
    glucose: Optional[float] = Field(None, ge=20, le=800, description="Blood glucose in mg/dL")
