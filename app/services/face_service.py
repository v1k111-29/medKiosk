import os
import io
import pickle
import base64
import numpy as np
from PIL import Image
from concurrent.futures import ThreadPoolExecutor
import asyncio

# Lazy load DeepFace
_deepface = None
executor = ThreadPoolExecutor(max_workers=4)

def get_df():
    global _deepface
    if _deepface is None:
        import logging
        os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"
        logging.getLogger("deepface").setLevel(logging.ERROR)
        from deepface import DeepFace
        _deepface = DeepFace
    return _deepface

def decode_image(data_url: str) -> np.ndarray:
    _, encoded = data_url.split(",", 1)
    img_bytes = base64.b64decode(encoded)
    img = Image.open(io.BytesIO(img_bytes)).convert("RGB")
    return np.array(img)

async def run_ai_task(func, *args, **kwargs):
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(executor, lambda: func(*args, **kwargs))

async def get_embedding_async(img: np.ndarray):
    def _task():
        try:
            print("[Face] Attempting detection with opencv...")
            result = get_df().represent(
                img_path=img,
                model_name="ArcFace",
                detector_backend="opencv",
                enforce_detection=True,
            )
            return np.array(result[0]["embedding"], dtype=np.float32)
        except Exception as e:
            print(f"[Face] Opencv detection failed: {str(e)}")
            try:
                print("[Face] Retrying with detector_backend='skip'...")
                result = get_df().represent(
                    img_path=img,
                    model_name="ArcFace",
                    detector_backend="skip", # Just use the center of the image
                    enforce_detection=False,
                )
                return np.array(result[0]["embedding"], dtype=np.float32)
            except Exception as e2:
                print(f"[Face] Skip detection also failed: {str(e2)}")
                return None
    return await run_ai_task(_task)

async def detect_gender_async(img: np.ndarray) -> str:
    def _task():
        try:
            result = get_df().analyze(
                img_path=img,
                actions=["gender"],
                detector_backend="opencv",
                enforce_detection=True,
                silent=True,
            )
            scores = result[0]["gender"]
            return "Man" if scores["Man"] >= scores["Woman"] else "Woman"
        except Exception:
            return "Unknown"
    return await run_ai_task(_task)

def cosine_dist(a: np.ndarray, b: np.ndarray) -> float:
    a = a / (np.linalg.norm(a) + 1e-9)
    b = b / (np.linalg.norm(b) + 1e-9)
    return float(1.0 - np.dot(a, b))
