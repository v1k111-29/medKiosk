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
from app.core.models import Patient
from app.core.security import require_kiosk
from app.services.clinical_rules import escalate, keyword_department
from app.services.llm_service import call_llm_general, call_llm_registration, call_llm_triage
from app.services.queue_service import departments_map, latest_vitals_today, waiting_counts

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


def _patient_context(patient_id: Optional[int]) -> tuple[Optional[int], Optional[dict]]:
    """(age, today's latest vitals) for a patient, or (None, None)."""
    if patient_id is None:
        return None, None
    with session_scope() as session:
        p = session.get(Patient, patient_id)
        if p is None:
            return None, None
        return p.age, latest_vitals_today(session, patient_id)


def _dept_fields(departments: dict[str, dict], dept_id: str) -> dict:
    d = departments.get(dept_id, {})
    return {
        "dept_id": dept_id,
        "dept_name": d.get("name_en"),
        "dept_name_ta": d.get("name_ta"),
        "room": d.get("room"),
        "wait_mins": int(d.get("wait_mins", 0)),
        "department": dept_id,  # legacy field
    }


async def _triage(text: str, patient_id: Optional[int] = None, age: Optional[int] = None) -> dict:
    """LLM triage (advisory) + deterministic safety layer.

    Final urgency = max(LLM, red flags, NEWS2 of today's vitals). Emergency always routes to
    the emergency department. If the LLM fails, keyword routing + rules are used instead.
    """
    departments = await run_in_threadpool(_load_departments)
    p_age, vitals = await run_in_threadpool(_patient_context, patient_id)
    age = age if age is not None else p_age

    result = await call_llm_triage(text, departments)
    reasons_prefix: list[str] = []
    if result.pop("llm_failed", False):
        dept_id = keyword_department(text, age=age)
        if dept_id not in departments:
            dept_id = "general" if "general" in departments else next(iter(departments), "general")
        reasons_prefix.append("AI triage unavailable: rule-based routing used")
        result = {
            "intent": "symptoms",
            "service": "symptoms",
            "symptoms": text.strip(),
            "urgency": "normal",
            "confidence": 0.3,
            "reply": "",
            **_dept_fields(departments, dept_id),
        }

    esc = escalate(result.get("urgency"), text, vitals=vitals, age=age)
    result["urgency"] = esc["urgency"]
    result["escalation_reasons"] = reasons_prefix + esc["escalation_reasons"]
    result["red_flags"] = esc["red_flags"]
    result["news2"] = esc["news2"]

    if esc["urgency"] == "emergency" and "emergency" in departments:
        result.update(_dept_fields(departments, "emergency"))
        result["intent"] = "emergency"
        result["service"] = "emergency"
        room = departments["emergency"].get("room") or "ER"
        result["reply"] = (
            f"This may be an emergency. Please go to Emergency ({room}) now. Staff are being alerted."
        )
    elif esc["red_flags"] and result.get("intent") not in ("symptoms", "appointment", "followup", "emergency"):
        result["intent"] = "symptoms"

    if not result.get("reply"):
        name = result.get("dept_name") or "the right department"
        result["reply"] = f"I'll direct you to {name}."
    return result


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
    language: str = Field("en", description="Reply language: en or ta")


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
    patient_id: Optional[int] = Field(None, description="If given, today's vitals and age feed escalation")
    age: Optional[int] = Field(None, ge=0, le=130)


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
    escalation_reasons: List[str] = Field(default_factory=list)
    red_flags:  List[str] = Field(default_factory=list)
    news2:      Optional[Dict[str, Any]] = None
    disclaimer: Dict[str, str] = Field(
        default_factory=lambda: {"en": "This is not a diagnosis.", "ta": "இது மருத்துவ நோயறிதல் அல்ல."}
    )
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
        language=req.language,
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

    result = await _triage(req.text, patient_id=req.patient_id, age=req.age)

    logger.info(
        "[Conversation/Triage] -> dept_id=%s urgency=%s conf=%s flags=%s",
        result.get("dept_id"), result.get("urgency"), result.get("confidence"), result.get("red_flags"),
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
