"""
Face Recognition Router — patient identification and registration.

Multi-shot gallery matching:
- Each patient stores up to MAX_GALLERY_SIZE embeddings in face_embeddings.
- On identify: loads full gallery, uses minimum cosine distance across all.
- On re-identify: adds new embedding to gallery (online learning).
- Legacy fallback: if gallery empty, uses patients.embedding column.

Threshold: 0.45 (ArcFace cosine distance — same person <0.42, diff >0.50)
"""

from fastapi import APIRouter, HTTPException, Header
from fastapi.responses import JSONResponse
import numpy as np
import os
import logging
from typing import List, Optional

from app.services.face_service import (
    decode_image,
    get_embedding_async,
    detect_gender_async,
    cosine_dist,
    best_gallery_distance,
    serialize_embedding,
    deserialize_embedding,
    MATCH_THRESHOLD,
    MAX_GALLERY_SIZE,
)
from app.core.database import get_db
from app.core.schemas import IdentifyRequest, PatientRegister, PatientRead
from app.core.errors import KioskError

logger = logging.getLogger("kiosk.face")
router = APIRouter(tags=["Face Recognition"])

API_KEY = os.getenv("KIOSK_API_KEY", "dev-key-change-in-production")


def verify_api_key(x_api_key: Optional[str] = Header(None)) -> bool:
    if API_KEY == "dev-key-change-in-production":
        return True
    return x_api_key == API_KEY


# ── Gallery helpers ────────────────────────────────────────────────────────────

def _load_gallery(conn, patient_id: int) -> list:
    """Load all stored embeddings for a patient from the gallery table."""
    rows = conn.execute(
        "SELECT embedding FROM face_embeddings WHERE patient_id = ? ORDER BY id",
        (patient_id,),
    ).fetchall()
    gallery = []
    for row in rows:
        emb = deserialize_embedding(row["embedding"])
        if emb is not None:
            gallery.append(emb)
    return gallery


def _count_gallery(conn, patient_id: int) -> int:
    return conn.execute(
        "SELECT COUNT(*) FROM face_embeddings WHERE patient_id = ?",
        (patient_id,),
    ).fetchone()[0]


def _add_to_gallery(conn, patient_id: int, embedding: np.ndarray) -> None:
    """
    Add a new embedding to the patient's gallery.
    If full (>= MAX_GALLERY_SIZE), replace the oldest entry.
    """
    count    = _count_gallery(conn, patient_id)
    emb_bytes = serialize_embedding(embedding)

    if count >= MAX_GALLERY_SIZE:
        oldest_id = conn.execute(
            "SELECT id FROM face_embeddings WHERE patient_id = ? ORDER BY id ASC LIMIT 1",
            (patient_id,),
        ).fetchone()["id"]
        conn.execute(
            "UPDATE face_embeddings SET embedding = ?, created_at = CURRENT_TIMESTAMP WHERE id = ?",
            (emb_bytes, oldest_id),
        )
        logger.debug(f"[Gallery] Replaced oldest for patient {patient_id} (gallery full at {MAX_GALLERY_SIZE})")
    else:
        conn.execute(
            "INSERT INTO face_embeddings (patient_id, embedding) VALUES (?, ?)",
            (patient_id, emb_bytes),
        )
        logger.debug(f"[Gallery] Added embedding #{count + 1}/{MAX_GALLERY_SIZE} for patient {patient_id}")

    conn.commit()


def _migrate_legacy_to_gallery(conn, patient_id: int, legacy_emb: np.ndarray) -> None:
    """
    Migrate a patient's legacy patients.embedding into the gallery table
    if their gallery is currently empty. Called lazily on first identify.
    """
    if _count_gallery(conn, patient_id) == 0:
        emb_bytes = serialize_embedding(legacy_emb)
        conn.execute(
            "INSERT INTO face_embeddings (patient_id, embedding, angle_hint) VALUES (?, ?, ?)",
            (patient_id, emb_bytes, "legacy"),
        )
        conn.commit()
        logger.info(f"[Gallery] Migrated legacy embedding for patient {patient_id}")


# ── Core match logic ──────────────────────────────────────────────────────────

def _find_match_sync(conn, embedding: np.ndarray, threshold: float):
    """
    Synchronous match logic — runs inside get_db() context.
    Returns (patient_dict, best_dist, all_distances_log).
    """
    patients = conn.execute(
        "SELECT id, name, gender, age, phone, embedding, visit_count FROM patients"
    ).fetchall()

    best_dist, best_patient = 1.0, None
    dist_log = []   # for debug endpoint

    for patient in patients:
        pid = patient["id"]

        # Load gallery; lazily migrate legacy embedding if needed
        gallery = _load_gallery(conn, pid)
        if not gallery and patient["embedding"]:
            legacy = deserialize_embedding(patient["embedding"])
            if legacy is not None:
                _migrate_legacy_to_gallery(conn, pid, legacy)
                gallery = [legacy]

        if not gallery:
            dist_log.append({"id": pid, "name": patient["name"], "dist": None, "note": "no embedding"})
            continue

        dist = best_gallery_distance(embedding, gallery)
        dist_log.append({
            "id":      pid,
            "name":    patient["name"],
            "dist":    round(dist, 4),
            "gallery": len(gallery),
            "match":   dist <= threshold,
        })

        if dist < best_dist:
            best_dist    = dist
            best_patient = patient

    match = dict(best_patient) if best_patient and best_dist <= threshold else None
    return match, best_dist, dist_log


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/identify")
async def identify(req: IdentifyRequest):
    """Identify patient — multi-shot gallery matching."""
    try:
        img = decode_image(req.image)
    except ValueError as e:
        raise KioskError(str(e), "தவறான படம்.", status_code=400)

    embedding = await get_embedding_async(img)
    if embedding is None:
        return JSONResponse({
            "status":  "no_face",
            "message": "No face detected — please look straight at the camera",
        })

    try:
        with get_db() as conn:
            match, dist, dist_log = _find_match_sync(conn, embedding, MATCH_THRESHOLD)
    except Exception as e:
        logger.error(f"[Face] DB search error: {e}")
        raise KioskError("Database search failed.", "தரவுத்தள தேடல் தோல்வி.", status_code=500)

    # Always log distances so we can tune threshold from server logs
    logger.info(f"[Face] Identify — best_dist={dist:.4f} threshold={MATCH_THRESHOLD} match={'YES' if match else 'NO'}")
    for d in dist_log:
        logger.info(f"  candidate id={d['id']} name={d['name']} dist={d.get('dist')} gallery={d.get('gallery', 0)}")

    if match:
        pid = match["id"]
        with get_db() as conn:
            conn.execute("UPDATE patients SET visit_count = visit_count + 1 WHERE id = ?", (pid,))
            # Online learning: add new embedding to gallery
            _add_to_gallery(conn, pid, embedding)
            updated = conn.execute(
                "SELECT visit_count FROM patients WHERE id = ?", (pid,)
            ).fetchone()

        return {
            "status":   "found",
            "id":       pid,
            "name":     match["name"],
            "gender":   match["gender"] or "Unknown",
            "age":      match["age"],
            "phone":    match["phone"],
            "visits":   updated["visit_count"],
            "distance": round(dist, 4),
        }

    # New visitor
    gender    = await detect_gender_async(img)
    emb_bytes = serialize_embedding(embedding)
    logger.info(f"[Face] New visitor — closest_dist={dist:.4f} (threshold={MATCH_THRESHOLD})")
    return {
        "status":    "new",
        "gender":    gender,
        "embedding": emb_bytes.hex(),
    }


@router.post("/identify/debug")
async def identify_debug(req: IdentifyRequest):
    """
    Debug endpoint — returns cosine distances to ALL patients without side effects.
    Use this to tune the threshold.
    """
    try:
        img = decode_image(req.image)
    except ValueError as e:
        return {"error": str(e)}

    embedding = await get_embedding_async(img)
    if embedding is None:
        return {"status": "no_face", "candidates": []}

    with get_db() as conn:
        match, dist, dist_log = _find_match_sync(conn, embedding, MATCH_THRESHOLD)

    return {
        "status":       "found" if match else "no_match",
        "best_dist":    round(dist, 4),
        "threshold":    MATCH_THRESHOLD,
        "would_match":  match["name"] if match else None,
        "candidates":   sorted(dist_log, key=lambda x: x.get("dist") or 9),
    }


@router.post("/register")
async def register(patient: PatientRegister, x_api_key: Optional[str] = Header(None)):
    """Register new patient and seed the face gallery."""
    if not verify_api_key(x_api_key):
        raise HTTPException(status_code=403, detail="Invalid or missing API key")

    try:
        emb_bytes     = None
        embedding_arr = None
        if patient.embedding:
            try:
                emb_bytes     = bytes.fromhex(patient.embedding)
                embedding_arr = deserialize_embedding(emb_bytes)
                if embedding_arr is None:
                    raise ValueError("Invalid embedding bytes")
            except ValueError as e:
                raise KioskError(f"Invalid embedding: {e}", "தவறான embedding", status_code=400)

        with get_db() as conn:
            cur = conn.execute(
                """INSERT INTO patients
                   (name, gender, age, phone, blood_group, city, embedding, consent_given)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    patient.name, patient.gender, patient.age,
                    patient.phone, patient.blood_group, patient.city,
                    emb_bytes, 1,
                ),
            )
            new_id = cur.lastrowid
            conn.commit()

            # Seed gallery immediately on registration
            if embedding_arr is not None:
                _add_to_gallery(conn, new_id, embedding_arr)

        logger.info(f"[Face] Registered patient id={new_id} name={patient.name} gallery={'seeded' if embedding_arr is not None else 'empty'}")
        return {"status": "registered", "id": new_id, "name": patient.name}

    except KioskError:
        raise
    except Exception as e:
        logger.error(f"Registration error: {e}")
        raise KioskError("Registration failed.", "பதிவு தோல்வியடைந்தது.", status_code=500)


# ── Admin ─────────────────────────────────────────────────────────────────────

@router.get("/patients", response_model=List[PatientRead])
async def list_patients():
    with get_db() as conn:
        rows = conn.execute(
            "SELECT id, name, gender, age, phone, blood_group, visit_count, created_at "
            "FROM patients ORDER BY id DESC"
        ).fetchall()
    return [dict(r) for r in rows]


@router.get("/patients/{pid}/gallery")
async def patient_gallery_info(pid: int):
    """How many gallery embeddings does this patient have?"""
    with get_db() as conn:
        patient = conn.execute("SELECT id, name FROM patients WHERE id = ?", (pid,)).fetchone()
        if not patient:
            raise HTTPException(404, "Patient not found")
        count = _count_gallery(conn, pid)
    return {
        "patient_id":    pid,
        "name":          patient["name"],
        "gallery_count": count,
        "max_gallery":   MAX_GALLERY_SIZE,
        "threshold":     MATCH_THRESHOLD,
    }


@router.post("/patients/migrate-gallery")
async def migrate_all_to_gallery():
    """
    One-time migration: copy the legacy patients.embedding into face_embeddings
    for any patient who has an embedding but no gallery entries yet.
    Run this once after upgrading to the multi-shot gallery system.
    """
    migrated, skipped = 0, 0
    with get_db() as conn:
        patients = conn.execute("SELECT id, name, embedding FROM patients").fetchall()
        for p in patients:
            if not p["embedding"]:
                skipped += 1
                continue
            if _count_gallery(conn, p["id"]) > 0:
                skipped += 1
                continue
            emb = deserialize_embedding(p["embedding"])
            if emb is None:
                skipped += 1
                continue
            conn.execute(
                "INSERT INTO face_embeddings (patient_id, embedding, angle_hint) VALUES (?, ?, ?)",
                (p["id"], p["embedding"], "legacy"),
            )
            migrated += 1
            logger.info(f"[Migrate] patient id={p['id']} name={p['name']}")
        conn.commit()

    return {
        "status":   "done",
        "migrated": migrated,
        "skipped":  skipped,
        "message":  f"Migrated {migrated} patients into face gallery",
    }


@router.delete("/patients/{pid}")
async def delete_patient(pid: int, x_api_key: Optional[str] = Header(None)):
    if not verify_api_key(x_api_key):
        raise HTTPException(status_code=403, detail="Invalid or missing API key")
    try:
        with get_db() as conn:
            conn.execute("DELETE FROM patients WHERE id = ?", (pid,))
            conn.commit()
        return {"status": "deleted", "id": pid}
    except Exception as e:
        logger.error(f"Delete error: {e}")
        raise HTTPException(500, "Failed to delete patient")
