"""
Conversation Router — Natural language interaction endpoints.

Three conversation modes:
- /conversation/register : Collect patient details via natural speech
- /conversation/triage   : Symptom analysis and department routing
- /conversation/chat     : General conversation / Q&A
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
import logging

from app.services.llm_service import (
    call_llm_registration,
    call_llm_triage,
    call_llm_general,
)

logger = logging.getLogger("kiosk.conversation")

router = APIRouter(prefix="/conversation", tags=["Conversational AI"])


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

    logger.info(f"[Conversation/Register] Input: '{req.text[:100]}'")

    # Convert history to dicts for the LLM service
    history_dicts = [{"role": m.role, "content": m.content} for m in req.history]

    result = await call_llm_registration(
        user_text=req.text,
        collected_fields=req.collected_fields,
        conversation_history=history_dicts,
    )

    logger.info(
        f"[Conversation/Register] Extracted: {result.get('extracted', {})} "
        f"| all_collected: {result.get('all_collected', False)}"
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
        logger.info(f"[Conversation/Triage] Non-English input (lang={req.language})")

    logger.info(f"[Conversation/Triage] Input: '{req.text[:100]}'")

    result = await call_llm_triage(req.text)

    logger.info(
        f"[Conversation/Triage] → dept_id={result.get('dept_id')} "
        f"urgency={result.get('urgency')} conf={result.get('confidence')}"
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

    return await call_llm_triage(req.text)
