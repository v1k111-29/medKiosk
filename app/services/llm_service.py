import httpx
import json
import logging

OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "llama3.1:8b"

SYSTEM_PROMPT = """
You are an expert medical triage assistant for a hospital kiosk. 
Your goal is to extract the patient's intent and symptoms from their speech.
Return ONLY a valid JSON object. Do not include any other text or markdown.

The JSON schema must be exactly:
{
  "intent": "symptoms" | "greeting" | "other",
  "department": "general" | "cardio" | "ortho" | "paeds" | "gyne" | "derm" | "ent" | "ophthal" | null,
  "symptoms": "short summary of symptoms",
  "urgency": "normal" | "urgent" | "emergency",
  "confidence": 0.0 to 1.0,
  "reply": "A short, friendly conversational response in English. Max 20 words."
}

Context for departments:
- cardio: chest pain, heart, blood pressure
- ortho: bones, joints, fractures
- paeds: children, babies
- gyne: pregnancy, female health
- derm: skin, rashes
- ent: ear, nose, throat
- ophthal: eyes, vision
- general: fever, headache, cold, everything else

Example Input: "My chest has been hurting since morning"
Example Output: {"intent": "symptoms", "department": "cardio", "symptoms": "chest pain since morning", "urgency": "normal", "confidence": 0.95, "reply": "I'm sorry you're feeling chest pain. I should direct you to Cardiology, is that okay?"}
"""

async def check_ollama_health():
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            # Check if Ollama is running by pinging the base URL
            response = await client.get("http://localhost:11434/")
            return response.status_code == 200
    except:
        return False

async def call_llm(prompt: str):
    payload = {
        "model": OLLAMA_MODEL,
        "prompt": f"{SYSTEM_PROMPT}\n\nPatient says: \"{prompt}\"\n\nOutput JSON:",
        "stream": False,
        "format": "json"
    }
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(OLLAMA_URL, json=payload)
            response.raise_for_status()
            result = response.json()
            return json.loads(result["response"])
    except Exception as e:
        logging.error(f"LLM Error: {str(e)}")
        # Graceful failure - returns a structure that forces a retry or fallback
        return {
            "intent": "other",
            "department": None,
            "symptoms": None,
            "urgency": "normal",
            "confidence": 0.0,
            "reply": "I'm having a little trouble understanding. Could you please say that again?"
        }
