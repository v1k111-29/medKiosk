"""
Text-to-speech via Sarvam AI (bulbul), with an in-memory LRU cache.

Sarvam TTS REST API (auth header `api-subscription-key`, JSON body
text/language_code/model/speaker/output_audio_codec; response {"audios":[base64 wav]}):
  https://docs.sarvam.ai/api-reference-docs/text-to-speech/convert
Speakers are model-specific (bulbul:v3 names such as kavitha, priya).
"""

from __future__ import annotations

import base64
import hashlib
import logging
from collections import OrderedDict

from app.core.config import settings
from app.services import groq_client

logger = logging.getLogger("kiosk.tts")

SARVAM_TTS_URL = "https://api.sarvam.ai/text-to-speech"
MAX_TEXT_CHARS = 500
_LANG_CODE = {"ta": "ta-IN", "en": "en-IN"}

_cache: "OrderedDict[tuple, bytes]" = OrderedDict()


class TTSUnavailable(Exception):
    """TTS provider is disabled or the upstream call failed (-> HTTP 503)."""


def is_enabled() -> bool:
    return settings.TTS_PROVIDER == "sarvam" and settings.sarvam_configured


def provider() -> str:
    return "sarvam" if is_enabled() else "browser"


def _speaker(lang: str) -> str:
    return settings.SARVAM_TTS_SPEAKER_TA if lang == "ta" else settings.SARVAM_TTS_SPEAKER_EN


async def synthesize(text: str, lang: str) -> bytes:
    """Return WAV bytes for `text` (cached). Raises TTSUnavailable on failure."""
    if not is_enabled():
        raise TTSUnavailable("TTS provider is not sarvam")
    speaker = _speaker(lang)
    key = (lang, speaker, settings.SARVAM_TTS_MODEL, hashlib.sha256(text.encode("utf-8")).hexdigest())
    hit = _cache.get(key)
    if hit is not None:
        _cache.move_to_end(key)
        return hit

    try:
        client = await groq_client.get_client()
        resp = await client.post(
            SARVAM_TTS_URL,
            headers={"api-subscription-key": settings.SARVAM_API_KEY},
            json={
                "text": text,
                "language_code": _LANG_CODE[lang],
                "model": settings.SARVAM_TTS_MODEL,
                "speaker": speaker,
                "output_audio_codec": "wav",
            },
            timeout=settings.SARVAM_TIMEOUT,
        )
        resp.raise_for_status()
        audios = resp.json().get("audios") or []
        if not audios:
            raise ValueError("empty audios array")
        wav = base64.b64decode(audios[0])
    except Exception as e:
        logger.warning("[TTS] Sarvam request failed: %s", e)
        raise TTSUnavailable(str(e)) from e

    _cache[key] = wav
    while len(_cache) > settings.TTS_CACHE_SIZE:
        _cache.popitem(last=False)
    return wav
