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
- Detectors: YuNet (fast, accurate) → OpenCV Haar fallback. The LARGEST face is used.
- align=True: corrects roll/tilt before embedding — major accuracy boost.
- Optional anti-spoofing (MiniFASNet): a face that looks like a photo/screen is
  never matched; the kiosk sends that visitor to phone check-in instead.
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

from app.core.config import settings

logger = logging.getLogger("kiosk.face")

# ── Constants ─────────────────────────────────────────────────────────────────
MAX_IMAGE_SIZE        = 5 * 1024 * 1024   # 5 MB
ALLOWED_IMAGE_FORMATS = {"JPEG", "PNG", "BMP"}

# ArcFace cosine distance threshold.
# Same person across angles/lighting: typically 0.10–0.42
# Different people:                   0.50–1.0
# 0.45 gives a comfortable same-person margin while rejecting impostors.
MATCH_THRESHOLD       = settings.FACE_MATCH_THRESHOLD

# Maximum embeddings to store per patient (multi-shot gallery)
MAX_GALLERY_SIZE      = settings.FACE_GALLERY_SIZE

_deepface = None
executor  = ThreadPoolExecutor(max_workers=4)


def get_df():
    """Lazy-load DeepFace (heavy: TensorFlow). Raises ImportError if not installed."""
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
        logger.debug("[Face] base64 decode failed: %s", e)
        raise ValueError("Invalid image data")

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
        logger.debug("[Face] image decode failed: %s", e)
        raise ValueError("Corrupt or unreadable image")


# ── Async helper ──────────────────────────────────────────────────────────────

async def run_ai_task(func, *args, **kwargs):
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(executor, lambda: func(*args, **kwargs))


# ── Errors ────────────────────────────────────────────────────────────────────

class FaceEngineError(RuntimeError):
    """The face engine itself failed (not installed, model load, download, crash).

    Never reported to the patient as "no face": the kiosk must offer phone check-in.
    """


class SpoofSuspected(Exception):
    """The largest face looks like a photo or screen, not a live person."""


# ── Face detection + embedding ───────────────────────────────────────────────

# Detector chain. YuNet (OpenCV DNN, ~0.1 s on CPU) is accurate and rarely
# returns false faces; the Haar-cascade "opencv" detector is the fallback.
# RetinaFace is NOT used: it takes 20-30 s per frame on a kiosk CPU.
DETECTORS = ("yunet", "opencv")
MIN_FACE_PX = 60   # ignore tiny detections (background people, posters, noise)


def _largest_face(faces: list) -> Optional[dict]:
    """Pick the biggest face: at a kiosk that is the person standing at the screen."""
    faces = [f for f in faces
             if min(f["facial_area"]["w"], f["facial_area"]["h"]) >= MIN_FACE_PX]
    if not faces:
        return None
    return max(faces, key=lambda f: f["facial_area"]["w"] * f["facial_area"]["h"])


def _to_bgr(img: np.ndarray) -> np.ndarray:
    """DeepFace treats numpy input as BGR (OpenCV order); decode_image returns RGB."""
    return np.ascontiguousarray(img[:, :, ::-1])


def _detect_largest(df, bgr: np.ndarray, anti_spoofing: bool) -> Optional[dict]:
    from deepface.modules.exceptions import FaceNotDetected

    for backend in DETECTORS:
        try:
            faces = df.extract_faces(
                img_path=bgr,
                detector_backend=backend,
                enforce_detection=True,
                align=True,            # corrects face roll/tilt
                anti_spoofing=anti_spoofing,
            )
        except FaceNotDetected:
            logger.debug("[Face] %s: no face", backend)
            continue
        face = _largest_face(faces)
        if face is not None:
            face["detector"] = backend
            return face
    return None


def embed_image(img: np.ndarray, anti_spoofing: Optional[bool] = None) -> Optional[np.ndarray]:
    """512-dim ArcFace embedding of the LARGEST face in an RGB image (blocking).

    Returns None when no face is found. Raises SpoofSuspected when anti-spoofing
    is on and that face looks like a photo/screen, FaceEngineError when the
    engine itself fails.
    """
    if anti_spoofing is None:
        anti_spoofing = settings.FACE_ANTI_SPOOFING
    try:
        df = get_df()
        face = _detect_largest(df, _to_bgr(img), anti_spoofing)
        if face is None:
            return None
        if anti_spoofing and face.get("is_real") is False:
            logger.warning("[Face] Spoof suspected (score=%.2f, detector=%s)",
                           float(face.get("antispoof_score", 0)), face["detector"])
            raise SpoofSuspected()
        # extract_faces returns the aligned crop as RGB float [0,1]; embed it directly.
        crop = _to_bgr((face["face"] * 255).astype(np.uint8))
        result = df.represent(img_path=crop, model_name="ArcFace", detector_backend="skip")
        emb = np.array(result[0]["embedding"], dtype=np.float32)
        logger.debug("[Face] Embedding via %s, face=%sx%s", face["detector"],
                     face["facial_area"]["w"], face["facial_area"]["h"])
        return emb
    except SpoofSuspected:
        raise
    except Exception as e:
        logger.error("[Face] Face engine error: %s: %s", type(e).__name__, e)
        raise FaceEngineError(str(e)) from e


async def get_embedding_async(img: np.ndarray, anti_spoofing: Optional[bool] = None) -> Optional[np.ndarray]:
    return await run_ai_task(embed_image, img, anti_spoofing)


# ── Gender detection ──────────────────────────────────────────────────────────

async def detect_gender_async(img: np.ndarray) -> str:
    """Best effort; "Unknown" on any failure (gender is only a form pre-fill)."""

    def _task():
        try:
            df = get_df()
            bgr = _to_bgr(img)
            for backend in DETECTORS:
                try:
                    result = df.analyze(img_path=bgr, actions=["gender"], detector_backend=backend,
                                        enforce_detection=True, silent=True)
                except ValueError:
                    continue
                biggest = max(result, key=lambda r: r["region"]["w"] * r["region"]["h"])
                scores = biggest["gender"]
                return "Man" if scores["Man"] >= scores["Woman"] else "Woman"
        except Exception as e:
            logger.warning("[Face] Gender detection failed: %s", e)
        return "Unknown"

    return await run_ai_task(_task)


# ── Model warm-up / prefetch ─────────────────────────────────────────────────

_warm_state = {"state": "not_started", "error": None}


def warm_state() -> dict:
    return dict(_warm_state)


def warm_up() -> None:
    """Load (and on first run download, ~800 MB) every model the kiosk uses.

    Blocking. Run at server start in the background, or ahead of time with
    `python -m app.services.face_service` (start.bat does this after install).
    """
    _warm_state.update(state="warming", error=None)
    try:
        df = get_df()
        dummy = np.zeros((224, 224, 3), dtype=np.uint8)
        df.build_model(model_name="ArcFace")
        df.build_model(model_name="Gender", task="facial_attribute")
        for backend in DETECTORS:
            df.extract_faces(img_path=dummy, detector_backend=backend, enforce_detection=False,
                             anti_spoofing=settings.FACE_ANTI_SPOOFING)
        df.represent(img_path=dummy, model_name="ArcFace", detector_backend="skip")
        _warm_state.update(state="ready")
    except Exception as e:
        _warm_state.update(state="failed", error=f"{type(e).__name__}: {e}")
        raise


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


if __name__ == "__main__":
    # Prefetch all face models (used by start.bat after the first install).
    import sys

    from app.core.utf8_console import force_utf8_console

    force_utf8_console()
    logging.basicConfig(level=logging.INFO)
    print("Downloading/loading face models (first time ~800 MB)...", flush=True)
    try:
        warm_up()
    except Exception as e:
        print(f"Face model prefetch failed: {e}", flush=True)
        sys.exit(1)
    print("Face models ready.", flush=True)
