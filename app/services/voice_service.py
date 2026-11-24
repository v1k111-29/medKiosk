"""
Voice Service — Groq Whisper API for fast cloud transcription (~0.5-1s).
Replaces local openai-whisper model inference.

Set GROQ_API_KEY environment variable before starting.
Get a free key at: https://console.groq.com

Supported audio: webm, ogg, mp4/m4a, mp3, wav (browser MediaRecorder formats)
Groq Whisper endpoint: POST https://api.groq.com/openai/v1/audio/transcriptions
"""

import logging
import os

import httpx

from app.core.config import settings
from app.services import groq_client

logger = logging.getLogger("kiosk.voice")


def is_whisper_available() -> bool:
    """Whisper is available whenever GROQ_API_KEY is configured."""
    return groq_client.is_configured()


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
    if not groq_client.is_configured():
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
        "model":            (None, settings.GROQ_WHISPER_MODEL),
        "response_format":  (None, "verbose_json"),
        "prompt":           (None, _build_whisper_prompt(language)),
        "temperature":      (None, "0.0"),  # Crucial to prevent hallucinations on silence
    }

    # Language: pass explicitly if not auto-detect
    lang_arg = None if language in (None, "", "auto") else language
    if lang_arg:
        form_data["language"] = (None, lang_arg)

    form_data["file"] = (filename, audio_bytes, mime_type)
    try:
        client = await groq_client.get_client()
        response = await client.post(
            groq_client.GROQ_WHISPER_URL,
            headers=groq_client.auth_headers(),
            files=form_data,
            timeout=settings.GROQ_WHISPER_TIMEOUT,
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

        logger.info("[Voice] Groq transcribed lang=%s chars=%d", detected, len(text))
        return {"text": text, "language": detected}

    except httpx.TimeoutException:
        raise RuntimeError(
            f"Groq Whisper timed out after {settings.GROQ_WHISPER_TIMEOUT}s. "
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
    except RuntimeError:
        raise
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
