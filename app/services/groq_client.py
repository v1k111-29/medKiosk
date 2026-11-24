"""
Shared httpx.AsyncClient for all Groq API calls (chat + Whisper).

Created in the app lifespan (`open_client`) and closed on shutdown. Per-request
timeouts are passed at call time.
"""

from __future__ import annotations

from typing import Optional

import httpx

from app.core.config import settings

GROQ_BASE_URL = "https://api.groq.com/openai/v1"
GROQ_CHAT_URL = f"{GROQ_BASE_URL}/chat/completions"
GROQ_WHISPER_URL = f"{GROQ_BASE_URL}/audio/transcriptions"
GROQ_MODELS_URL = f"{GROQ_BASE_URL}/models"

_client: Optional[httpx.AsyncClient] = None


async def open_client() -> httpx.AsyncClient:
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(
            timeout=httpx.Timeout(settings.GROQ_TIMEOUT),
            limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
        )
    return _client


async def close_client() -> None:
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None


async def get_client() -> httpx.AsyncClient:
    """Return the shared client (opens it lazily if the lifespan did not run)."""
    if _client is None or _client.is_closed:
        return await open_client()
    return _client


def auth_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {settings.GROQ_API_KEY}"}


def is_configured() -> bool:
    return bool(settings.GROQ_API_KEY)
