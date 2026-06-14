from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from contextlib import asynccontextmanager
from pathlib import Path

from app.core.database import init_db
from app.routers import face, voice, medical
from app.core.errors import KioskError, kiosk_exception_handler, global_exception_handler

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize DB
    init_db()
    # Pre-warm AI models if needed
    from app.services.face_service import get_df
    import numpy as np
    print("[Kiosk] Warming up AI models...")
    dummy = np.zeros((112, 112, 3), dtype=np.uint8)
    get_df().represent(dummy, model_name="ArcFace", detector_backend="skip", enforce_detection=False)
    print("[Kiosk] AI Warm-up Complete.")
    yield

app = FastAPI(title="Hospital Kiosk Unified API", lifespan=lifespan)

# Register Exception Handlers
app.add_exception_handler(KioskError, kiosk_exception_handler)
app.add_exception_handler(Exception, global_exception_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Routers (The "Plugins")
app.include_router(face.router)
app.include_router(voice.router)
app.include_router(medical.router)

@app.get("/health")
async def health():
    return {"status": "ok", "version": "1.1.0", "plugins": ["face", "voice", "medical"]}

# Static Files
BASE_DIR = Path(__file__).parent.parent.resolve()
STATIC_DIR = BASE_DIR / "static"

if STATIC_DIR.exists():
    app.mount("/assets", StaticFiles(directory=STATIC_DIR / "assets"), name="assets")

    @app.get("/", response_class=HTMLResponse)
    async def serve_index():
        return (STATIC_DIR / "index.html").read_text(encoding="utf-8")
