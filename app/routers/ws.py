"""
WebSocket endpoints (single-process hub — see app/services/realtime.py).

WS /ws/queue?token=<JWT>  staff: {"type":"queue.updated","data":<queue item>}; closes 4401 on bad token
WS /ws/display            public: {"type":"token.called",...} and {"type":"counts",...}
"""

import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fastapi.concurrency import run_in_threadpool

from app.core.database import session_scope
from app.core.security import user_from_token
from app.services.queue_service import waiting_counts
from app.services.realtime import DISPLAY, STAFF, hub

logger = logging.getLogger("kiosk.ws")

router = APIRouter(tags=["WebSockets"])


async def _hold(channel: str, ws: WebSocket) -> None:
    """Keep the socket registered until the client disconnects (client messages are ignored)."""
    hub.connect(channel, ws)
    try:
        while True:
            msg = await ws.receive_text()
            if msg == "ping":
                await ws.send_json({"type": "pong"})
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.debug("[WS] %s socket error: %s", channel, e)
    finally:
        hub.disconnect(channel, ws)


def _auth_staff(token: str):
    with session_scope() as session:
        user = user_from_token(session, token)
        return (user.id, user.role) if user else None


def _counts() -> dict:
    with session_scope() as session:
        return waiting_counts(session)


@router.websocket("/ws/queue")
async def ws_queue(ws: WebSocket):
    token = ws.query_params.get("token")
    who = await run_in_threadpool(_auth_staff, token) if token else None
    await ws.accept()
    if who is None:
        await ws.close(code=4401, reason="Invalid or missing token")
        return
    logger.info("[WS] staff connected user_id=%s", who[0])
    await _hold(STAFF, ws)


@router.websocket("/ws/display")
async def ws_display(ws: WebSocket):
    await ws.accept()
    try:
        await ws.send_json({"type": "counts", "data": await run_in_threadpool(_counts)})
    except Exception:
        return
    await _hold(DISPLAY, ws)
