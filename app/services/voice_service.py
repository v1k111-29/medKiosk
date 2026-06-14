import os
import whisper
from concurrent.futures import ThreadPoolExecutor
import asyncio

# Lazy load Whisper
_model = None
executor = ThreadPoolExecutor(max_workers=1) # Whisper is very heavy, usually 1 worker for local

def get_model():
    global _model
    if _model is None:
        print("[Voice] Loading Whisper model (base)...")
        _model = whisper.load_model("base")
    return _model

async def transcribe_async(audio_path: str, language: str = "ta"):
    loop = asyncio.get_event_loop()
    def _task():
        return get_model().transcribe(
            audio_path,
            language=language,
            prompt="This is Tamil and English conversation. நாம் பேசுவது தமிழ் மற்றும் ஆங்கிலம் mix.",
            fp16=False
        )
    return await loop.run_in_executor(executor, _task)
