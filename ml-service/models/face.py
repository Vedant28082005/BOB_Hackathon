"""
InsightFace ArcFace (buffalo_l) for face matching between document photo and selfie.
Cosine similarity → match decision + confidence.
"""
from __future__ import annotations
from dataclasses import dataclass
from functools import lru_cache
from typing import Optional

import numpy as np
import structlog

log = structlog.get_logger(__name__)

try:
    import insightface
    from insightface.app import FaceAnalysis
    HAS_INSIGHTFACE = True
except ImportError:
    HAS_INSIGHTFACE = False
    log.warning("insightface not installed; face-match stage will return 0")


@lru_cache(maxsize=1)
def _get_face_app(model_name: str = "buffalo_l", use_gpu: bool = True) -> Optional["FaceAnalysis"]:
    if not HAS_INSIGHTFACE:
        return None
    try:
        providers = (["CUDAExecutionProvider", "CPUExecutionProvider"]
                     if use_gpu else ["CPUExecutionProvider"])
        app = FaceAnalysis(name=model_name, providers=providers)
        app.prepare(ctx_id=0 if use_gpu else -1, det_size=(640, 640))
        log.info("insightface_loaded", model=model_name)
        return app
    except Exception as e:
        log.error("insightface_load_failed", error=str(e))
        return None


def _bytes_to_cv2(image_bytes: bytes):
    import cv2
    arr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    return img


def _extract_embedding(app: "FaceAnalysis", image_bytes: bytes) -> Optional[np.ndarray]:
    img = _bytes_to_cv2(image_bytes)
    if img is None:
        return None
    faces = app.get(img)
    if not faces:
        return None
    # Use the largest detected face
    largest = max(faces, key=lambda f: (f.bbox[2]-f.bbox[0]) * (f.bbox[3]-f.bbox[1]))
    return largest.normed_embedding


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-10))


@dataclass
class FaceMatchResult:
    match_score: float = 0.0          # cosine similarity 0-1
    matched: bool = False
    doc_face_detected: bool = False
    selfie_face_detected: bool = False
    error: Optional[str] = None
    threshold_used: float = 0.40


def run_face_match(
    doc_image_bytes: bytes,
    selfie_bytes: bytes,
    model_name: str = "buffalo_l",
    threshold: float = 0.40,          # cosine distance; higher = more similar
    use_gpu: bool = True,
) -> FaceMatchResult:
    result = FaceMatchResult(threshold_used=threshold)

    app = _get_face_app(model_name, use_gpu)
    if app is None:
        result.error = "InsightFace not available (CPU-only or install missing)"
        return result

    try:
        doc_emb = _extract_embedding(app, doc_image_bytes)
        result.doc_face_detected = doc_emb is not None

        selfie_emb = _extract_embedding(app, selfie_bytes)
        result.selfie_face_detected = selfie_emb is not None

        if doc_emb is None or selfie_emb is None:
            result.error = (
                "No face in document" if doc_emb is None
                else "No face in selfie"
            )
            return result

        sim = cosine_similarity(doc_emb, selfie_emb)
        result.match_score = max(0.0, float(sim))
        result.matched = sim >= threshold

    except Exception as e:
        result.error = str(e)
        log.error("face_match_failed", error=str(e))

    return result
