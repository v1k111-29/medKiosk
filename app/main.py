"""
Hospital Kiosk — FastAPI unified backend.

Entry point: uvicorn app.main:app --host 0.0.0.0 --port 8000

Features:
- Face recognition (ArcFace via DeepFace)
- Voice transcription (Whisper)
- Conversational AI registration & triage (Ollama)
- Medical vitals recording
"""

import logging
import sys
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse

from app.core.database import init_db, seed_doctors
from app.routers import face, voice, medical, conversation
from app.core.errors import KioskError, kiosk_exception_handler, global_exception_handler

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%H:%M:%S",
    stream=sys.stdout,
)
logger = logging.getLogger("kiosk")

# Suppress noisy libraries
for lib in ("deepface", "tensorflow", "absl", "httpx"):
    logging.getLogger(lib).setLevel(logging.WARNING)


# ── Lifespan (startup/shutdown) ───────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown."""
    logger.info("=" * 50)
    logger.info("  Hospital Kiosk — Starting Up")
    logger.info("=" * 50)

    # 1. Initialize database
    init_db()
    seed_doctors()

    # 2. Pre-warm face recognition model
    try:
        import numpy as np
        from app.services.face_service import get_df
        logger.info("[AI] Warming up ArcFace model...")
        dummy = np.zeros((112, 112, 3), dtype=np.uint8)
        get_df().represent(
            img_path=dummy,
            model_name="ArcFace",
            detector_backend="skip",
            enforce_detection=False,
        )
        logger.info("[AI] [OK] ArcFace model ready")
    except Exception as e:
        logger.warning(f"[AI] ArcFace warmup note: {e}")

    # 3. Check Groq Whisper availability (cloud API — no model to load)
    from app.services.voice_service import is_whisper_available, GROQ_WHISPER_MODEL
    if is_whisper_available():
        logger.info(f"[AI] [OK] Groq Whisper ready (model: {GROQ_WHISPER_MODEL})")
    else:
        logger.warning(
            "[AI] [WARN] GROQ_API_KEY not set -- voice transcription unavailable. "
            "Get a free key at https://console.groq.com and set GROQ_API_KEY env var."
        )

    # 4. Check Groq LLM availability
    from app.services.llm_service import (
        check_ollama_health, check_ollama_model, warmup_ollama, GROQ_MODEL
    )
    groq_ok = await check_ollama_health()  # alias: checks Groq API key + reachability
    if groq_ok:
        model_info = await check_ollama_model()
        if model_info["available"]:
            logger.info(f"[AI] [OK] Groq LLM ready (model: {GROQ_MODEL})")
            await warmup_ollama()  # alias: no-op for Groq (no warmup needed)
        else:
            logger.warning(
                f"[AI] [WARN] Groq not available: {model_info.get('error', 'unknown error')}"
            )
    else:
        logger.warning(
            "[AI] [WARN] Groq API unreachable -- conversational AI unavailable. "
            "Check GROQ_API_KEY at https://console.groq.com"
        )

    logger.info("=" * 50)
    logger.info("  [OK] Server ready -- http://localhost:8000")
    logger.info("=" * 50)

    yield

    logger.info("Hospital Kiosk — Shutting down.")


# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="Hospital Kiosk API",
    version="2.0.0",
    lifespan=lifespan,
)

# Exception handlers
app.add_exception_handler(KioskError, kiosk_exception_handler)
app.add_exception_handler(Exception, global_exception_handler)

# CORS — restrict in production via KIOSK_CORS_ORIGINS env var
import os
cors_origins = os.getenv("KIOSK_CORS_ORIGINS", "*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(face.router)
app.include_router(voice.router)
app.include_router(medical.router)
app.include_router(conversation.router)

from app.routers import appointment
from app.routers import doctors
app.include_router(appointment.router)
app.include_router(doctors.router)


# ── Health Check ──────────────────────────────────────────────────────────────
@app.get("/health")
async def health():
    """Comprehensive health check for all services."""
    from app.services.llm_service import check_ollama_health
    from app.services.voice_service import is_whisper_available
    from app.core.database import get_db

    # DB health
    db_ok = True
    patient_count = 0
    try:
        with get_db() as conn:
            patient_count = conn.execute("SELECT COUNT(*) FROM patients").fetchone()[0]
    except Exception:
        db_ok = False

    # Ollama health
    ollama_ok = await check_ollama_health()

    return {
        "status": "ok",
        "version": "2.0.0",
        "services": {
            "database": {"ok": db_ok, "patients": patient_count},
            "face_recognition": True,
            "whisper": is_whisper_available(),
            "ollama": ollama_ok,
        },
        "plugins": ["face", "voice", "medical", "conversation"],
    }


# ── Static Files / SPA ───────────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent.parent.resolve()
STATIC_DIR = BASE_DIR / "static"

if STATIC_DIR.exists():
    # Mount assets subdirectory
    assets_dir = STATIC_DIR / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        """Serve the React SPA with client-side routing support."""
        file_path = STATIC_DIR / full_path
        if file_path.is_file():
            return FileResponse(file_path)

        index_file = STATIC_DIR / "index.html"
        if index_file.exists():
            return HTMLResponse(content=index_file.read_text(encoding="utf-8"))

        return HTMLResponse(
            content="<h1>Frontend not found. Run: cd frontend && npm run build</h1>",
            status_code=404,
        )
