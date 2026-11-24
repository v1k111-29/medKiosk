"""
Face Recognition Router — patient identification and registration.

Multi-shot gallery matching:
- Each patient stores up to FACE_GALLERY_SIZE embeddings in face_embeddings.
- On identify: loads all galleries, uses minimum cosine distance per patient.
- On re-identify: adds the new embedding to the gallery (online learning).
- Legacy fallback: if a gallery is empty, patients.embedding is migrated into it.
- Only patients with face_consent=true are matched.

Threshold: FACE_MATCH_THRESHOLD (ArcFace cosine distance; same person <0.42, different >0.50).
"""

from __future__ import annotations

import logging
from collections import defaultdict
from typing import List

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
from app.core.schemas import IdentifyRequest, PatientRead, PatientRegister
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

logger = logging.getLogger("kiosk.face")
router = APIRouter(tags=["Face Recognition"])

DEFAULT_CONSENT_VERSION = "v1"


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
        return {
            "match": {
                "status": "found",
                "id": match.id,
                "name": match.name,
                "gender": match.gender or "Unknown",
                "age": match.age,
                "phone": match.phone,
                "visits": match.visit_count,
                "distance": round(dist, 4),
            },
            "dist": dist,
        }


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

    gender = await detect_gender_async(img)
    logger.info("[Face] New visitor — closest_dist=%.4f", result["dist"])
    return {"status": "new", "gender": gender, "embedding": serialize_embedding(embedding).hex()}


@router.post("/register", dependencies=[Depends(require_kiosk)])
def register(patient: PatientRegister, session: Session = Depends(get_session)):
    """Register a new patient and (with consent) seed the face gallery."""
    face_consent = True if patient.face_consent is None else bool(patient.face_consent)

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
        phone=patient.phone,
        blood_group=patient.blood_group,
        city=patient.city,
        embedding=emb_bytes,
        consent_given=face_consent,
        face_consent=face_consent,
        consent_at=utcnow() if face_consent else None,
        consent_version=(patient.consent_version or DEFAULT_CONSENT_VERSION) if face_consent else None,
    )
    session.add(row)
    session.flush()
    if embedding_arr is not None:
        _add_to_gallery(session, row.id, embedding_arr)
    session.commit()

    logger.info("[Face] Registered patient id=%s face_consent=%s gallery=%s",
                row.id, face_consent, "seeded" if embedding_arr is not None else "empty")
    return {"status": "registered", "id": row.id, "name": row.name}


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
