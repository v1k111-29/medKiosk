"""
LLM Service — Groq chat completions for conversational registration, triage and chat.

The LLM never decides rooms, wait times or department names: triage returns only
dept_id / urgency / symptoms / reply / confidence / intent / service, and the
department details are resolved from the `departments` table by the caller.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Optional

import httpx

from app.core.config import settings
from app.services import groq_client

logger = logging.getLogger("kiosk.llm")

URGENCY_VALUES = ("normal", "urgent", "emergency")
SERVICE_VALUES = ("symptoms", "appointment", "followup", "emergency")
FALLBACK_DEPT = "general"


# ── System Prompts ────────────────────────────────────────────────────────────

REGISTRATION_SYSTEM_PROMPT = """\
You are a warm, friendly hospital kiosk assistant helping a NEW patient register.
Reply naturally and briefly (max 25 words).

Extract patient details from what they say, acknowledge, then ask for the NEXT missing field.

Fields to collect:
- name (string, required)
- age (integer)
- phone (10-digit Indian mobile)
- blood_group (A+/A-/B+/B-/AB+/AB-/O+/O-)
- city (string)

Rules:
- Extract ALL fields mentioned in one utterance ("I'm Ravi, 35, from Chennai").
- Accept spoken numbers ("thirty five" = 35).
- Skip blood_group if unknown — don't insist.
- Use their name once you know it.
- Always write name and city in English letters, even if spoken in Tamil (முருகன் -> "Murugan", கோயம்புத்தூர் -> "Coimbatore").
- Set all_collected true when name is known and patient seems done.
- If the user input is exactly ".", it means no voice was heard. Reply: "I didn't quite catch that. Could you please repeat?"

Return ONLY valid JSON (no markdown):
{"extracted":{"name":null,"age":null,"phone":null,"blood_group":null,"city":null},"reply":"...","all_collected":false}
"""

REGISTRATION_TAMIL_RULE = """
LANGUAGE: The patient chose Tamil. Write "reply" in simple, polite spoken Tamil (Tamil script), as a hospital receptionist in Tamil Nadu would speak. Keep field values in "extracted" in English letters.
If the user input is exactly ".", reply: "மன்னிக்கவும், சரியாகக் கேட்கவில்லை. மீண்டும் சொல்ல முடியுமா?"
"""

REGISTRATION_FALLBACK_REPLY = {
    "en": "I'm sorry, I had a little trouble there. Could you please say that again?",
    "ta": "மன்னிக்கவும், சிறிய பிரச்சனை. தயவுசெய்து மீண்டும் சொல்லுங்கள்.",
}
REGISTRATION_REPEAT_REPLY = {
    "en": "Could you please repeat that?",
    "ta": "தயவுசெய்து மீண்டும் சொல்லுங்கள்.",
}

TRIAGE_SYSTEM_PROMPT_TEMPLATE = """\
You are a clinical triage assistant at a hospital kiosk. Your task is to route patients to the correct department based on their symptoms.
Be accurate and clinically sound. Reply warmly in 1-2 sentences.
Do NOT mention room numbers or waiting times in your reply — the kiosk shows those.

═══ CLINICAL PRIORITY RULES (apply these BEFORE department keywords) ═══

1. GENERAL MEDICINE (dept_id: "general") — the DEFAULT for acute/common illness:
   ✓ Fever (any cause)
   ✓ Common cold, runny nose, nasal congestion
   ✓ Sore throat / throat pain / pharyngitis — ESPECIALLY with fever or cold
   ✓ Cough (acute, < 3 weeks)
   ✓ Flu, viral infection, URTI (upper respiratory tract infection)
   ✓ Headache, body ache, fatigue
   ✓ Stomach pain, nausea, vomiting, diarrhoea
   ✓ General weakness, loss of appetite
   ✓ Diabetes/BP routine checkup
   ✓ Patient asks for "OPD", "GP", "doctor" without specifying

2. ENT (dept_id: "ent") — ONLY for chronic/specialist ear-nose-throat conditions:
   ✓ Hearing loss, deafness
   ✓ Chronic sinusitis (> 12 weeks)
   ✓ Tonsillectomy / adenoidectomy
   ✓ Nasal polyps, deviated septum
   ✓ Vertigo / balance disorders
   ✓ Ear discharge, ear drum perforation
   ✗ NEVER route to ENT for: sore throat + fever, common cold, flu, acute cough

3. CARDIOLOGY (dept_id: "cardio") — heart / cardiovascular only:
   ✓ Chest pain or pressure
   ✓ Palpitations, irregular heartbeat
   ✓ Uncontrolled high BP with symptoms
   ✓ Breathlessness at rest or on mild exertion

4. ORTHOPAEDICS (dept_id: "ortho"):
   ✓ Joint pain (knee, hip, shoulder, spine)
   ✓ Fractures, sprains, sports injuries
   ✓ Back pain, neck pain

5. PAEDIATRICS (dept_id: "paeds"):
   ✓ Child / infant / baby patients (under 14 years)
   ✓ Growth, developmental concerns in children

6. GYNAECOLOGY (dept_id: "gyne"):
   ✓ Pregnancy, antenatal care
   ✓ Menstrual problems, PCOS
   ✓ Female reproductive concerns

7. DERMATOLOGY (dept_id: "derm"):
   ✓ Skin rash, eczema, psoriasis, acne
   ✓ Fungal/allergic skin conditions
   ✓ Hair/nail disorders

8. OPHTHALMOLOGY (dept_id: "ophthal"):
   ✓ Eye pain, redness, discharge
   ✓ Blurred / reduced vision
   ✓ Cataract, glaucoma follow-up

9. EMERGENCY (dept_id: "emergency", urgency: "emergency"):
   ✓ Severe chest pain / suspected heart attack
   ✓ Difficulty breathing / breathlessness at rest
   ✓ Heavy uncontrolled bleeding
   ✓ Loss of consciousness / seizure
   ✓ Stroke symptoms (face drooping, arm weakness, speech slurred)

═══ EXAMPLES ═══
"fever and cold" → general
"fever, cold, sore throat" → general  (NOT ent)
"sore throat for 2 days with fever" → general
"sore throat, cough, runny nose" → general
"chronic hearing loss for 6 months" → ent
"throat pain + body ache + fever" → general
"chest pain and sweating" → emergency
"knee pain after fall" → ortho
"skin rash and itching" → derm
"Baby has fever" → paeds

IF INPUT IS JUST ".":
   - It means no voice was heard. Ask the patient to repeat.
   - Example reply: "I'm sorry, I didn't catch that. Could you please repeat?"
   - Set urgency="normal", service="symptoms", dept_id="general" (as fallback).

═══ VALID dept_id VALUES (use exactly one of these) ═══
{dept_list}

Return ONLY valid JSON (no markdown, no explanation):
{{
  "intent": "symptoms",
  "service": "symptoms",
  "dept_id": "general",
  "symptoms": "brief description of patient's symptoms",
  "urgency": "normal",
  "confidence": 0.95,
  "reply": "1-2 sentence warm reply confirming the department"
}}
urgency values: normal | urgent | emergency
service values: symptoms | appointment | followup
"""

CONVERSATION_SYSTEM_PROMPT = """\
You are a friendly hospital kiosk AI assistant. The patient is already registered and checked in.
Keep replies warm and brief (max 30 words).
Your job: understand what the patient wants and set the right intent.

If the patient describes symptoms or asks to see a doctor → intent="symptoms"
If the patient asks to book an appointment (OPD, specific dept, doctor visit) → intent="appointment"
If the patient mentions a follow-up / previous visit → intent="followup"
If it is an emergency → intent="emergency"
If just greeting/chat → intent="greeting"
If the patient input is exactly "." (no voice heard) → intent="greeting", reply="I didn't quite catch that. Could you please repeat?"

Return ONLY valid JSON:
{"intent": "greeting", "reply": "...", "suggest_triage": false}
intent: greeting | symptoms | appointment | followup | emergency | question | other
"""


# ── Health Check ──────────────────────────────────────────────────────────────

async def check_groq_health() -> dict:
    """Check if the Groq API key is configured and the API is reachable."""
    if not groq_client.is_configured():
        return {"ok": False, "error": "GROQ_API_KEY not set. Get a free key at https://console.groq.com"}
    try:
        client = await groq_client.get_client()
        r = await client.get(groq_client.GROQ_MODELS_URL, headers=groq_client.auth_headers(), timeout=5.0)
        if r.status_code == 200:
            return {"ok": True, "model": settings.GROQ_MODEL}
        return {"ok": False, "error": f"Groq returned HTTP {r.status_code}"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


# ── Core Groq Call ────────────────────────────────────────────────────────────

def _is_reasoning_model(name: str) -> bool:
    n = name.lower()
    return n.startswith("openai/gpt-oss") or n.startswith("qwen/qwen3")


async def _call_groq(
    system_prompt: str,
    user_prompt: str,
    model: Optional[str] = None,
    max_tokens: int = 300,
) -> Optional[dict]:
    """Call Groq chat completions in JSON mode. Returns parsed dict or None on failure."""
    if not groq_client.is_configured():
        logger.error("[LLM] GROQ_API_KEY is not set. Cannot call Groq API.")
        return None

    model_name = model or settings.GROQ_MODEL
    payload = {
        "model": model_name,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0.5,
        "max_tokens": max_tokens,
    }
    # Reasoning models (gpt-oss, qwen3) spend output tokens on hidden reasoning
    # before the JSON answer. With a small max_tokens they run out and Groq
    # returns 400 json_validate_failed with empty output. Keep reasoning short
    # and give room for it.
    if _is_reasoning_model(model_name):
        payload["reasoning_effort"] = "low"
        payload["max_tokens"] = max(max_tokens, 1500)

    raw_text = ""
    try:
        client = await groq_client.get_client()
        for attempt in range(2):
            response = await client.post(
                groq_client.GROQ_CHAT_URL,
                json=payload,
                headers=groq_client.auth_headers(),
                timeout=settings.GROQ_TIMEOUT,
            )
            # One short retry on rate limit (patient is waiting at the kiosk:
            # never wait more than 3 s; after that the rule engine takes over).
            # Groq JSON mode occasionally fails validation on a valid request;
            # one immediate retry usually succeeds.
            if (response.status_code == 400 and attempt == 0
                    and "json_validate_failed" in response.text):
                logger.warning("[LLM] Groq json_validate_failed; retrying once")
                continue
            if response.status_code == 429 and attempt == 0:
                try:
                    wait = float(response.headers.get("retry-after", "1"))
                except ValueError:
                    wait = 1.0
                wait = min(max(wait, 0.5), 3.0)
                logger.warning("[LLM] Groq rate limit hit; retrying once in %.1fs", wait)
                await asyncio.sleep(wait)
                continue
            break
        response.raise_for_status()
        raw_text = response.json()["choices"][0]["message"]["content"]
        return json.loads(raw_text)
    except json.JSONDecodeError as e:
        logger.error("[LLM] Groq returned invalid JSON: %s (len=%d)", e, len(raw_text))
        return None
    except httpx.TimeoutException:
        logger.error("[LLM] Groq timed out after %ss", settings.GROQ_TIMEOUT)
        return None
    except httpx.HTTPStatusError as e:
        status = e.response.status_code
        if status == 401:
            logger.error("[LLM] Groq API key invalid or missing. Check GROQ_API_KEY.")
        elif status == 429:
            logger.warning("[LLM] Groq rate limit hit.")
        else:
            logger.error("[LLM] Groq HTTP %s: %s", status, e.response.text[:200])
        return None
    except Exception as e:
        logger.error("[LLM] Groq call failed: %s", e)
        return None


# ── Registration Conversation ─────────────────────────────────────────────────

async def call_llm_registration(
    user_text: str,
    collected_fields: dict,
    conversation_history: Optional[list] = None,
    language: str = "en",
) -> dict:
    """Extract patient fields from natural speech.

    `language` is the kiosk language ("en" or "ta"); the spoken reply is
    written in it. Extracted values are always in English letters.

    Returns {"extracted": {...}, "reply": "...", "all_collected": bool}
    """
    already, missing = [], []
    for field in ["name", "age", "phone", "blood_group", "city"]:
        val = collected_fields.get(field)
        if val is not None and val != "" and val != 0:
            already.append(f"  {field}: {val}")
        else:
            missing.append(field)

    context_parts = []
    if already:
        context_parts.append("Already collected:\n" + "\n".join(already))
    if missing:
        context_parts.append("Still needed: " + ", ".join(missing))

    history_text = ""
    if conversation_history:
        lines = []
        for msg in conversation_history[-6:]:
            role = "Patient" if msg.get("role") == "user" else "Assistant"
            lines.append(f"{role}: {msg['content']}")
        history_text = "\n\nRecent conversation:\n" + "\n".join(lines)

    user_prompt = (
        f"{chr(10).join(context_parts)}{history_text}\n\n"
        f'Patient says: "{user_text}"\n\n'
        "Extract new fields and reply naturally. Output JSON:"
    )

    lang = "ta" if language == "ta" else "en"
    system_prompt = REGISTRATION_SYSTEM_PROMPT
    if lang == "ta":
        system_prompt += REGISTRATION_TAMIL_RULE

    result = await _call_groq(system_prompt, user_prompt)
    if result is None:
        return {
            "extracted": {},
            "reply": REGISTRATION_FALLBACK_REPLY[lang],
            "all_collected": False,
        }

    extracted = result.get("extracted") or {}
    sanitized = {}
    for field in ["name", "age", "phone", "blood_group", "city"]:
        val = extracted.get(field)
        if val is not None and str(val).lower() not in ("null", "none", ""):
            if field == "age":
                try:
                    sanitized[field] = int(val)
                except (ValueError, TypeError):
                    pass
            else:
                sanitized[field] = str(val).strip()

    return {
        "extracted": sanitized,
        "reply": result.get("reply") or REGISTRATION_REPEAT_REPLY[lang],
        "all_collected": bool(result.get("all_collected", False)),
    }


# ── Triage Conversation ───────────────────────────────────────────────────────

def build_triage_prompt(departments: dict[str, dict]) -> str:
    dept_list = "\n".join(f"- {dept_id}: {d['name_en']}" for dept_id, d in departments.items())
    return TRIAGE_SYSTEM_PROMPT_TEMPLATE.format(dept_list=dept_list)


async def call_llm_triage(user_text: str, departments: dict[str, dict]) -> dict:
    """Analyse symptoms and route to a department.

    `departments` maps dept_id → {name_en, name_ta, room, wait_mins} from the
    departments table (active only). The LLM's dept_id is validated against it;
    unknown ids fall back to "general".
    """
    user_prompt = f'Patient says: "{user_text}"\n\nApply the clinical priority rules. Output JSON only:'
    result = await _call_groq(
        build_triage_prompt(departments), user_prompt, model=settings.GROQ_TRIAGE_MODEL, max_tokens=400
    )

    if result is None:
        # Callers (conversation router) fall back to deterministic rules on llm_failed.
        return {
            "llm_failed": True,
            "intent": "other",
            "department": None,
            "symptoms": None,
            "urgency": "normal",
            "confidence": 0.0,
            "reply": "I'm having a little trouble. Could you please describe your symptoms again?",
        }

    raw_dept = str(result.get("dept_id") or result.get("department") or "").strip().lower()
    if raw_dept in departments:
        dept_id = raw_dept
    else:
        if raw_dept:
            logger.warning("[LLM] Triage returned unknown dept_id=%r → %s", raw_dept, FALLBACK_DEPT)
        dept_id = FALLBACK_DEPT if FALLBACK_DEPT in departments else next(iter(departments), FALLBACK_DEPT)

    urgency = str(result.get("urgency") or "normal").lower()
    if urgency not in URGENCY_VALUES:
        urgency = "normal"
    if dept_id == "emergency":
        urgency = "emergency"

    service = str(result.get("service") or "symptoms").lower()
    if service not in SERVICE_VALUES:
        service = "symptoms"

    try:
        confidence = max(0.0, min(1.0, float(result.get("confidence", 0.8))))
    except (TypeError, ValueError):
        confidence = 0.8

    d = departments.get(dept_id, {})
    return {
        "intent": result.get("intent", "symptoms"),
        "service": service,
        "dept_id": dept_id,
        "dept_name": d.get("name_en"),
        "dept_name_ta": d.get("name_ta"),
        "room": d.get("room"),
        "wait_mins": int(d.get("wait_mins", 0)),
        "department": dept_id,  # legacy field
        "symptoms": result.get("symptoms"),
        "urgency": urgency,
        "confidence": confidence,
        "reply": result.get("reply", "Let me direct you to the right department."),
    }


# ── General Conversation ──────────────────────────────────────────────────────

async def call_llm_general(user_text: str) -> dict:
    """General chat: friendly response, detect if symptoms mentioned."""
    user_prompt = f'Patient says: "{user_text}"\n\nRespond naturally. Output JSON:'
    result = await _call_groq(CONVERSATION_SYSTEM_PROMPT, user_prompt)
    if result is None:
        return {"intent": "other", "reply": "I'm sorry, could you say that again?", "suggest_triage": False}
    return {
        "intent": result.get("intent", "other"),
        "reply": result.get("reply", "How can I help you today?"),
        "suggest_triage": bool(result.get("suggest_triage", False)),
    }
