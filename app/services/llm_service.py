"""
LLM Service — Local Ollama (Gemma 3 4B) for conversational registration & triage.
Designed for edge deployment on Raspberry Pi 5 (8GB RAM).

Ensure Ollama is running locally:
  curl -fsSL https://ollama.com/install.sh | sh
  ollama pull gemma3:4b

# ─── OLD GROQ CLOUD CODE (commented out) ──────────────────────────────────────
# Set GROQ_API_KEY environment variable before starting.
# Get a free key at: https://console.groq.com
#
# GROQ_BASE_URL   = "https://api.groq.com/openai/v1"
# GROQ_CHAT_URL   = f"{GROQ_BASE_URL}/chat/completions"
# GROQ_MODEL      = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")
# GROQ_TRIAGE_MODEL = os.getenv("GROQ_TRIAGE_MODEL", "llama-3.3-70b-versatile")
# GROQ_TIMEOUT    = float(os.getenv("GROQ_TIMEOUT", "30"))
#
# def _get_groq_api_key() -> str:
#     return os.getenv("GROQ_API_KEY", "")
#
# async def _call_groq(system_prompt, user_prompt, model=None, max_tokens=300):
#     if not _get_groq_api_key():
#         logger.error("[LLM] GROQ_API_KEY is not set.")
#         return None
#     payload = {
#         "model": model or GROQ_MODEL,
#         "messages": [
#             {"role": "system", "content": system_prompt},
#             {"role": "user",   "content": user_prompt},
#         ],
#         "response_format": {"type": "json_object"},
#         "temperature": 0.25,
#         "max_tokens": max_tokens,
#     }
#     headers = {
#         "Authorization": f"Bearer {_get_groq_api_key()}",
#         "Content-Type": "application/json",
#     }
#     async with httpx.AsyncClient(timeout=GROQ_TIMEOUT) as client:
#         response = await client.post(GROQ_CHAT_URL, json=payload, headers=headers)
#         response.raise_for_status()
#         result = response.json()
#         raw_text = result["choices"][0]["message"]["content"]
#         return json.loads(raw_text)
#
# async def check_groq_health() -> dict:
#     if not _get_groq_api_key():
#         return {"ok": False, "error": "GROQ_API_KEY not set."}
#     try:
#         async with httpx.AsyncClient(timeout=5.0) as client:
#             r = await client.get(
#                 f"{GROQ_BASE_URL}/models",
#                 headers={"Authorization": f"Bearer {_get_groq_api_key()}"},
#             )
#             if r.status_code == 200:
#                 return {"ok": True, "model": GROQ_MODEL}
#             return {"ok": False, "error": f"Groq returned HTTP {r.status_code}"}
#     except Exception as e:
#         return {"ok": False, "error": str(e)}
# ──────────────────────────────────────────────────────────────────────────────

# ─── OLD OLLAMA CODE (commented out — original pre-Groq version) ─────────────
# OLLAMA_BASE_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
# OLLAMA_GENERATE = f"{OLLAMA_BASE_URL}/api/generate"
# OLLAMA_MODEL    = os.getenv("OLLAMA_MODEL", "llama3.1:8b")
# OLLAMA_TIMEOUT  = float(os.getenv("OLLAMA_TIMEOUT", "180"))
#
# async def _call_ollama(system_prompt, user_prompt):
#     payload = {
#         "model": OLLAMA_MODEL,
#         "system": system_prompt,
#         "prompt": user_prompt,
#         "stream": False,
#         "format": "json",
#         "options": {"temperature": 0.3, "num_predict": 150, "num_ctx": 2048},
#     }
#     async with httpx.AsyncClient(timeout=OLLAMA_TIMEOUT) as client:
#         response = await client.post(OLLAMA_GENERATE, json=payload)
#         response.raise_for_status()
#         return json.loads(response.json().get("response", ""))
# ──────────────────────────────────────────────────────────────────────────────
"""

import os
import json
import logging
import re
import httpx
from typing import Optional

logger = logging.getLogger("kiosk.llm")

# ── Ollama Local Configuration (Gemma 3 — edge-friendly for RPi 5) ───────────
OLLAMA_BASE_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
OLLAMA_CHAT_URL = f"{OLLAMA_BASE_URL}/api/chat"
OLLAMA_MODEL    = os.getenv("OLLAMA_MODEL", "gemma3:4b")
# Longer timeout for Raspberry Pi 5 CPU inference (~5-15s per response)
OLLAMA_TIMEOUT  = float(os.getenv("OLLAMA_TIMEOUT", "120"))


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
- Set all_collected true when name is known and patient seems done.
- If the user input is exactly ".", it means no voice was heard. Reply: "I didn't quite catch that. Could you please repeat?"
- CORRECTIONS: If the patient repeats or restates a field that was already collected
  (e.g. says a different phone number, a different name, or "no it's X" / "actually X" /
  "I said X" / "it's X not Y"), ALWAYS overwrite the stored value with the new one.
  Never tell the patient that the field is already saved or ask them to move on.
  Simply confirm the corrected value and continue.

Return ONLY valid JSON (no markdown):
{"extracted":{"name":null,"age":null,"phone":null,"blood_group":null,"city":null},"reply":"...","all_collected":false}
"""

TRIAGE_SYSTEM_PROMPT = """\
You are a clinical triage assistant at a hospital kiosk. Your task is to route patients to the correct department based on their symptoms.
Be accurate and clinically sound. Reply warmly in 1-2 sentences.

═══ CLINICAL PRIORITY RULES (apply these BEFORE department keywords) ═══

1. GENERAL OPD (dept_id: "general") — for specific acute/common illness:
   ✓ Fever (any cause)
   ✓ Common cold, runny nose, nasal congestion
   ✓ Sore throat / throat pain / pharyngitis — ESPECIALLY with fever or cold
   ✓ Cough (acute, < 3 weeks)
   ✓ Flu, viral infection, URTI (upper respiratory tract infection)
   ✓ Headache, body ache, fatigue
   ✓ Stomach pain, nausea, vomiting, diarrhoea
   ✓ General weakness, loss of appetite
   ✓ Diabetes/BP routine checkup

2. ENT — ONLY for chronic/specialist ear-nose-throat conditions:
   ✓ Hearing loss, deafness
   ✓ Chronic sinusitis (> 12 weeks)
   ✓ Tonsillectomy / adenoidectomy
   ✓ Nasal polyps, deviated septum
   ✓ Vertigo / balance disorders
   ✓ Ear discharge, ear drum perforation
   ✗ NEVER route to ENT for: sore throat + fever, common cold, flu, acute cough

3. CARDIOLOGY — heart / cardiovascular only:
   ✓ Chest pain or pressure
   ✓ Palpitations, irregular heartbeat
   ✓ Uncontrolled high BP with symptoms
   ✓ Breathlessness at rest or on mild exertion

4. ORTHOPEDICS:
   ✓ Joint pain (knee, hip, shoulder, spine)
   ✓ Fractures, sprains, sports injuries
   ✓ Back pain, neck pain

5. PAEDIATRICS:
   ✓ Child / infant / baby patients (under 14 years)
   ✓ Growth, developmental concerns in children

6. GYNAECOLOGY:
   ✓ Pregnancy, antenatal care
   ✓ Menstrual problems, PCOS
   ✓ Female reproductive concerns

7. DERMATOLOGY:
   ✓ Skin rash, eczema, psoriasis, acne
   ✓ Fungal/allergic skin conditions
   ✓ Hair/nail disorders

8. OPHTHALMOLOGY:
   ✓ Eye pain, redness, discharge
   ✓ Blurred / reduced vision
   ✓ Cataract, glaucoma follow-up

9. EMERGENCY (urgency: "emergency"):
   ✓ Severe chest pain / suspected heart attack
   ✓ Difficulty breathing / breathlessness at rest
   ✓ Heavy uncontrolled bleeding
   ✓ Loss of consciousness / seizure
   ✓ Stroke symptoms (face drooping, arm weakness, speech slurred)

6. VAGUE OR UNCLEAR INPUT (No direct fallback):
   - If the input is just ".", a greeting, or vague like "I am sick" or "I need a doctor" without specific symptoms.
   - DO NOT route to general. 
   - Set intent="clarify", dept_id="unknown", and ask the patient to describe their symptoms.

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
"I feel sick" → clarify (ask for symptoms)
"I want to see a doctor" → clarify (ask for symptoms)

═══ DEPARTMENT REFERENCE ═══
Room numbers: general=OPD-1, cardio=OPD-3, ortho=OPD-4, paeds=OPD-2, gyne=OPD-5, derm=OPD-6, ent=OPD-7, ophthal=OPD-8, emergency=ER-1
Wait times (min): general=20, cardio=30, ortho=25, paeds=15, gyne=20, derm=15, ent=15, ophthal=20

Return ONLY valid JSON (no markdown, no explanation):
{
  "intent": "symptoms",
  "service": "symptoms",
  "dept_id": "general",
  "dept_name": "General OPD",
  "room": "OPD-1",
  "wait_mins": 20,
  "symptoms": "brief description of patient's symptoms",
  "urgency": "normal",
  "confidence": 0.95,
  "reply": "1-2 sentence warm reply confirming department"
}
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

async def check_ollama_health() -> bool:
    """Check if Ollama is running and reachable at the configured URL."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get(OLLAMA_BASE_URL)
            return r.status_code == 200
    except Exception:
        return False


async def check_ollama_model() -> dict:
    """Check if the configured model is available in Ollama."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get(f"{OLLAMA_BASE_URL}/api/tags")
            if r.status_code != 200:
                return {"available": False, "model": OLLAMA_MODEL, "error": f"Ollama HTTP {r.status_code}"}
            models = r.json().get("models", [])
            model_names = [m.get("name", "") for m in models]
            # Check if our model (or a prefix match) is available
            found = any(
                OLLAMA_MODEL == name or name.startswith(OLLAMA_MODEL.split(":")[0])
                for name in model_names
            )
            if found:
                return {"available": True, "model": OLLAMA_MODEL}
            return {
                "available": False,
                "model": OLLAMA_MODEL,
                "error": f"Model '{OLLAMA_MODEL}' not found. Run: ollama pull {OLLAMA_MODEL}",
            }
    except Exception as e:
        return {"available": False, "model": OLLAMA_MODEL, "error": str(e)}


async def warmup_ollama() -> bool:
    """Send a short warmup prompt to load the model into memory."""
    logger.info(f"[LLM] Warming up Ollama model '{OLLAMA_MODEL}'...")
    try:
        payload = {
            "model": OLLAMA_MODEL,
            "messages": [{"role": "user", "content": "hi"}],
            "stream": False,
            "options": {"num_predict": 5},
        }
        async with httpx.AsyncClient(timeout=OLLAMA_TIMEOUT) as client:
            r = await client.post(OLLAMA_CHAT_URL, json=payload)
            if r.status_code == 200:
                logger.info("[LLM] Ollama warmup complete — model loaded into memory.")
                return True
            logger.warning(f"[LLM] Ollama warmup got HTTP {r.status_code}")
            return False
    except Exception as e:
        logger.warning(f"[LLM] Ollama warmup failed: {e}")
        return False


# ── Core Ollama Call ──────────────────────────────────────────────────────────

def _extract_json_from_text(text: str) -> Optional[dict]:
    """
    Try to extract a JSON object from text that may contain markdown fences
    or extra prose (common with smaller edge models like Gemma 3 4B).
    """
    # 1. Try direct parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # 2. Try extracting from ```json ... ``` fences
    fence_match = re.search(r"```(?:json)?\s*\n?(.*?)\n?\s*```", text, re.DOTALL)
    if fence_match:
        try:
            return json.loads(fence_match.group(1).strip())
        except json.JSONDecodeError:
            pass

    # 3. Try finding the first { ... } block
    brace_match = re.search(r"\{.*\}", text, re.DOTALL)
    if brace_match:
        try:
            return json.loads(brace_match.group(0))
        except json.JSONDecodeError:
            pass

    return None


async def _call_ollama(
    system_prompt: str,
    user_prompt: str,
    model: Optional[str] = None,
    max_tokens: int = 300,
) -> Optional[dict]:
    """
    Call local Ollama chat completions API.
    Returns parsed dict or None on failure.
    """
    payload = {
        "model": model or OLLAMA_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_prompt},
        ],
        "stream": False,
        "format": "json",
        "options": {
            "temperature": 0.25,
            "num_predict": max_tokens,
            "num_ctx": 4096,
        },
    }

    raw_text = ""
    try:
        async with httpx.AsyncClient(timeout=OLLAMA_TIMEOUT) as client:
            response = await client.post(OLLAMA_CHAT_URL, json=payload)
            response.raise_for_status()
            result = response.json()
            raw_text = result.get("message", {}).get("content", "")
            parsed = _extract_json_from_text(raw_text)
            if parsed is None:
                logger.error(f"[LLM] Ollama returned non-JSON: {raw_text[:300]}")
                return None
            logger.debug(f"[LLM] Ollama response: {parsed}")
            return parsed

    except json.JSONDecodeError as e:
        logger.error(f"[LLM] Ollama returned invalid JSON: {e} | raw: {raw_text[:300]}")
        return None
    except httpx.TimeoutException:
        logger.error(f"[LLM] Ollama timed out after {OLLAMA_TIMEOUT}s")
        return None
    except httpx.ConnectError:
        logger.error(
            "[LLM] Cannot connect to Ollama. Is it running? "
            "Start with: ollama serve"
        )
        return None
    except httpx.HTTPStatusError as e:
        logger.error(f"[LLM] Ollama HTTP {e.response.status_code}: {e.response.text[:200]}")
        return None
    except Exception as e:
        logger.error(f"[LLM] Ollama call failed: {e}")
        return None


# ── Registration Conversation ─────────────────────────────────────────────────

async def call_llm_registration(
    user_text: str,
    collected_fields: dict,
    conversation_history: Optional[list] = None,
) -> dict:
    """
    Conversational registration: extract patient fields from natural speech.

    Args:
        user_text: What the patient just said (transcribed speech)
        collected_fields: Fields already collected {name, age, phone, blood_group, city}
        conversation_history: Previous exchanges [{role, content}, ...]

    Returns:
        {"extracted": {...}, "reply": "...", "all_collected": bool}
    """
    # Build context of what's already known vs missing
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

    # Include recent conversation history
    history_text = ""
    if conversation_history:
        recent = conversation_history[-6:]
        lines = []
        for msg in recent:
            role = "Patient" if msg.get("role") == "user" else "Assistant"
            lines.append(f"{role}: {msg['content']}")
        history_text = "\n\nRecent conversation:\n" + "\n".join(lines)

    context_str = "\n".join(context_parts)
    user_prompt = (
        f"{context_str}{history_text}\n\n"
        f'Patient says: "{user_text}"\n\n'
        "Extract new fields and reply naturally. Output JSON:"
    )

    result = await _call_ollama(REGISTRATION_SYSTEM_PROMPT, user_prompt)

    if result is None:
        return {
            "extracted": {},
            "reply": "I'm sorry, I had a little trouble there. Could you please say that again?",
            "all_collected": False,
        }

    # Validate and sanitize extracted fields
    extracted = result.get("extracted", {})
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
        "reply": result.get("reply", "Could you please repeat that?"),
        "all_collected": bool(result.get("all_collected", False)),
    }


# ── Triage Conversation ───────────────────────────────────────────────────────

async def call_llm_triage(user_text: str) -> dict:
    """
    Triage: analyze symptoms and route to department.
    Uses the same local Gemma model (RPi 5 can only run one model efficiently).
    """
    from app.core.database import get_db
    
    docs_text = ""
    try:
        with get_db() as conn:
            docs = conn.execute("SELECT name, dept_name, available FROM doctors").fetchall()
            doc_lines = []
            for d in docs:
                status = "Available" if d["available"] else "Not Available"
                doc_lines.append(f"- {d['name']} (Dept: {d['dept_name']}) - Status: {status}")
            docs_text = "\n".join(doc_lines)
    except Exception as e:
        logger.error(f"[LLM] Failed to fetch doctors for prompt: {e}")

    user_prompt = (
        f'Hospital Doctors (Check availability here):\n{docs_text}\n\n'
        f'Rules for specific doctor requests:\n'
        f'- If the patient asks for a doctor NOT on this list, return exactly: {{"intent": "unavailable", "reply": "No doctors available by that name."}}\n'
        f'- If the patient asks for a doctor on this list but Status is "Not Available", return exactly: {{"intent": "unavailable", "reply": "That doctor is not available at this moment."}}\n'
        f'- If the patient asks for an Available doctor on this list, route to their department and set intent to "symptoms".\n\n'
        f'Patient says: "{user_text}"\n\n'
        f'Apply the clinical priority rules. Output JSON only:'
    )

    # NOTE: On RPi 5 we use the same model for triage (no separate 70B model)
    # Previously used GROQ_TRIAGE_MODEL = "llama-3.3-70b-versatile"
    result = await _call_ollama(
        TRIAGE_SYSTEM_PROMPT,
        user_prompt,
        model=OLLAMA_MODEL,
        max_tokens=400,
    )

    if result is None:
        return {
            "intent": "other",
            "department": None,
            "symptoms": None,
            "urgency": "normal",
            "confidence": 0.0,
            "reply": "I'm having a little trouble. Could you please describe your symptoms again?",
        }

    # Defaults per dept
    DEPT_ROOMS = {
        "general": "OPD-1", "cardio": "OPD-3", "ortho": "OPD-4",
        "paeds": "OPD-2", "gyne": "OPD-5", "derm": "OPD-6",
        "ent": "OPD-7", "ophthal": "OPD-8", "emergency": "ER-1",
    }
    DEPT_WAIT = {
        "general": 20, "cardio": 30, "ortho": 25, "paeds": 15,
        "gyne": 20, "derm": 15, "ent": 15, "ophthal": 20, "emergency": 0,
    }
    DEPT_NAMES = {
        "general": "General OPD", "cardio": "Cardiology", "ortho": "Orthopedics",
        "paeds": "Paediatrics", "gyne": "Gynaecology", "derm": "Dermatology",
        "ent": "ENT", "ophthal": "Ophthalmology", "emergency": "Emergency",
    }

    dept_id   = result.get("dept_id") or result.get("department") or "unknown"
    dept_name = result.get("dept_name") or DEPT_NAMES.get(dept_id, "Unknown")
    room      = result.get("room")     or DEPT_ROOMS.get(dept_id, "—")
    wait_mins = int(result.get("wait_mins") or DEPT_WAIT.get(dept_id, 20))

    return {
        "intent":    result.get("intent", "symptoms"),
        "service":   result.get("service", "symptoms"),
        "dept_id":   dept_id,
        "dept_name": dept_name,
        "room":      room,
        "wait_mins": wait_mins,
        # legacy field kept for backward compat
        "department":  dept_id,
        "symptoms":    result.get("symptoms"),
        "urgency":     result.get("urgency", "normal"),
        "confidence":  float(result.get("confidence", 0.8)),
        "reply":       result.get("reply", "Let me direct you to the right department."),
    }


# ── General Conversation ──────────────────────────────────────────────────────

async def call_llm_general(user_text: str) -> dict:
    """General chat: friendly response, detect if symptoms mentioned."""
    user_prompt = f'Patient says: "{user_text}"\n\nRespond naturally. Output JSON:'

    result = await _call_ollama(CONVERSATION_SYSTEM_PROMPT, user_prompt)

    if result is None:
        return {
            "intent": "other",
            "reply": "I'm sorry, could you say that again?",
            "suggest_triage": False,
        }

    return {
        "intent":        result.get("intent", "other"),
        "reply":         result.get("reply", "How can I help you today?"),
        "suggest_triage": bool(result.get("suggest_triage", False)),
    }
