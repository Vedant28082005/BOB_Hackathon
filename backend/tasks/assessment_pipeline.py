"""
Celery tasks for the async KYC pipeline.
Each task stage reports progress to Redis pub/sub so the frontend can poll.
"""
from __future__ import annotations
import base64
import hashlib
import json
import time
import uuid
from typing import Any

import httpx
from celery import Celery
from celery.utils.log import get_task_logger

from config import settings

celery_app = Celery(
    "trustlayer",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)
celery_app.conf.task_serializer = "json"
celery_app.conf.result_serializer = "json"
celery_app.conf.accept_content = ["json"]
celery_app.conf.task_track_started = True
celery_app.conf.task_acks_late = True

logger = get_task_logger(__name__)


def _pub(job_id: str, stage: str, pct: int, detail: str = "") -> None:
    """Publish progress update to Redis (sync version for Celery workers)."""
    import redis
    r = redis.from_url(settings.redis_url)
    r.set(f"job:{job_id}", json.dumps({"stage": stage, "pct": pct, "detail": detail}), ex=3600)
    r.publish(f"progress:{job_id}", json.dumps({"stage": stage, "pct": pct, "detail": detail}))


def _ml_post(endpoint: str, payload: dict) -> dict:
    """Call the ML inference service."""
    url = f"{settings.ml_service_url}/v1/ml/{endpoint}"
    with httpx.Client(timeout=settings.ml_timeout_seconds) as client:
        resp = client.post(url, json=payload,
                           headers={"X-API-Key": settings.ml_service_api_key})
        resp.raise_for_status()
        return resp.json()


@celery_app.task(bind=True, name="assessment.run_pipeline", max_retries=1)
def run_assessment_pipeline(self, job_id: str, request_data: dict) -> dict:
    """
    Full KYC pipeline. Stages:
      1. Document forensics + OCR   (20%)
      2. Biometric analysis         (40%)
      3. Device intelligence        (60%)
      4. Behavioural analysis       (75%)
      5. Identity graph             (90%)
      6. Fusion + LLM narration    (100%)
    """
    from engines.fusion import fuse
    from engines.device import analyse_device
    from engines.behavioural import analyse_behavioural
    from engines.identity_graph import analyse_graph
    from llm.gemini import generate_explanation
    import asyncio

    start = time.time()
    _pub(job_id, "document", 5, "Starting document forensics…")

    # ── Stage 1: Document ────────────────────────────────────────────────────
    doc_result = {"score": 50.0, "signals": {}, "flags": []}
    try:
        doc_payload = {
            "image_b64": request_data.get("doc_image_b64", ""),
            "doc_type":  request_data.get("doc_type", "UNKNOWN"),
            "id_number": request_data.get("pan_number", ""),
            "user_fields": {
                "name": request_data.get("full_name", ""),
                "dob":  request_data.get("dob", ""),
            },
            "lang": "en",
        }
        if doc_payload["image_b64"]:
            ml_doc = _ml_post("document", doc_payload)
            auth_pct = ml_doc["authenticity_score"]
            doc_score = auth_pct * 100
            doc_result = {
                "score": doc_score,
                "signals": {
                    "ocr_confidence": ml_doc["ocr_confidence"],
                    "ela_score": ml_doc["ela_score"],
                    "copy_move_score": ml_doc["copy_move_score"],
                    "noise_score": ml_doc["noise_score"],
                    "tampering_score": ml_doc["tampering_score"],
                    "authenticity_score": ml_doc["authenticity_score"],
                    "id_valid": ml_doc["id_valid"],
                    "id_message": ml_doc["id_message"],
                    "ocr_fields": ml_doc["ocr_fields"],
                },
                "flags": ml_doc["anomaly_flags"],
            }
    except Exception as e:
        logger.warning(f"ML document stage failed: {e}; using fallback score")
        doc_result = {"score": 60.0, "signals": {"error": str(e)}, "flags": ["DOC_ML_UNAVAILABLE"]}

    _pub(job_id, "biometric", 25, "Running biometric checks…")

    # ── Stage 2: Biometric ───────────────────────────────────────────────────
    bio_result = {"score": 50.0, "signals": {}, "flags": []}
    try:
        bio_payload = {
            "doc_image_b64": request_data.get("doc_image_b64", ""),
            "selfie_b64":    request_data.get("selfie_b64", ""),
            "video_frames_b64": request_data.get("video_frames_b64", []),
        }
        if bio_payload["selfie_b64"]:
            ml_bio = _ml_post("biometric", bio_payload)
            # Compute bio score
            face_w, live_w, dfake_w = 0.40, 0.35, 0.25
            face_score  = ml_bio["face_match_score"] * 100
            live_score  = ml_bio["liveness_score"] * 100
            dfake_score = (1.0 - ml_bio["deepfake_probability"]) * 100

            bio_score = face_w * face_score + live_w * live_score + dfake_w * dfake_score
            flags = []
            if not ml_bio["face_matched"]:
                flags.append("FACE_MISMATCH")
            if not ml_bio["liveness_combined"]:
                flags.append("LIVENESS_FAIL")
            if ml_bio["is_deepfake"]:
                flags.append("BIO_DEEPFAKE")
            bio_result = {
                "score": bio_score,
                "signals": {
                    "face_match_score": ml_bio["face_match_score"],
                    "liveness_score": ml_bio["liveness_score"],
                    "deepfake_probability": ml_bio["deepfake_probability"],
                    "gan_artifact_score": ml_bio["gan_artifact_score"],
                    "liveness_passive": ml_bio["liveness_passive"],
                    "liveness_active_passed": ml_bio["liveness_active_passed"],
                },
                "flags": flags,
            }
    except Exception as e:
        logger.warning(f"ML biometric stage failed: {e}; using fallback")
        bio_result = {"score": 60.0, "signals": {"error": str(e)}, "flags": ["BIO_ML_UNAVAILABLE"]}

    _pub(job_id, "device", 45, "Analysing device signals…")

    # ── Stage 3: Device ──────────────────────────────────────────────────────
    device_signals = request_data.get("device", {})
    ip_address = request_data.get("ip_address", "")
    dev_result = analyse_device(device_signals, ip_address)

    _pub(job_id, "behavioural", 60, "Scoring behavioural biometrics…")

    # ── Stage 4: Behavioural ─────────────────────────────────────────────────
    beh_signals = request_data.get("behavioural", {})
    beh_result = analyse_behavioural(beh_signals)

    _pub(job_id, "identity_graph", 75, "Querying identity graph…")

    # ── Stage 5: Identity graph (Neo4j) ──────────────────────────────────────
    applicant_id = request_data.get("applicant_id", str(uuid.uuid4()))
    graph_result = asyncio.run(
        analyse_graph(
            applicant_id=applicant_id,
            email_hash=_sha256(request_data.get("email", "")),
            phone_hash=_sha256(request_data.get("phone", "")),
            pan_hash=_sha256(request_data.get("pan_number", "")),
            device_fingerprint=device_signals.get("fingerprint", ""),
            ip_address=ip_address,
            name=request_data.get("full_name", ""),
        )
    )

    _pub(job_id, "fusion", 88, "Computing trust score…")

    # ── Stage 6: Fusion ──────────────────────────────────────────────────────
    weights = {
        "document":       settings.weight_document,
        "biometric":      settings.weight_biometric,
        "device":         settings.weight_device,
        "behavioural":    settings.weight_behavioural,
        "identity_graph": settings.weight_identity_graph,
    }
    thresholds = {
        "approve":        settings.threshold_approve,
        "step_up":        settings.threshold_step_up,
        "manual_review":  settings.threshold_manual_review,
    }

    pipeline = {
        "document":       doc_result,
        "biometric":      bio_result,
        "device":         dev_result,
        "behavioural":    beh_result,
        "identity_graph": graph_result,
    }

    fusion = fuse(pipeline, weights, thresholds)

    # ── LLM explanation ───────────────────────────────────────────────────────
    llm_explanation = generate_explanation(
        fusion["trust_score"], fusion["decision"], fusion["reason_codes"],
        pipeline, request_data.get("full_name", "Applicant"),
    )

    elapsed = int((time.time() - start) * 1000)
    _pub(job_id, "complete", 100, "Assessment complete")

    return {
        "job_id": job_id,
        "applicant_id": applicant_id,
        "trust_score": fusion["trust_score"],
        "risk_band": fusion["risk_band"],
        "decision": fusion["decision"],
        "reason_codes": fusion["reason_codes"],
        "pipeline": pipeline,
        "graph_data": graph_result.get("graph_data", {}),
        "llm_explanation": llm_explanation,
        "processing_time_ms": elapsed,
        "data_retained": [
            "Applicant name (encrypted)", "Email hash (SHA-256)", "Phone hash (SHA-256)",
            "PAN hash (SHA-256)", "Document type", "Date of birth",
            "Device fingerprint hash", "Assessment decision", "Trust score",
            "Reason codes", "Audit log entry", "Assessment timestamp",
            "Fusion weights snapshot", "LLM explanation",
        ],
        "data_discarded": [
            "Raw document image (purged after hashing)",
            "Raw selfie image (purged after hashing)",
            "Keystroke timing raw samples (aggregated only)",
            "Full IP address (geo-region retained only)",
            "OCR full text (structured fields only retained)",
            "Video frames (analyzed, not stored)",
            "EXIF metadata (flags only retained)",
        ],
    }


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest() if value else ""
