"""
Face Recognition Service — DeepFace with ArcFace embeddings.

Key design decisions:
- NO pre-processing (CLAHE etc.) before embedding: ArcFace is internally
  lighting-robust. Adding CLAHE BEFORE the model changes pixel values and
  causes stored vs query embedding drift, which is the #1 cause of false
  "new patient" results.
- Threshold 0.45: empirically validated for ArcFace cosine distance.
  Same person (frontal + angle/lighting): 0.10–0.42
  Different people:                       0.50–1.0
  Buffer zone at 0.45 gives safety without false positives.
- Dual detector: opencv (fast) → retinaface fallback (low-light/off-angle).
- align=True: corrects roll/tilt before embedding — major accuracy boost.
- Multi-shot gallery: up to 5 embeddings per patient, matched with min-dist.
"""

import os
import io
import base64
import logging
import asyncio
import numpy as np
from PIL import Image
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

logger = logging.getLogger("kiosk.face")

# ── Constants ─────────────────────────────────────────────────────────────────
MAX_IMAGE_SIZE        = 5 * 1024 * 1024   # 5 MB
ALLOWED_IMAGE_FORMATS = {"JPEG", "PNG", "BMP"}

# ArcFace cosine distance threshold.
# Same person across angles/lighting: typically 0.10–0.42
# Different people:                   0.50–1.0
# 0.45 gives a comfortable same-person margin while rejecting impostors.
MATCH_THRESHOLD       = float(os.getenv("FACE_MATCH_THRESHOLD", "0.45"))

# Maximum embeddings to store per patient (multi-shot gallery)
MAX_GALLERY_SIZE      = int(os.getenv("FACE_GALLERY_SIZE", "5"))

_deepface = None
executor  = ThreadPoolExecutor(max_workers=4)


def get_df():
    """Lazy-load DeepFace."""
    global _deepface
    if _deepface is None:
        os.environ["TF_CPP_MIN_LOG_LEVEL"]  = "3"
        os.environ["TF_ENABLE_ONEDNN_OPTS"] = "0"
        logging.getLogger("deepface").setLevel(logging.ERROR)
        logging.getLogger("tensorflow").setLevel(logging.ERROR)
        from deepface import DeepFace
        _deepface = DeepFace
    return _deepface


# ── Image decode (pure — NO pre-processing) ───────────────────────────────────

def decode_image(data_url: str) -> np.ndarray:
    """
    Decode base64 data URL to RGB numpy array.

    IMPORTANT: Do NOT apply CLAHE, histogram equalisation, or any pixel
    transforms here. ArcFace's internal backbone handles lighting normalisation.
    Applying CLAHE before the model creates embedding drift: stored embeddings
    (computed without CLAHE) will NOT match query embeddings (computed with
    CLAHE), causing the same person to register as new every time.
    """
    if not isinstance(data_url, str) or "," not in data_url:
        raise ValueError("Invalid image: must be a base64 data URL")

    try:
        _, encoded = data_url.split(",", 1)
        img_bytes  = base64.b64decode(encoded, validate=True)
    except Exception as e:
        raise ValueError(f"Invalid base64: {e}")

    if len(img_bytes) > MAX_IMAGE_SIZE:
        raise ValueError(f"Image too large (max {MAX_IMAGE_SIZE // 1024 // 1024} MB)")

    try:
        img = Image.open(io.BytesIO(img_bytes))
        if img.format and img.format not in ALLOWED_IMAGE_FORMATS:
            raise ValueError(f"Unsupported format: {img.format}")
        return np.array(img.convert("RGB"))
    except ValueError:
        raise
    except Exception as e:
        raise ValueError(f"Corrupt image: {e}")


# ── Async helper ──────────────────────────────────────────────────────────────

async def run_ai_task(func, *args, **kwargs):
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(executor, lambda: func(*args, **kwargs))


# ── Embedding extraction — dual detector ─────────────────────────────────────

async def get_embedding_async(img: np.ndarray) -> Optional[np.ndarray]:
    """
    Extract 512-dim ArcFace embedding.

    1. Try opencv (fast, good in normal lighting, ~0.1s)
    2. Fall back to retinaface (robust in low light / angles, ~0.5s)
    3. Return None only if both fail (genuine no-face frame)
    """

    def _task():
        df = get_df()

        for backend in ("opencv", "retinaface"):
            try:
                result = df.represent(
                    img_path=img,
                    model_name="ArcFace",
                    detector_backend=backend,
                    enforce_detection=True,
                    align=True,          # corrects face roll/tilt
                )
                emb = np.array(result[0]["embedding"], dtype=np.float32)
                logger.debug(f"[Face] Embedding via {backend}, norm={float(np.linalg.norm(emb)):.3f}")
                return emb
            except Exception as e:
                logger.debug(f"[Face] {backend} failed: {e}")

        logger.warning("[Face] Both detectors failed — no face in frame")
        return None

    return await run_ai_task(_task)


# ── Gender detection ──────────────────────────────────────────────────────────

async def detect_gender_async(img: np.ndarray) -> str:

    def _task():
        df = get_df()
        for backend in ("opencv", "retinaface"):
            try:
                result = df.analyze(
                    img_path=img,
                    actions=["gender"],
                    detector_backend=backend,
                    enforce_detection=True,
                    silent=True,
                )
                scores = result[0]["gender"]
                return "Man" if scores["Man"] >= scores["Woman"] else "Woman"
            except Exception:
                continue
        return "Unknown"

    return await run_ai_task(_task)


# ── Distance helpers ──────────────────────────────────────────────────────────

def cosine_dist(a: np.ndarray, b: np.ndarray) -> float:
    """Cosine distance [0, 2]. Lower = more similar."""
    try:
        a  = np.asarray(a, dtype=np.float32)
        b  = np.asarray(b, dtype=np.float32)
        an = np.linalg.norm(a) + 1e-9
        bn = np.linalg.norm(b) + 1e-9
        return float(1.0 - np.dot(a / an, b / bn))
    except Exception as e:
        logger.error(f"cosine_dist error: {e}")
        return 1.0


def best_gallery_distance(query: np.ndarray, gallery: list) -> float:
    """Minimum cosine distance between query and all gallery embeddings."""
    if not gallery:
        return 1.0
    return min(cosine_dist(query, g) for g in gallery)


# ── Serialisation ─────────────────────────────────────────────────────────────

def serialize_embedding(embedding: np.ndarray) -> bytes:
    return embedding.astype(np.float32).tobytes()


def deserialize_embedding(data) -> Optional[np.ndarray]:
    try:
        if not isinstance(data, (bytes, memoryview)) or len(data) == 0:
            return None
        if len(data) != 512 * 4:
            logger.warning(f"[Face] Bad embedding size: {len(data)}B (expected {512*4}B)")
            return None
        return np.frombuffer(data, dtype=np.float32).copy()
    except Exception as e:
        logger.error(f"[Face] Deserialize error: {e}")
        return None
