"""
Realtime hub — in-memory WebSocket fan-out.

Channels:
- "staff"   (WS /ws/queue)   — {"type": "queue.updated", "data": <queue item>}
- "display" (WS /ws/display) — {"type": "token.called", ...} and {"type": "counts", ...}

LIMITATION: this hub lives in a single process. Running uvicorn/gunicorn with
more than one worker means events published in one worker never reach sockets
held by another. Multi-worker deployments need a shared broker (e.g. Redis
pub/sub, or Postgres LISTEN/NOTIFY) — not built yet. Run a single worker.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from fastapi import WebSocket

logger = logging.getLogger("kiosk.realtime")

STAFF = "staff"
DISPLAY = "display"


class RealtimeHub:
    def __init__(self) -> None:
        self._channels: dict[str, set[WebSocket]] = {STAFF: set(), DISPLAY: set()}
        self._loop: asyncio.AbstractEventLoop | None = None

    def bind_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    def connect(self, channel: str, ws: WebSocket) -> None:
        self._channels.setdefault(channel, set()).add(ws)
        logger.info("[WS] +%s (now %d)", channel, len(self._channels[channel]))

    def disconnect(self, channel: str, ws: WebSocket) -> None:
        self._channels.get(channel, set()).discard(ws)
        logger.info("[WS] -%s (now %d)", channel, len(self._channels.get(channel, ())))

    def count(self, channel: str) -> int:
        return len(self._channels.get(channel, ()))

    async def broadcast(self, channel: str, message: dict[str, Any]) -> None:
        dead = []
        for ws in list(self._channels.get(channel, ())):
            try:
                await asyncio.wait_for(ws.send_json(message), timeout=5)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self._channels[channel].discard(ws)

    def publish(self, channel: str, message: dict[str, Any]) -> None:
        """Fire-and-forget publish, safe to call from sync endpoints (worker threads)."""
        loop = self._loop
        if loop is None or loop.is_closed():
            return
        try:
            running = asyncio.get_running_loop()
        except RuntimeError:
            running = None
        if running is loop:
            loop.create_task(self.broadcast(channel, message))
        else:
            asyncio.run_coroutine_threadsafe(self.broadcast(channel, message), loop)


hub = RealtimeHub()
