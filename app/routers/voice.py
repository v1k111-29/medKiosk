from fastapi import APIRouter, File, UploadFile, HTTPException
import tempfile
import os
from app.services.voice_service import transcribe_async
from app.core.errors import KioskError

router = APIRouter(tags=["Voice Transcription"])

MIME_TO_EXT = {
    "audio/webm": ".webm",
    "audio/webm;codecs=opus": ".webm",
    "audio/ogg": ".ogg",
    "audio/ogg;codecs=opus": ".ogg",
    "audio/mp4": ".mp4",
    "audio/mpeg": ".mp3",
    "audio/wav": ".wav",
    "audio/x-wav": ".wav",
}

@router.post("/transcribe")
async def transcribe(audio: UploadFile = File(...)):
    print(f"[Voice] Received transcription request: {audio.filename}, type: {audio.content_type}")
    content_type = (audio.content_type or "audio/webm").split(";")[0].strip()
    ext = MIME_TO_EXT.get(content_type, ".webm")

    with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
        raw = await audio.read()
        if not raw or len(raw) < 1000:
            print(f"[Voice] Rejected: file too small ({len(raw)} bytes)")
            raise KioskError(
                "Recording too short. Please hold the button longer.",
                "பதிவு மிகக் குறுகியது. தயவுசெய்து பொத்தானை நீண்ட நேரம் அழுத்தவும்.",
                status_code=400
            )
        tmp.write(raw)
        tmp_path = tmp.name

    try:
        result = await transcribe_async(tmp_path)
        return {
            "transcription": result["text"].strip(),
            "status": "success",
            "language": result.get("language", "unknown"),
        }
    except Exception as e:
        import traceback
        print(f"[Voice] Transcription Error: {str(e)}")
        traceback.print_exc()
        raise KioskError(
            "Voice processing failed. Please speak clearly.",
            "குரல் செயலாக்கம் தோல்வியடைந்தது. தயவுசெய்து தெளிவாகப் பேசவும்.",
            status_code=500
        )
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
