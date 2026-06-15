"""ML Service API routes — called internally by the backend Celery workers."""
from __future__ import annotations
import base64
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Header
from pydantic import BaseModel

from config import settings
from models.ocr import run_ocr
from models.document_forensics import run_forensics
from models.face import run_face_match
from models.liveness import run_liveness
from models.deepfake import run_deepfake_detection

router = APIRouter(prefix="/v1/ml")


def _auth(x_api_key: str = Header(...)):
    if x_api_key != settings.internal_api_key:
        raise HTTPException(401, "Invalid internal API key")


# ── Request / response schemas ─────────────────────────────────────────────────
class DocumentRequest(BaseModel):
    image_b64: str          # base64-encoded image bytes
    doc_type: str = "UNKNOWN"
    id_number: str = ""
    user_fields: dict = {}   # name, dob, etc from the form
    lang: str = "en"


class DocumentResponse(BaseModel):
    ocr_text: str
    ocr_confidence: float
    ocr_fields: dict
    ela_score: float
    exif_flags: list[str]
    copy_move_score: float
    noise_score: float
    tampering_score: float
    authenticity_score: float
    id_valid: bool
    id_message: str
    field_cross_check: dict
    anomaly_flags: list[str]


class BiometricRequest(BaseModel):
    doc_image_b64: str       # document photo for face extraction
    selfie_b64: str
    video_frames_b64: list[str] = []   # optional frames for active liveness


class BiometricResponse(BaseModel):
    face_match_score: float
    face_matched: bool
    liveness_passive_score: float
    liveness_passive: bool
    liveness_active_passed: bool
    liveness_combined: bool
    liveness_score: float
    deepfake_probability: float
    is_deepfake: bool
    gan_artifact_score: float
    deepfake_note: str
    errors: list[str]


# ── Endpoints ──────────────────────────────────────────────────────────────────
@router.post("/document", response_model=DocumentResponse)
async def analyse_document(req: DocumentRequest, _=Depends(_auth)):
    img_bytes = base64.b64decode(req.image_b64)

    # OCR
    ocr = run_ocr(img_bytes, req.doc_type, settings.use_gpu, req.lang)

    # Forensics (ELA, EXIF, copy-move, noise, ID checksum, field cross-check)
    forensics = run_forensics(
        image_bytes=img_bytes,
        doc_type=req.doc_type,
        id_number=req.id_number,
        ocr_fields=ocr.fields,
        user_fields=req.user_fields,
        ela_quality=settings.ela_quality,
    )

    return DocumentResponse(
        ocr_text=ocr.raw_text,
        ocr_confidence=ocr.confidence,
        ocr_fields=ocr.fields,
        ela_score=forensics.ela_score,
        exif_flags=forensics.exif_flags,
        copy_move_score=forensics.copy_move_score,
        noise_score=forensics.noise_score,
        tampering_score=forensics.tampering_score,
        authenticity_score=forensics.authenticity_score,
        id_valid=forensics.id_valid,
        id_message=forensics.id_message,
        field_cross_check=forensics.field_cross_check,
        anomaly_flags=forensics.anomaly_flags,
    )


@router.post("/biometric", response_model=BiometricResponse)
async def analyse_biometric(req: BiometricRequest, _=Depends(_auth)):
    doc_bytes = base64.b64decode(req.doc_image_b64)
    selfie_bytes = base64.b64decode(req.selfie_b64)
    video_frames = [base64.b64decode(f) for f in req.video_frames_b64]

    models_dir = settings.models_dir
    errors: list[str] = []

    # Face match
    face = run_face_match(doc_bytes, selfie_bytes,
                          settings.insightface_model, settings.face_match_threshold,
                          settings.use_gpu)
    if face.error:
        errors.append(f"face_match: {face.error}")

    # Liveness
    liveness = run_liveness(selfie_bytes, video_frames, models_dir, settings.use_gpu)
    if liveness.error:
        errors.append(f"liveness: {liveness.error}")

    # Deepfake
    deepfake = run_deepfake_detection(selfie_bytes, video_frames, models_dir,
                                      settings.deepfake_threshold, settings.use_gpu)
    if deepfake.error:
        errors.append(f"deepfake: {deepfake.error}")

    return BiometricResponse(
        face_match_score=face.match_score,
        face_matched=face.matched,
        liveness_passive_score=liveness.passive_score,
        liveness_passive=liveness.passive_live,
        liveness_active_passed=liveness.active.challenge_passed,
        liveness_combined=liveness.combined_live,
        liveness_score=liveness.combined_score,
        deepfake_probability=deepfake.deepfake_probability,
        is_deepfake=deepfake.is_deepfake,
        gan_artifact_score=deepfake.gan_artifact_score,
        deepfake_note=deepfake.note,
        errors=errors,
    )


@router.get("/health")
async def health():
    return {"status": "ok", "gpu": settings.use_gpu}
