"""
Hospital Kiosk — FastAPI backend v2
Face recognition + gender + voice registration + vitals
Windows + Linux compatible
"""

import os, io, logging, sqlite3, pickle, base64
from pathlib import Path

os.environ["TF_CPP_MIN_LOG_LEVEL"]  = "3"
os.environ["TF_ENABLE_ONEDNN_OPTS"] = "0"
os.environ["ABSL_MIN_LOG_LEVEL"]    = "3"
logging.getLogger("deepface").setLevel(logging.ERROR)
logging.getLogger("tensorflow").setLevel(logging.ERROR)
logging.getLogger("absl").setLevel(logging.ERROR)

import numpy as np
from PIL import Image
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import uvicorn

BASE_DIR = Path(__file__).parent.resolve()
DB_PATH  = BASE_DIR / "patients.db"
STATIC   = BASE_DIR / "static"

# ── lazy DeepFace ─────────────────────────────────────────────────────────────
_df = None
def df():
    global _df
    if _df is None:
        from deepface import DeepFace as _d
        _df = _d
    return _df

# ── lifespan warmup ───────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    print("[Kiosk] Warming up ArcFace model…")
    try:
        dummy = np.zeros((112,112,3), dtype=np.uint8)
        df().represent(img_path=dummy, model_name="ArcFace",
                       detector_backend="skip", enforce_detection=False)
        print("[Kiosk] ✅ Model ready — open http://localhost:8000")
    except Exception as e:
        print(f"[Kiosk] Warmup note: {e}")
    yield
    print("[Kiosk] Shutting down.")

app = FastAPI(title="Hospital Kiosk API", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"],
                   allow_methods=["*"], allow_headers=["*"])
if STATIC.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC)), name="static")

# ── DB init ───────────────────────────────────────────────────────────────────
def get_db():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS patients (
            id           INTEGER  PRIMARY KEY AUTOINCREMENT,
            name         TEXT     NOT NULL,
            gender       TEXT,
            age          INTEGER,
            phone        TEXT,
            blood_group  TEXT,
            city         TEXT,
            embedding    BLOB     NOT NULL,
            created_at   DATETIME DEFAULT CURRENT_TIMESTAMP,
            visit_count  INTEGER  DEFAULT 1
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS vitals (
            id           INTEGER  PRIMARY KEY AUTOINCREMENT,
            patient_id   INTEGER  NOT NULL REFERENCES patients(id),
            height       INTEGER,
            weight       INTEGER,
            bp_sys       INTEGER,
            bp_dia       INTEGER,
            spo2         INTEGER,
            diabetes     INTEGER  DEFAULT 0,
            hypertension INTEGER  DEFAULT 0,
            recorded_at  DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()
    print(f"[DB]  Persistent database → {DB_PATH}")

init_db()

# ── helpers ───────────────────────────────────────────────────────────────────
def decode_image(data_url: str) -> np.ndarray:
    _, encoded = data_url.split(",", 1)
    img = Image.open(io.BytesIO(base64.b64decode(encoded))).convert("RGB")
    return np.array(img)

def get_embedding(img: np.ndarray):
    try:
        r = df().represent(img_path=img, model_name="ArcFace",
                           detector_backend="opencv", enforce_detection=True)
        return np.array(r[0]["embedding"], dtype=np.float32)
    except Exception as e:
        print(f"[Embed] {e}")
        return None

def cosine_dist(a, b):
    a = a / (np.linalg.norm(a) + 1e-9)
    b = b / (np.linalg.norm(b) + 1e-9)
    return float(1.0 - np.dot(a, b))

def find_match(embedding, threshold=0.40):
    conn = get_db()
    rows = conn.execute(
        "SELECT id,name,gender,age,phone,embedding,visit_count FROM patients"
    ).fetchall()
    conn.close()
    best_dist, best_row = 1.0, None
    for row in rows:
        d = cosine_dist(embedding, pickle.loads(row["embedding"]))
        if d < best_dist:
            best_dist, best_row = d, row
    if best_dist <= threshold and best_row:
        return dict(best_row), best_dist
    return None, best_dist

def detect_gender(img: np.ndarray) -> str:
    try:
        r = df().analyze(img_path=img, actions=["gender"],
                         detector_backend="opencv", enforce_detection=True, silent=True)
        s = r[0]["gender"]
        return "Man" if s["Man"] >= s["Woman"] else "Woman"
    except:
        return "Unknown"

# ── routes ────────────────────────────────────────────────────────────────────
@app.get("/", response_class=HTMLResponse)
async def serve_ui():
    html = (BASE_DIR / "static" / "index.html").read_text(encoding="utf-8")
    return HTMLResponse(content=html)

@app.get("/health")
async def health():
    conn = get_db()
    count = conn.execute("SELECT COUNT(*) FROM patients").fetchone()[0]
    conn.close()
    return {"status": "ok", "patients": count}

@app.post("/identify")
async def identify(payload: dict):
    image_data = payload.get("image")
    if not image_data:
        raise HTTPException(400, "No image")
    try:
        img = decode_image(image_data)
    except:
        raise HTTPException(400, "Invalid image")

    embedding = get_embedding(img)
    if embedding is None:
        return {"status": "no_face", "message": "No face detected — centre your face and try again"}

    match, dist = find_match(embedding)
    if match:
        conn = get_db()
        conn.execute("UPDATE patients SET visit_count=visit_count+1 WHERE id=?", (match["id"],))
        conn.commit()
        conn.close()
        return {
            "status":   "found",
            "id":       match["id"],
            "name":     match["name"],
            "gender":   match["gender"] or "Unknown",
            "age":      match["age"],
            "phone":    match["phone"],
            "visits":   match["visit_count"] + 1,
            "distance": round(dist, 4),
        }

    gender  = detect_gender(img)
    emb_b64 = base64.b64encode(pickle.dumps(embedding)).decode()
    return {"status": "new", "gender": gender, "embedding": emb_b64}

@app.post("/register")
async def register(payload: dict):
    name    = (payload.get("name") or "").strip()
    gender  = payload.get("gender", "Unknown")
    age     = payload.get("age")
    phone   = payload.get("phone", "")
    blood   = payload.get("blood_group", "")
    city    = payload.get("city", "")
    emb_b64 = payload.get("embedding")

    if not name:
        raise HTTPException(400, "Name required")
    if not emb_b64:
        raise HTTPException(400, "Embedding missing — please scan again")

    emb_bytes = base64.b64decode(emb_b64)
    conn = get_db()
    cur  = conn.execute(
        "INSERT INTO patients (name,gender,age,phone,blood_group,city,embedding) VALUES (?,?,?,?,?,?,?)",
        (name, gender, age, phone, blood, city, emb_bytes)
    )
    new_id = cur.lastrowid
    conn.commit()
    conn.close()
    return {"status": "registered", "id": new_id, "name": name, "gender": gender}

@app.post("/vitals")
async def save_vitals(payload: dict):
    pid = payload.get("patient_id")
    if not pid:
        raise HTTPException(400, "patient_id required")
    conn = get_db()
    conn.execute("""
        INSERT INTO vitals (patient_id,height,weight,bp_sys,bp_dia,spo2,diabetes,hypertension)
        VALUES (?,?,?,?,?,?,?,?)
    """, (
        pid,
        payload.get("height"),
        payload.get("weight"),
        payload.get("bp_sys"),
        payload.get("bp_dia"),
        payload.get("spo2"),
        int(bool(payload.get("diabetes"))),
        int(bool(payload.get("hypertension"))),
    ))
    conn.commit()
    conn.close()
    return {"status": "saved"}

@app.get("/patients")
async def list_patients():
    conn = get_db()
    rows = conn.execute(
        "SELECT id,name,gender,age,phone,visit_count,created_at FROM patients ORDER BY id DESC"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]

@app.delete("/patients/{pid}")
async def delete_patient(pid: int):
    conn = get_db()
    conn.execute("DELETE FROM vitals  WHERE patient_id=?", (pid,))
    conn.execute("DELETE FROM patients WHERE id=?", (pid,))
    conn.commit()
    conn.close()
    return {"status": "deleted", "id": pid}

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)
