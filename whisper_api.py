import os
import tempfile
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import whisper

app = FastAPI(title="Voice Transcriber API — Local Whisper")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Load model on startup (base = ~140MB, small = ~460MB, medium = ~1.5GB)
# First run downloads the model automatically
print("Loading Whisper model (base)...")
model = whisper.load_model("base")
print("✓ Whisper ready")

# Supported MIME → extension mapping
MIME_TO_EXT = {
    "audio/webm":         ".webm",
    "audio/webm;codecs=opus": ".webm",
    "audio/ogg":          ".ogg",
    "audio/ogg;codecs=opus": ".ogg",
    "audio/mp4":          ".mp4",
    "audio/mpeg":         ".mp3",
    "audio/wav":          ".wav",
    "audio/x-wav":        ".wav",
}

@app.get("/health")
def health_check():
    return {"status": "ok", "model": "whisper-base-local"}


@app.post("/transcribe")
async def transcribe_audio(audio: UploadFile = File(...)):
    """
    Accept an audio file and transcribe with local Whisper.
    Supports Tamil (ta) and English (en) — auto-detected.
    """
    content_type = (audio.content_type or "audio/webm").split(";")[0].strip()
    ext = MIME_TO_EXT.get(audio.content_type, MIME_TO_EXT.get(content_type, ".webm"))

    with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
        raw = await audio.read()
        if not raw:
            raise HTTPException(status_code=400, detail="Empty audio file received.")
        tmp.write(raw)
        tmp_path = tmp.name

    try:
        # Transcribe with local Whisper
        # fp16=False prevents the "FP16 is not supported on CPU" warning
        result = model.transcribe(
            tmp_path, 
            language="ta",  # Bias toward Tamil
            prompt="This is Tamil and English conversation. நாம் பேசுவது தமிழ் மற்றும் ஆங்கிலம் mix.",
            fp16=False
        )
       
        
        return {
            "transcription": result["text"].strip(),
            "status": "success",
            "bytes_received": len(raw),
            "language": result.get("language", "unknown"),
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
