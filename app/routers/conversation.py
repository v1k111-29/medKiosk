"""
Conversation Router — Natural language interaction endpoints.

Three conversation modes:
- /conversation/register : Collect patient details via natural speech
- /conversation/triage   : Symptom analysis and department routing
- /conversation/chat     : General conversation / Q&A
"""

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field

from app.core.database import session_scope
from app.core.security import require_kiosk
from app.services.llm_service import call_llm_general, call_llm_registration, call_llm_triage
from app.services.queue_service import departments_map, waiting_counts

logger = logging.getLogger("kiosk.conversation")

router = APIRouter(prefix="/conversation", tags=["Conversational AI"], dependencies=[Depends(require_kiosk)])


def _load_departments() -> dict[str, dict]:
    """Active departments from the DB, with a queue-based wait estimate."""
    with session_scope() as session:
        counts = waiting_counts(session)
        out = {}
        for dept_id, d in departments_map(session, active_only=True).items():
            out[dept_id] = {
                "name_en": d.name_en,
                "name_ta": d.name_ta,
                "room": d.room,
                "wait_mins": 0 if dept_id == "emergency" else counts.get(dept_id, 0) * d.avg_wait_mins,
            }
        return out


async def _triage(text: str) -> dict:
    departments = await run_in_threadpool(_load_departments)
    return await call_llm_triage(text, departments)


# ── Request/Response Schemas ──────────────────────────────────────────────────

class ChatMessage(BaseModel):
    role: str = Field(..., description="'user' or 'assistant'")
    content: str


class RegisterConversationRequest(BaseModel):
    """Request for conversational registration."""
    text: str = Field(..., description="What the patient just said (transcribed speech)")
    collected_fields: Dict[str, Any] = Field(
        default_factory=lambda: {
            "name": None, "age": None, "phone": None,
            "blood_group": None, "city": None,
        },
        description="Fields already collected so far (age may be int)",
    )
    history: List[ChatMessage] = Field(
        default_factory=list,
        description="Previous conversation exchanges",
    )


class RegisterConversationResponse(BaseModel):
    extracted: Dict[str, Any] = Field(
        default_factory=dict,
        description="Newly extracted fields (age=int, others=str)",
    )
    reply: str = Field(..., description="Assistant's natural language reply")
    all_collected: bool = Field(
        False, description="True when all required fields are collected"
    )
    status: str = "success"


class TriageRequest(BaseModel):
    text: str = Field(..., description="Patient's symptom description")
    language: str = Field("en", description="Language code: en, ta, auto")


class TriageResponse(BaseModel):
    intent:     str
    service:    str = "symptoms"
    dept_id:    Optional[str] = None
    dept_name:  Optional[str] = None
    dept_name_ta: Optional[str] = None
    room:       Optional[str] = None
    wait_mins:  int = 15
    # legacy field kept for backward compat
    department: Optional[str] = None
    symptoms:   Optional[str] = None
    urgency:    str = "normal"
    confidence: float = 0.0
    reply:      str = ""
    status:     str = "success"


class ChatRequest(BaseModel):
    text: str
    language: str = "en"


class ChatResponse(BaseModel):
    intent: str = "other"
    reply: str = ""
    suggest_triage: bool = False
    status: str = "success"


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/register", response_model=RegisterConversationResponse)
async def conversation_register(req: RegisterConversationRequest):
    """
    Conversational registration: extract patient details from natural speech.

    Flow:
    1. Frontend captures audio → sends to /transcribe → gets text
    2. Frontend sends text here with collected_fields and history
    3. LLM extracts new fields and generates a natural follow-up reply
    4. Frontend auto-fills extracted fields, speaks the reply via TTS
    5. Repeat until all_collected is True
    """
    if not req.text.strip():
        raise HTTPException(400, "Empty text provided")

    logger.info("[Conversation/Register] input chars=%d history=%d", len(req.text), len(req.history))

    # Convert history to dicts for the LLM service
    history_dicts = [{"role": m.role, "content": m.content} for m in req.history]

    result = await call_llm_registration(
        user_text=req.text,
        collected_fields=req.collected_fields,
        conversation_history=history_dicts,
    )

    logger.info(
        "[Conversation/Register] extracted_fields=%s all_collected=%s",
        sorted(result.get("extracted", {}).keys()), result.get("all_collected", False),
    )

    return RegisterConversationResponse(**result)


@router.post("/triage", response_model=TriageResponse)
async def conversation_triage(req: TriageRequest):
    """
    Triage conversation: analyze symptoms and route to department.

    The LLM analyzes the patient's description and returns:
    - department routing
    - symptom summary
    - urgency level
    - a natural reply
    """
    if not req.text.strip():
        raise HTTPException(400, "Empty text provided")

    if req.language not in ("en", "auto"):
        # For non-English, we still try but warn
        logger.info("[Conversation/Triage] Non-English input (lang=%s)", req.language)

    logger.info("[Conversation/Triage] input chars=%d", len(req.text))

    result = await _triage(req.text)

    logger.info(
        "[Conversation/Triage] -> dept_id=%s urgency=%s conf=%s",
        result.get("dept_id"), result.get("urgency"), result.get("confidence"),
    )

    return TriageResponse(**{k: v for k, v in result.items() if k in TriageResponse.model_fields})


@router.post("/chat", response_model=ChatResponse)
async def conversation_chat(req: ChatRequest):
    """
    General conversation: friendly chat with the kiosk.
    Detects if the patient mentions symptoms and suggests triage.
    """
    if not req.text.strip():
        raise HTTPException(400, "Empty text provided")

    result = await call_llm_general(req.text)
    return ChatResponse(**result)


# ── Legacy endpoint (backward compat) ────────────────────────────────────────

class LegacyConversationRequest(BaseModel):
    text: str
    language: str = "en"


@router.post("")
async def conversation_legacy(req: LegacyConversationRequest):
    """
    Legacy /conversation endpoint for backward compatibility.
    Routes to triage by default.
    """
    if not req.text.strip():
        raise HTTPException(400, "Empty text provided")

    if req.language != "en":
        return {
            "intent": "other",
            "reply": "I currently only support conversational triage in English. Please use the touch menu.",
        }

    return await _triage(req.text)
