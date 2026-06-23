"""
Voice Service — Groq Whisper API for fast cloud transcription (~0.5-1s).
Replaces local openai-whisper model inference.

Set GROQ_API_KEY environment variable before starting.
Get a free key at: https://console.groq.com

Supported audio: webm, ogg, mp4/m4a, mp3, wav (browser MediaRecorder formats)
Groq Whisper endpoint: POST https://api.groq.com/openai/v1/audio/transcriptions

# ─── OLD LOCAL WHISPER CODE (commented out) ─────────────────────────────────
# import whisper
# from concurrent.futures import ThreadPoolExecutor
# executor = ThreadPoolExecutor(max_workers=1)
# WHISPER_MODEL = os.getenv("WHISPER_MODEL", "base")
#
# _model = None
# _whisper_available = None
#
# def is_whisper_available() -> bool:
#     global _whisper_available
#     if _whisper_available is None:
#         try:
#             import whisper; _whisper_available = True
#         except ImportError:
#             _whisper_available = False
#     return _whisper_available
#
# def get_model():
#     global _model
#     if _model is None:
#         import whisper
#         _model = whisper.load_model(WHISPER_MODEL)
#     return _model
#
# async def transcribe_async(audio_path, language="auto"):
#     loop = asyncio.get_running_loop()
#     lang_arg = None if language in (None, "", "auto") else language
#     def _task():
#         kwargs = dict(fp16=False)
#         if lang_arg:
#             kwargs["language"] = lang_arg
#         return get_model().transcribe(audio_path, **kwargs)
#     return await loop.run_in_executor(executor, _task)
# ────────────────────────────────────────────────────────────────────────────
"""

import os
import logging
import httpx

logger = logging.getLogger("kiosk.voice")

# ── Groq Whisper Configuration ─────────────────────────────────────────────────
GROQ_API_KEY        = os.getenv("GROQ_API_KEY", "")
GROQ_WHISPER_URL    = "https://api.groq.com/openai/v1/audio/transcriptions"
# whisper-large-v3-turbo: best quality/speed balance on Groq
# whisper-large-v3: highest accuracy (slightly slower)
GROQ_WHISPER_MODEL  = os.getenv("GROQ_WHISPER_MODEL", "whisper-large-v3-turbo")
GROQ_WHISPER_TIMEOUT = float(os.getenv("GROQ_WHISPER_TIMEOUT", "30"))


def is_whisper_available() -> bool:
    """
    With Groq, Whisper is always 'available' as long as the API key is set.
    Returns True if GROQ_API_KEY is configured.
    """
    if not GROQ_API_KEY:
        logger.warning(
            "[Voice] GROQ_API_KEY not set — voice transcription unavailable. "
            "Get a free key at https://console.groq.com"
        )
        return False
    return True


def get_model():
    """
    Compatibility stub — local Whisper model loading is no longer used.
    Groq handles inference in the cloud; nothing to load locally.
    """
    if not GROQ_API_KEY:
        raise RuntimeError(
            "GROQ_API_KEY is not set. "
            "Get a free key at https://console.groq.com and set it as an environment variable."
        )
    logger.info(f"[Voice] Using Groq Whisper API (model: {GROQ_WHISPER_MODEL})")
    return True  # Nothing to load locally


async def transcribe_async(
    audio_path: str,
    language: str = "auto",
) -> dict:
    """
    Transcribe audio using Groq's Whisper API.

    Args:
        audio_path: Path to the audio file (webm, ogg, mp4, wav, mp3)
        language:
            - "en"   -> force English decoding
            - "ta"   -> force Tamil decoding
            - "auto" -> let Whisper auto-detect language (default)

    Returns:
        dict with "text" and "language" keys
    """
    if not GROQ_API_KEY:
        raise RuntimeError(
            "GROQ_API_KEY is not set. "
            "Get a free key at https://console.groq.com"
        )

    # Read file
    try:
        with open(audio_path, "rb") as f:
            audio_bytes = f.read()
    except OSError as e:
        raise RuntimeError(f"Could not read audio file: {e}")

    # Detect filename extension for Content-Type
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

    # Build multipart form
    form_data = {
        "model":            (None, GROQ_WHISPER_MODEL),
        "response_format":  (None, "verbose_json"),
        "prompt":           (None, _build_whisper_prompt(language)),
        "temperature":      (None, "0.0"),  # Crucial to prevent hallucinations on silence
    }

    # Language: pass explicitly if not auto-detect
    lang_arg = None if language in (None, "", "auto") else language
    if lang_arg:
        form_data["language"] = (None, lang_arg)

    form_data["file"] = (filename, audio_bytes, mime_type)
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}"}

    try:
        async with httpx.AsyncClient(timeout=GROQ_WHISPER_TIMEOUT) as client:
            response = await client.post(
                GROQ_WHISPER_URL,
                headers=headers,
                files=form_data,
            )
            response.raise_for_status()
            data = response.json()

            text     = data.get("text", "").strip()
            detected = data.get("language", language or "unknown")
            
            # Filter out known Whisper hallucinations
            lower_text = text.lower()
            hallucinations = [
                "indian english", "amara.org", "thank you", "thanks for watching",
                "bye", "subtitle", "translated", "hospital registration",
                "patsy is speaking", "patient is speaking", 
                "i'm not sure what i'm saying", "i am a little", 
                "why should i accept it", "e.", "say what is", "wx."
            ]
            
            # If the text is just a common hallucination or prompt repetition, ignore it
            is_hallucination = any(h in lower_text for h in hallucinations) and len(text.split()) <= 6
            if is_hallucination or not text:
                logger.info("[Voice] Ignored hallucination or silence. Returning '.'")
                return {"text": ".", "language": detected}

            logger.info(
                f"[Voice] Groq transcribed ({detected}): "
                f"'{text[:80]}{'...' if len(text) > 80 else ''}'"
            )
            return {"text": text, "language": detected}

    except httpx.TimeoutException:
        raise RuntimeError(
            f"Groq Whisper timed out after {GROQ_WHISPER_TIMEOUT}s. "
            "Check your internet connection."
        )
    except httpx.HTTPStatusError as e:
        status = e.response.status_code
        body   = e.response.text[:300]
        if status == 400:
            # Groq returns 400 when audio is too short or unreadable
            raise RuntimeError(
                "Recording was too short or the audio couldn't be read. "
                "Please hold the button longer and speak clearly."
            )
        elif status == 401:
            raise RuntimeError(
                "Groq API key is invalid. Check your GROQ_API_KEY environment variable."
            )
        elif status == 413:
            raise RuntimeError(
                "Audio file too large for Groq Whisper. "
                "Maximum file size is 25MB."
            )
        elif status == 429:
            raise RuntimeError(
                "Groq rate limit hit. Please wait a moment and try again."
            )
        else:
            raise RuntimeError(f"Groq Whisper API error {status}: {body}")
    except Exception as e:
        raise RuntimeError(f"Transcription failed: {e}")


def _build_whisper_prompt(language: str) -> str:
    """
    Build a Whisper prompt hint to improve accuracy for this kiosk's use case.
    Keep it minimal to avoid Whisper repeating it on silence.
    """
    # Providing a list of cities biases Whisper's language model to correctly spell 
    # and recognize Tamil locations even if spoken with different accents.
    cities = "Chennai, Coimbatore, Madurai, Trichy, Salem, Tirunelveli, Erode, Vellore, Thoothukudi, Dindigul, Thanjavur, Kanchipuram, Karur, Ooty, Hosur, Nagercoil."
    
    if language == "ta":
        return f"Tamil and English medical context. Cities: {cities}. Return a single period '.' when no voice is heard."
    elif language == "en":
        return f"Medical context. Cities: {cities}. Return a single period '.' when no voice is heard."
    else:
        return f"Medical context. Cities: {cities}. Return a single period '.' when no voice is heard."
    