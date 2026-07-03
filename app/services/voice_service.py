import os
import logging
import httpx

logger = logging.getLogger("kiosk.voice")

# ── Sarvam AI Configuration ──────────────────────────────────────────────────
def _get_sarvam_api_key() -> str:
    """Read SARVAM_API_KEY at call time so runtime env changes are picked up."""
    return os.getenv("SARVAM_API_KEY", "")

SARVAM_STT_URL = "https://api.sarvam.ai/speech-to-text"
SARVAM_TIMEOUT = float(os.getenv("SARVAM_TIMEOUT", "30"))

_availability_warned = False

def is_whisper_available() -> bool:
    """
    Returns True if SARVAM_API_KEY is configured. 
    (Function name kept as is_whisper_available for compatibility with other modules).
    """
    global _availability_warned
    if not _get_sarvam_api_key():
        if not _availability_warned:
            logger.warning(
                "[Voice] SARVAM_API_KEY not set — voice transcription unavailable. "
                "Get a key from Sarvam AI dashboard."
            )
            _availability_warned = True
        return False
    _availability_warned = False
    return True

def get_model():
    raise NotImplementedError("Local model is not used. Use transcribe_async() with the Sarvam API instead.")

async def transcribe_async(
    audio_path: str,
    language: str = "auto",
) -> dict:
    """
    Transcribe audio using Sarvam AI's Speech-to-Text API.
    """
    if not _get_sarvam_api_key():
        raise RuntimeError("SARVAM_API_KEY is not set.")

    # Read file
    try:
        with open(audio_path, "rb") as f:
            audio_bytes = f.read()
    except OSError as e:
        raise RuntimeError(f"Could not read audio file: {e}")

    ext = os.path.splitext(audio_path)[1].lower().lstrip(".")
    mime_map = {
        "webm": "audio/webm",
        "ogg":  "audio/ogg",
        "mp4":  "audio/mp4",
        "m4a":  "audio/mp4",
        "mp3":  "audio/mpeg",
        "wav":  "audio/wav",
        "aac":  "audio/aac",
        "flac": "audio/flac",
    }
    mime_type = mime_map.get(ext, "audio/webm")
    filename  = f"recording.{ext or 'webm'}"

    # Sarvam requires model="saaras:v3"
    data_payload = {"model": "saaras:v3"}
    files_payload = {"file": (filename, audio_bytes, mime_type)}

    headers = {"api-subscription-key": _get_sarvam_api_key()}

    try:
        async with httpx.AsyncClient(timeout=SARVAM_TIMEOUT) as client:
            response = await client.post(
                SARVAM_STT_URL,
                headers=headers,
                data=data_payload,
                files=files_payload,
            )
            response.raise_for_status()
            data = response.json()

            # Fallback across possible Sarvam response structures
            text = data.get("transcript") or data.get("text") or ""
            text = text.strip()

            if not text:
                logger.info("[Voice] No speech / silence detected — returning empty text.")
                return {"text": "", "language": "unknown"}

            logger.info(
                f"[Voice] Sarvam transcribed: "
                f"'{text[:80]}{'...' if len(text) > 80 else ''}'"
            )
            return {"text": text, "language": "unknown"}

    except httpx.TimeoutException:
        raise RuntimeError(f"Sarvam AI timed out after {SARVAM_TIMEOUT}s.")
    except httpx.HTTPStatusError as e:
        status = e.response.status_code
        body   = e.response.text[:300]
        if status == 401:
            raise RuntimeError("Sarvam API key is invalid.")
        else:
            raise RuntimeError(f"Sarvam AI API error {status}: {body}")
    except Exception as e:
        raise RuntimeError(f"Transcription failed: {e}")
