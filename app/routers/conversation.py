from fastapi import APIRouter, HTTPException
from app.services.llm_service import call_llm
from pydantic import BaseModel
from typing import Optional

router = APIRouter(tags=["Conversational AI"])

class ConversationRequest(BaseModel):
    text: str
    language: str = "en"

@router.post("/conversation")
async def conversation(req: ConversationRequest):
    if not req.text.strip():
        raise HTTPException(400, "Empty text provided")
    
    # We only support English for LLM conversation currently
    if req.language != "en":
        return {
            "intent": "other",
            "reply": "I currently only support conversational triage in English. Please use the touch menu."
        }

    result = await call_llm(req.text)
    return result
