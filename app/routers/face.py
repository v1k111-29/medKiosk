from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
import base64
import pickle
import numpy as np
from typing import List
from app.services.face_service import decode_image, get_embedding_async, detect_gender_async, cosine_dist
from app.core.database import get_db
from app.core.schemas import IdentifyRequest, PatientRegister, PatientRead
from app.core.errors import KioskError

router = APIRouter(tags=["Face Recognition"])

async def find_match(embedding: np.ndarray, threshold: float = 0.40):
    conn = get_db()
    rows = conn.execute(
        "SELECT id, name, gender, age, embedding, visit_count, created_at FROM patients"
    ).fetchall()
    conn.close()

    best_dist, best_row = 1.0, None
    for row in rows:
        try:
            stored = pickle.loads(row["embedding"])
            d = cosine_dist(embedding, stored)
            if d < best_dist:
                best_dist, best_row = d, row
        except Exception as e:
            print(f"[Face] Corrupt embedding in DB for ID {row['id']}: {str(e)}")
            continue

    if best_dist <= threshold and best_row:
        return dict(best_row), best_dist
    return None, best_dist

@router.post("/identify")
async def identify(req: IdentifyRequest):
    try:
        img = decode_image(req.image)
    except Exception:
        raise KioskError(
            "Invalid image data received.",
            "தவறான படத் தரவு பெறப்பட்டது.",
            status_code=400
        )

    embedding = await get_embedding_async(img)
    if embedding is None:
        return JSONResponse({
            "status": "no_face",
            "message": "No face detected — centre your face and try again"
        })

    try:
        match, dist = await find_match(embedding)
    except Exception as e:
        raise KioskError(
            "Database search failed.",
            "தரவுத்தள தேடல் தோல்வியடைந்தது.",
            status_code=500
        )

    if match:
        conn = get_db()
        conn.execute(
            "UPDATE patients SET visit_count = visit_count + 1 WHERE id = ?",
            (match["id"],)
        )
        conn.commit()
        conn.close()
        return {
            "status": "found",
            "id": match["id"],
            "name": match["name"],
            "gender": match["gender"] or "Unknown",
            "age": match["age"],
            "visits": match["visit_count"] + 1,
            "distance": round(dist, 4),
        }

    gender = await detect_gender_async(img)
    emb_b64 = base64.b64encode(pickle.dumps(embedding)).decode()
    return {
        "status": "new",
        "gender": gender,
        "embedding": emb_b64,
    }

@router.post("/register")
async def register(patient: PatientRegister):
    try:
        emb_bytes = base64.b64decode(patient.embedding) if patient.embedding else None
        conn = get_db()
        cur = conn.execute(
            "INSERT INTO patients (name, gender, age, phone, blood_group, city, embedding) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (patient.name, patient.gender, patient.age, patient.phone, patient.blood_group, patient.city, emb_bytes)
        )
        new_id = cur.lastrowid
        conn.commit()
        conn.close()
        return {"status": "registered", "id": new_id, "name": patient.name, "gender": patient.gender}
    except Exception as e:
        raise KioskError(
            "Registration failed. Please try again.",
            "பதிவு தோல்வியடைந்தது. மீண்டும் முயற்சிக்கவும்.",
            status_code=500
        )

@router.get("/patients", response_model=List[PatientRead])
async def list_patients():
    conn = get_db()
    rows = conn.execute(
        "SELECT id, name, gender, age, visit_count, created_at FROM patients ORDER BY id DESC"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]

@router.delete("/patients/{pid}")
async def delete_patient(pid: int):
    conn = get_db()
    conn.execute("DELETE FROM patients WHERE id = ?", (pid,))
    conn.commit()
    conn.close()
    return {"status": "deleted", "id": pid}
