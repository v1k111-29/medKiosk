"""
Hospital Kiosk — FastAPI backend.

Entry point: uvicorn app.main:app --host 0.0.0.0 --port 8000
(single worker: the realtime hub is in-process — see app/services/realtime.py)

Features:
- Face recognition (ArcFace via DeepFace, loaded lazily)
- Voice transcription (Groq Whisper)
- Conversational registration & triage (Groq LLM)
- Medical vitals, sequential department tokens, staff queue, display board, websockets
"""

import asyncio
import importlib.util
import logging
import re
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import func, select

from app.core.config import settings
from app.core.database import run_migrations, session_scope
from app.core.errors import KioskError, global_exception_handler, kiosk_exception_handler
from app.core.models import Patient
from app.core.seed import seed_all
from app.routers import (
    admin,
    appointment,
    auth,
    conversation,
    departments,
    display,
    doctors,
    face,
    medical,
    queue,
    tts,
    voice,
    ws,
)
from app.services import groq_client, otp_service
from app.services.realtime import hub

APP_VERSION = "3.0.0"

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%H:%M:%S",
    stream=sys.stdout,
)
logger = logging.getLogger("kiosk")

for lib in ("deepface", "tensorflow", "absl", "httpx", "httpcore", "alembic.runtime.plugins"):
    logging.getLogger(lib).setLevel(logging.WARNING)


_TOKEN_QS = re.compile(r"((?:^|[?&])(?:token|access_token)=)[^&\s\"]*", re.IGNORECASE)


def redact_tokens(text: str) -> str:
    """Replace `token=` / `access_token=` query-string values with [REDACTED]."""
    return _TOKEN_QS.sub(r"\1[REDACTED]", text)


class RedactTokenFilter(logging.Filter):
    """Keeps JWTs out of logs.

    The staff WebSocket (`/ws/queue?token=<JWT>`) carries the token in the query string,
    and uvicorn logs the full path in its access log ("uvicorn.access") and in its
    WebSocket accept/reject lines ("uvicorn.error").
    """

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str) and "token=" in record.msg.lower():
            record.msg = redact_tokens(record.msg)
        if record.args:
            if isinstance(record.args, tuple):
                record.args = tuple(redact_tokens(a) if isinstance(a, str) else a for a in record.args)
            elif isinstance(record.args, dict):
                record.args = {k: redact_tokens(v) if isinstance(v, str) else v for k, v in record.args.items()}
        return True


_redact_filter = RedactTokenFilter()
for _name in ("uvicorn.access", "uvicorn.error", "uvicorn"):
    _lg = logging.getLogger(_name)
    if not any(isinstance(f, RedactTokenFilter) for f in _lg.filters):
        _lg.addFilter(_redact_filter)


def _deepface_installed() -> bool:
    return importlib.util.find_spec("deepface") is not None


def _warm_arcface() -> None:
    import numpy as np

    from app.services.face_service import get_df

    get_df().represent(
        img_path=np.zeros((112, 112, 3), dtype=np.uint8),
        model_name="ArcFace",
        detector_backend="skip",
        enforce_detection=False,
    )


def _startup_db() -> None:
    run_migrations()
    with session_scope() as session:
        seed_all(session)
    with session_scope() as session:
        purged = otp_service.purge_expired(session)
        if purged:
            logger.info("[DB] Purged %d expired phone OTP row(s)", purged)


# ── Lifespan (startup/shutdown) ───────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Hospital Kiosk %s starting (ENV=%s)", APP_VERSION, settings.ENV)

    # 1. Configuration (fails fast on unsafe prod config)
    settings.validate_for_startup()

    # 2. Database: Alembic migrations + idempotent seed
    await run_in_threadpool(_startup_db)

    # 3. Realtime hub + shared Groq HTTP client
    hub.bind_loop(asyncio.get_running_loop())
    await groq_client.open_client()

    # 4. Face recognition warm-up (optional dependency)
    if _deepface_installed():
        try:
            logger.info("[AI] Warming up ArcFace model...")
            await run_in_threadpool(_warm_arcface)
            logger.info("[AI] ArcFace model ready")
        except Exception as e:
            logger.warning("[AI] ArcFace warmup failed: %s", e)
    else:
        logger.warning("[AI] deepface not installed — /identify will fail; other routes work")

    # 5. Groq availability
    from app.services.llm_service import check_groq_health

    if not groq_client.is_configured():
        logger.warning("[AI] GROQ_API_KEY not set — transcription and conversational AI unavailable")
    else:
        health = await check_groq_health()
        if health["ok"]:
            logger.info("[AI] Groq ready (chat=%s, triage=%s, whisper=%s)",
                        settings.GROQ_MODEL, settings.GROQ_TRIAGE_MODEL, settings.GROQ_WHISPER_MODEL)
        else:
            logger.warning("[AI] Groq not reachable: %s", health.get("error"))

    logger.info("Server ready")
    yield

    await groq_client.close_client()
    logger.info("Hospital Kiosk shutting down.")


# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(title="Hospital Kiosk API", version=APP_VERSION, lifespan=lifespan)

app.add_exception_handler(KioskError, kiosk_exception_handler)
app.add_exception_handler(Exception, global_exception_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

for r in (face, voice, medical, conversation, appointment, doctors, departments,
          auth, admin, queue, display, ws, tts):
    app.include_router(r.router)


# ── Health Check ──────────────────────────────────────────────────────────────
@app.get("/health")
async def health():
    from app.services.llm_service import check_groq_health
    from app.services.voice_service import is_whisper_available

    def _db_check():
        with session_scope() as session:
            return session.scalar(select(func.count()).select_from(Patient))

    db_ok, patient_count = True, 0
    try:
        patient_count = await run_in_threadpool(_db_check)
    except Exception:
        db_ok = False

    llm_ok = (await check_groq_health())["ok"] if groq_client.is_configured() else False

    return {
        "status": "ok" if db_ok else "degraded",
        "version": APP_VERSION,
        "env": settings.ENV,
        "services": {
            "database": {"ok": db_ok, "patients": patient_count},
            "face_recognition": _deepface_installed(),
            "whisper": is_whisper_available(),
            "llm": llm_ok,
            "realtime": {"staff": hub.count("staff"), "display": hub.count("display")},
        },
        "plugins": ["face", "voice", "medical", "conversation", "queue", "display"],
    }


# ── Static Files / SPA ───────────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent.parent.resolve()
STATIC_DIR = BASE_DIR / "static"

if STATIC_DIR.exists():
    assets_dir = STATIC_DIR / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        """Serve the React SPA with client-side routing support."""
        file_path = (STATIC_DIR / full_path).resolve()
        if file_path.is_file() and STATIC_DIR in file_path.parents:
            return FileResponse(file_path)
        index_file = STATIC_DIR / "index.html"
        if index_file.exists():
            return HTMLResponse(content=index_file.read_text(encoding="utf-8"))
        return HTMLResponse(
            content="<h1>Frontend not found. Run: cd frontend && npm run build</h1>",
            status_code=404,
        )
