"""
Voice Transcription Router — audio upload via Groq Whisper API.

No local ffmpeg required — Groq handles all audio decoding in the cloud.
Supports: webm, ogg, mp4/m4a, mp3, wav (all browser MediaRecorder formats).
"""

from fastapi import APIRouter, File, UploadFile, Form
import tempfile
import os
import logging

from app.services.voice_service import (
    transcribe_async,
    is_whisper_available,
    GROQ_WHISPER_MODEL,
)
from app.core.errors import KioskError

logger = logging.getLogger("kiosk.voice")

router = APIRouter(tags=["Voice Transcription"])

MIME_TO_EXT = {
    "audio/webm":              ".webm",
    "audio/webm;codecs=opus":  ".webm",
    "audio/ogg":               ".ogg",
    "audio/ogg;codecs=opus":   ".ogg",
    "audio/mp4":               ".mp4",
    "audio/mp4;codecs=mp4a.40.2": ".mp4",
    "audio/aac":               ".aac",
    "audio/mpeg":              ".mp3",
    "audio/wav":               ".wav",
    "audio/x-wav":             ".wav",
}

# Groq Whisper max file size: 25 MB
MAX_AUDIO_BYTES = 25 * 1024 * 1024


@router.get("/transcribe/health")
async def transcribe_health():
    """
    Diagnostic endpoint — check Groq Whisper availability.
    No ffmpeg check needed: Groq decodes audio in the cloud.
    """
    api_key_set = bool(os.getenv("GROQ_API_KEY", ""))
    groq_ok = is_whisper_available()

    return {
        "provider":            "Groq Whisper API",
        "model":               GROQ_WHISPER_MODEL,
        "api_key_configured":  api_key_set,
        "ready":               groq_ok,
        "ffmpeg_required":     False,
        "note": (
            "Set GROQ_API_KEY env var to enable transcription. "
            "Free key: https://console.groq.com"
            if not api_key_set
            else "Groq Whisper is ready."
        ),
    }


@router.post("/transcribe")
async def transcribe(
    audio: UploadFile = File(...),
    language: str = Form("auto"),
):
    """
    Transcribe audio via Groq Whisper API.

    `language`:
      - "en"   -> force English
      - "ta"   -> force Tamil
      - "auto" -> auto-detect (default; works well for mixed speech)

    Audio formats accepted: webm, ogg, mp4/m4a, mp3, wav, aac
    Max size: 25MB
    """
    logger.info(
        f"/transcribe — file={audio.filename!r}, "
        f"type={audio.content_type!r}, lang={language!r}"
    )

    # ── Pre-checks ──────────────────────────────────────────────────────────
    if not is_whisper_available():
        raise KioskError(
            "Voice transcription is unavailable: GROQ_API_KEY is not set. "
            "Get a free key at https://console.groq.com",
            "குரல் சேவை கிடைக்கவில்லை. GROQ_API_KEY அமைக்கப்படவில்லை.",
            status_code=503,
        )

    raw = await audio.read()

    if not raw:
        raise KioskError(
            "No audio received. Please check your microphone and try again.",
            "ஒலி பெறப்படவில்லை. மைக்ரோஃபோனை சரிபார்க்கவும்.",
            status_code=400,
        )

    if len(raw) < 1500:
        raise KioskError(
            "Recording was too short. Hold the button and speak a full sentence.",
            "பதிவு மிகக் குறுகியதாக இருந்தது. கொஞ்சம் நேரம் பேசவும்.",
            status_code=400,
        )

    if len(raw) > MAX_AUDIO_BYTES:
        raise KioskError(
            f"Audio file too large ({len(raw) // 1024}KB). Maximum is 25MB.",
            "ஒலி கோப்பு மிகவும் பெரியது.",
            status_code=413,
        )

    # ── Detect extension from MIME ───────────────────────────────────────────
    content_type = (audio.content_type or "audio/webm")
    content_type_base = content_type.split(";")[0].strip()
    ext = MIME_TO_EXT.get(content_type, MIME_TO_EXT.get(content_type_base, ".webm"))

    # ── Write to temp file and transcribe ────────────────────────────────────
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
            tmp.write(raw)
            tmp_path = tmp.name

        result = await transcribe_async(tmp_path, language=language)
        text = (result.get("text") or "").strip()

        if not text:
            raise KioskError(
                "No speech detected. Please speak clearly and try again.",
                "பேச்சு கண்டறியப்படவில்லை. தெளிவாகப் பேசவும்.",
                status_code=422,
            )

        return {
            "transcription": text,
            "status": "success",
            "language": result.get("language", "unknown"),
            "provider": "groq",
        }

    except KioskError:
        raise
    except RuntimeError as e:
        msg = str(e)
        logger.error(f"[Voice] Transcription error: {msg}")
        # Map "too short" errors to 400 so frontend shows a retry hint
        status_code = 400 if "too short" in msg.lower() or "couldn't be read" in msg.lower() else 500
        raise KioskError(
            msg,
            "பதிவு மிகக் குறுகியதாக இருந்தது. கொஞ்சம் நேரம் பேசவும்." if status_code == 400
            else "குரல் செயலாக்கம் தோல்வியடைந்தது. மீண்டும் முயற்சிக்கவும்.",
            status_code=status_code,
        )
    except Exception as e:
        import traceback
        logger.error(f"[Voice] Unexpected error: {e}")
        traceback.print_exc()
        raise KioskError(
            "Voice processing failed. Please try again.",
            "குரல் செயலாக்கம் தோல்வியடைந்தது.",
            status_code=500,
        )
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)
