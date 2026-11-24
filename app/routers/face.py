"""
Face Recognition Router — patient identification and registration.

Multi-shot gallery matching:
- Each patient stores up to FACE_GALLERY_SIZE embeddings in face_embeddings.
- On identify: loads all galleries, uses minimum cosine distance per patient.
- On re-identify: adds the new embedding to the gallery (online learning).
- Legacy fallback: if a gallery is empty, patients.embedding is migrated into it.
- Only patients with face_consent=true are matched.

Threshold: FACE_MATCH_THRESHOLD (ArcFace cosine distance; same person <0.42, different >0.50).

Consent:
- `/identify` with `match_only=true` (kiosk, before consent) never returns or stores
  anything for a non-match.
- `/register` requires an explicit `face_consent`; the embedding is stored only when true.
- Visitors who decline identify by phone: `/identify/phone/start` + `/identify/phone/verify`.
- Admins can withdraw face data with `DELETE /patients/{id}/face`.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from typing import List, Optional

import numpy as np
from fastapi import APIRouter, Depends, HTTPException
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_session, session_scope
from app.core.errors import KioskError
from app.core.models import FaceEmbedding, Patient, iso_z, utcnow
from app.core.schemas import IdentifyRequest, PatientRead, PatientRegister, PhoneStartRequest, PhoneVerifyRequest
from app.core.security import require_admin, require_kiosk
from app.services.face_service import (
    MATCH_THRESHOLD,
    MAX_GALLERY_SIZE,
    best_gallery_distance,
    decode_image,
    deserialize_embedding,
    detect_gender_async,
    get_embedding_async,
    serialize_embedding,
)
from app.services import otp_service
from app.services.sms import mask_phone, normalize_phone_in, send_otp_sms

logger = logging.getLogger("kiosk.face")
router = APIRouter(tags=["Face Recognition"])

# Version of the consent text shown on the kiosk consent screen.
# TODO: move to settings when the consent text becomes configurable.
CONSENT_VERSION = "v1-2026-11"


# ── Gallery helpers ────────────────────────────────────────────────────────────

def _count_gallery(session: Session, patient_id: int) -> int:
    return int(session.scalar(
        select(func.count()).select_from(FaceEmbedding).where(FaceEmbedding.patient_id == patient_id)
    ) or 0)


def _add_to_gallery(session: Session, patient_id: int, embedding: np.ndarray) -> None:
    """Add an embedding to the patient's gallery; when full, replace the oldest entry."""
    emb_bytes = serialize_embedding(embedding)
    if _count_gallery(session, patient_id) >= MAX_GALLERY_SIZE:
        oldest = session.scalars(
            select(FaceEmbedding).where(FaceEmbedding.patient_id == patient_id).order_by(FaceEmbedding.id).limit(1)
        ).first()
        oldest.embedding = emb_bytes
        oldest.created_at = utcnow()
    else:
        session.add(FaceEmbedding(patient_id=patient_id, embedding=emb_bytes))


def _find_match(session: Session, embedding: np.ndarray, threshold: float):
    """Returns (patient | None, best_dist, per-candidate log)."""
    consented = set(session.scalars(select(Patient.id).where(Patient.face_consent.is_(True))))
    galleries: dict[int, list] = defaultdict(list)
    for pid, emb in session.execute(select(FaceEmbedding.patient_id, FaceEmbedding.embedding)):
        if pid not in consented:
            continue
        arr = deserialize_embedding(emb)
        if arr is not None:
            galleries[pid].append(arr)

    # Lazily migrate legacy single embeddings into the gallery.
    migrated = False
    for pid, emb in session.execute(
        select(Patient.id, Patient.embedding).where(Patient.embedding.is_not(None), Patient.face_consent.is_(True))
    ):
        if pid in galleries:
            continue
        arr = deserialize_embedding(emb)
        if arr is not None:
            session.add(FaceEmbedding(patient_id=pid, embedding=bytes(emb), angle_hint="legacy"))
            galleries[pid] = [arr]
            migrated = True
    if migrated:
        session.commit()

    best_dist, best_pid = 1.0, None
    dist_log = []
    for pid, gallery in galleries.items():
        dist = best_gallery_distance(embedding, gallery)
        dist_log.append({"id": pid, "dist": round(dist, 4), "gallery": len(gallery), "match": dist <= threshold})
        if dist < best_dist:
            best_dist, best_pid = dist, pid

    match = session.get(Patient, best_pid) if best_pid is not None and best_dist <= threshold else None
    return match, best_dist, dist_log


def _found_payload(p: Patient, distance: Optional[float] = None) -> dict:
    out = {
        "status": "found",
        "id": p.id,
        "name": p.name,
        "gender": p.gender or "Unknown",
        "age": p.age,
        "phone": p.phone,
        "visits": p.visit_count,
    }
    if distance is not None:
        out["distance"] = round(distance, 4)
    return out


def _identify_db(embedding: np.ndarray) -> dict:
    with session_scope() as session:
        match, dist, dist_log = _find_match(session, embedding, MATCH_THRESHOLD)
        logger.info("[Face] Identify best_dist=%.4f threshold=%s match=%s candidates=%d",
                    dist, MATCH_THRESHOLD, "YES" if match else "NO", len(dist_log))
        for d in dist_log:
            logger.debug("  candidate id=%s dist=%s gallery=%s", d["id"], d["dist"], d["gallery"])
        if match is None:
            return {"match": None, "dist": dist}
        match.visit_count = (match.visit_count or 0) + 1
        _add_to_gallery(session, match.id, embedding)
        session.flush()
        return {"match": _found_payload(match, dist), "dist": dist}


# ── Kiosk endpoints ───────────────────────────────────────────────────────────

@router.post("/identify", dependencies=[Depends(require_kiosk)])
async def identify(req: IdentifyRequest):
    """Identify patient — multi-shot gallery matching."""
    try:
        img = decode_image(req.image)
    except ValueError as e:
        raise KioskError(str(e), "தவறான படம்.", status_code=400)

    embedding = await get_embedding_async(img)
    if embedding is None:
        return JSONResponse({"status": "no_face", "message": "No face detected — please look straight at the camera"})

    try:
        result = await run_in_threadpool(_identify_db, embedding)
    except Exception as e:
        logger.error("[Face] DB search error: %s", e)
        raise KioskError("Database search failed.", "தரவுத்தள தேடல் தோல்வி.", status_code=500)

    if result["match"]:
        return result["match"]

    if req.match_only:
        # Pre-consent scan: nothing about a non-matching visitor leaves the server or is stored.
        return {"status": "new"}

    gender = await detect_gender_async(img)
    logger.info("[Face] New visitor — closest_dist=%.4f", result["dist"])
    return {"status": "new", "gender": gender, "embedding": serialize_embedding(embedding).hex()}


@router.post("/register", dependencies=[Depends(require_kiosk)])
def register(patient: PatientRegister, session: Session = Depends(get_session)):
    """Register a new patient and (only with explicit consent) seed the face gallery."""
    face_consent = bool(patient.face_consent)
    if patient.embedding and not face_consent:
        logger.info("[Face] Embedding supplied without face consent — discarded")

    embedding_arr = None
    emb_bytes = None
    if patient.embedding and face_consent:
        try:
            emb_bytes = bytes.fromhex(patient.embedding)
        except ValueError as e:
            raise KioskError(f"Invalid embedding: {e}", "தவறான embedding", status_code=400)
        embedding_arr = deserialize_embedding(emb_bytes)
        if embedding_arr is None:
            raise KioskError("Invalid embedding: bad size", "தவறான embedding", status_code=400)

    row = Patient(
        name=patient.name,
        gender=patient.gender,
        age=patient.age,
        phone=normalize_phone_in(patient.phone) or patient.phone,
        blood_group=patient.blood_group,
        city=patient.city,
        embedding=emb_bytes,
        consent_given=face_consent,
        face_consent=face_consent,
        consent_at=utcnow() if face_consent else None,
        consent_version=CONSENT_VERSION if face_consent else None,
    )
    session.add(row)
    session.flush()
    if embedding_arr is not None:
        _add_to_gallery(session, row.id, embedding_arr)
    session.commit()

    logger.info("[Face] Registered patient id=%s face_consent=%s gallery=%s",
                row.id, face_consent, "seeded" if embedding_arr is not None else "empty")
    return {"status": "registered", "id": row.id, "name": row.name}


# ── Phone identification (face opt-out) ───────────────────────────────────────

def _require_phone(raw: str) -> str:
    phone = normalize_phone_in(raw)
    if not phone:
        raise KioskError("Please enter a valid 10-digit mobile number.",
                         "சரியான 10 இலக்க மொபைல் எண்ணை உள்ளிடவும்.", status_code=400)
    return phone


def _patients_by_phone(session: Session, phone_e164: str) -> list[Patient]:
    # Stored numbers may contain spaces/dashes (older kiosks); narrow by the last 4 digits,
    # then compare normalised values.
    last4 = phone_e164[-4:]
    rows = session.scalars(
        select(Patient).where(Patient.phone.like(f"%{last4}"))
        .order_by(Patient.created_at.desc(), Patient.id.desc())
    ).all()
    return [p for p in rows if normalize_phone_in(p.phone) == phone_e164]


@router.post("/identify/phone/start", dependencies=[Depends(require_kiosk)])
def identify_phone_start(req: PhoneStartRequest, session: Session = Depends(get_session)):
    """Send a 6-digit code by SMS. Same response whether or not the number is registered."""
    phone = _require_phone(req.phone)
    try:
        otp = otp_service.start(session, phone)
    except otp_service.OtpRateLimited:
        raise KioskError(
            "Too many codes requested. Please wait a few minutes or ask at the front desk.",
            "அதிக முறை குறியீடு கேட்கப்பட்டது. சில நிமிடங்கள் கழித்து முயற்சிக்கவும் அல்லது வரவேற்பில் கேளுங்கள்.",
            status_code=429,
        )
    sms_status = send_otp_sms(phone, otp)
    logger.info("[Phone] OTP issued to %s sms=%s", mask_phone(phone), sms_status)
    return {"status": "otp_sent"}


@router.post("/identify/phone/verify", dependencies=[Depends(require_kiosk)])
def identify_phone_verify(req: PhoneVerifyRequest, session: Session = Depends(get_session)):
    """Check the code. Found → same shape as /identify (plus `other_patients` sharing the number); else `new`."""
    phone = _require_phone(req.phone)
    result = otp_service.verify(session, phone, req.otp)
    if not result.ok:
        if result.reason == "invalid":
            raise KioskError(
                f"Incorrect code. {result.attempts_left} attempt(s) left.",
                f"தவறான குறியீடு. இன்னும் {result.attempts_left} முயற்சி(கள்) உள்ளன.",
                status_code=400,
            )
        if result.reason == "expired":
            raise KioskError("This code has expired. Please request a new one.",
                             "குறியீடு காலாவதியானது. புதிய குறியீட்டைக் கேளுங்கள்.", status_code=400)
        raise KioskError("Too many wrong attempts. Please request a new code.",
                         "அதிக தவறான முயற்சிகள். புதிய குறியீட்டைக் கேளுங்கள்.", status_code=429)

    patients = _patients_by_phone(session, phone)
    if not patients:
        logger.info("[Phone] Verified %s — no patient, continue to registration", mask_phone(phone))
        return {"status": "new", "phone": phone}

    match = patients[0]
    match.visit_count = (match.visit_count or 0) + 1
    session.commit()
    logger.info("[Phone] Verified %s — patient id=%s (others=%d)", mask_phone(phone), match.id, len(patients) - 1)
    out = _found_payload(match)
    out["other_patients"] = [_found_payload(p) for p in patients[1:]]
    return out


# ── Admin endpoints ───────────────────────────────────────────────────────────

@router.post("/identify/debug", dependencies=[Depends(require_admin)])
async def identify_debug(req: IdentifyRequest):
    """Admin-only threshold tuning: distances to all patients, no side effects. Disabled in prod."""
    if settings.is_prod:
        raise HTTPException(404, "Not found")
    try:
        img = decode_image(req.image)
    except ValueError as e:
        return {"error": str(e)}

    embedding = await get_embedding_async(img)
    if embedding is None:
        return {"status": "no_face", "candidates": []}

    def _run():
        with session_scope() as session:
            match, dist, dist_log = _find_match(session, embedding, MATCH_THRESHOLD)
            names = dict(session.execute(select(Patient.id, Patient.name)).all())
            for d in dist_log:
                d["name"] = names.get(d["id"])
            return (match.name if match else None), dist, dist_log

    would_match, dist, dist_log = await run_in_threadpool(_run)
    return {
        "status": "found" if would_match else "no_match",
        "best_dist": round(dist, 4),
        "threshold": MATCH_THRESHOLD,
        "would_match": would_match,
        "candidates": sorted(dist_log, key=lambda x: x.get("dist") or 9),
    }


@router.get("/patients", response_model=List[PatientRead], dependencies=[Depends(require_admin)])
def list_patients(session: Session = Depends(get_session)):
    rows = session.scalars(select(Patient).order_by(Patient.id.desc())).all()
    return [
        {
            "id": p.id, "name": p.name, "gender": p.gender, "age": p.age, "phone": p.phone,
            "blood_group": p.blood_group, "visit_count": p.visit_count,
            "created_at": iso_z(p.created_at), "face_consent": bool(p.face_consent),
        }
        for p in rows
    ]


@router.get("/patients/{pid}/gallery", dependencies=[Depends(require_admin)])
def patient_gallery_info(pid: int, session: Session = Depends(get_session)):
    patient = session.get(Patient, pid)
    if patient is None:
        raise HTTPException(404, "Patient not found")
    return {
        "patient_id": pid,
        "name": patient.name,
        "gallery_count": _count_gallery(session, pid),
        "max_gallery": MAX_GALLERY_SIZE,
        "threshold": MATCH_THRESHOLD,
    }


@router.post("/patients/migrate-gallery", dependencies=[Depends(require_admin)])
def migrate_all_to_gallery(session: Session = Depends(get_session)):
    """Copy legacy patients.embedding into face_embeddings for patients with no gallery yet."""
    migrated, skipped = 0, 0
    with_gallery = set(session.scalars(select(FaceEmbedding.patient_id).distinct()))
    for pid, emb in session.execute(select(Patient.id, Patient.embedding)):
        if not emb or pid in with_gallery or deserialize_embedding(emb) is None:
            skipped += 1
            continue
        session.add(FaceEmbedding(patient_id=pid, embedding=bytes(emb), angle_hint="legacy"))
        migrated += 1
    session.commit()
    logger.info("[Migrate] gallery migrated=%d skipped=%d", migrated, skipped)
    return {"status": "done", "migrated": migrated, "skipped": skipped,
            "message": f"Migrated {migrated} patients into face gallery"}


@router.delete("/patients/{pid}/face", dependencies=[Depends(require_admin)])
def delete_patient_face(pid: int, session: Session = Depends(get_session)):
    """Withdraw face consent: delete all face templates and stop face matching for this patient."""
    patient = session.get(Patient, pid)
    if patient is None:
        raise HTTPException(404, "Patient not found")
    deleted = session.execute(delete(FaceEmbedding).where(FaceEmbedding.patient_id == pid)).rowcount or 0
    patient.embedding = None
    patient.face_consent = False
    patient.consent_given = False
    patient.consent_at = None
    patient.consent_version = None
    session.commit()
    logger.info("[Face] Deleted face data for patient id=%s (templates=%d)", pid, deleted)
    return {"status": "face_deleted", "id": pid, "templates_deleted": deleted, "face_consent": False}


@router.delete("/patients/{pid}", dependencies=[Depends(require_admin)])
def delete_patient(pid: int, session: Session = Depends(get_session)):
    patient = session.get(Patient, pid)
    if patient is None:
        raise HTTPException(404, "Patient not found")
    # Explicit child deletes so this also works where FK cascades are not enforced.
    session.execute(delete(FaceEmbedding).where(FaceEmbedding.patient_id == pid))
    session.delete(patient)
    session.commit()
    logger.info("[Face] Deleted patient id=%s", pid)
    return {"status": "deleted", "id": pid}
