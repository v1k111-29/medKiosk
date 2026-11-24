"""
Text-to-speech router.

Auth decision: `/tts` and `/tts/config` are PUBLIC (no kiosk key) because the
staff waiting-room display board (no login, different origin) also speaks token
announcements through it. Abuse is bounded instead by: text capped at 500 chars,
an in-process per-client-IP rate limit (TTS_RATE_LIMIT_PER_MIN, default 60/min),
and the server-side LRU cache. The endpoint only synthesises caller-supplied
text and exposes no patient data. Multi-worker deployments get a per-worker limit.
"""

from __future__ import annotations

import time
from collections import defaultdict, deque
from typing import Literal

from fastapi import APIRouter, Request
from fastapi.responses import Response
from pydantic import BaseModel, Field

from app.core.config import settings
from app.core.errors import KioskError
from app.services import tts_service

router = APIRouter(tags=["Text to Speech"])

_hits: dict[str, deque] = defaultdict(deque)


def _rate_limited(ip: str) -> bool:
    now = time.monotonic()
    q = _hits[ip]
    while q and now - q[0] > 60:
        q.popleft()
    if len(q) >= settings.TTS_RATE_LIMIT_PER_MIN:
        return True
    q.append(now)
    if len(_hits) > 1024:  # drop idle clients
        for k in [k for k, v in _hits.items() if not v or now - v[-1] > 60]:
            _hits.pop(k, None)
    return False


class TTSRequest(BaseModel):
    text: str = Field(min_length=1, max_length=tts_service.MAX_TEXT_CHARS)
    language: Literal["ta", "en"] = "en"


@router.get("/tts/config")
async def tts_config():
    return {"provider": tts_service.provider()}


@router.post("/tts")
async def tts(body: TTSRequest, request: Request):
    if not tts_service.is_enabled():
        raise KioskError("Server text-to-speech is disabled.", "குரல் வெளியீடு முடக்கப்பட்டுள்ளது.", status_code=503)
    ip = request.client.host if request.client else "unknown"
    if _rate_limited(ip):
        raise KioskError("Too many speech requests.", "அதிக கோரிக்கைகள்.", status_code=429)
    text = body.text.strip()
    if not text:
        raise KioskError("Text is empty.", "உரை காலியாக உள்ளது.", status_code=422)
    try:
        wav = await tts_service.synthesize(text, body.language)
    except tts_service.TTSUnavailable:
        raise KioskError("Text-to-speech is temporarily unavailable.", "குரல் வெளியீடு கிடைக்கவில்லை.", status_code=503)
    return Response(content=wav, media_type="audio/wav", headers={"Cache-Control": "private, max-age=3600"})
