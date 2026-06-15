"""Assessment router — async Celery-backed pipeline with SSE progress streaming."""
from __future__ import annotations
import hashlib
import json
import uuid
from typing import AsyncIterator

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from config import settings
from security.auth import get_current_user, CurrentUser
from storage.redis_client import get_job_status, set_job_status, rate_limit_check, get_redis
from tasks.assessment_pipeline import run_assessment_pipeline

router = APIRouter()


class AssessmentRequest(BaseModel):
    full_name: str
    email: str
    phone: str
    dob: str
    address: str = ""
    pan_number: str
    doc_type: str = "AADHAAR"
    doc_name_on_doc: str = ""
    doc_image_b64: str = ""
    selfie_b64: str = ""
    video_frames_b64: list[str] = []
    device: dict = Field(default_factory=dict)
    behavioural: dict = Field(default_factory=dict)
    webhook_url: str = ""
    scenario: str = ""


def _sha256(v: str) -> str:
    return hashlib.sha256(v.encode()).hexdigest()


@router.post("", status_code=202)
async def submit_assessment(
    req: AssessmentRequest,
    request: Request,
    user: CurrentUser = Depends(get_current_user),
):
    if not await rate_limit_check(f"assessment:{user.sub}"):
        raise HTTPException(429, "Rate limit exceeded")

    job_id = str(uuid.uuid4())
    applicant_id = str(uuid.uuid4())
    ip_address = request.client.host if request.client else ""

    # Upload media to MinIO (transient; auto-purged after retention period)
    if req.doc_image_b64:
        import base64
        from storage.minio_client import upload_media
        doc_bytes = base64.b64decode(req.doc_image_b64)
        await upload_media(doc_bytes, "image/jpeg", applicant_id, "document")

    if req.selfie_b64:
        import base64
        from storage.minio_client import upload_media
        selfie_bytes = base64.b64decode(req.selfie_b64)
        await upload_media(selfie_bytes, "image/jpeg", applicant_id, "selfie")

    task_payload = req.model_dump()
    task_payload["applicant_id"] = applicant_id
    task_payload["ip_address"] = ip_address
    task_payload["submitted_by"] = user.sub

    run_assessment_pipeline.apply_async(args=[job_id, task_payload], task_id=job_id)
    await set_job_status(job_id, {"stage": "QUEUED", "pct": 0, "detail": "Pipeline queued"})

    return {
        "job_id": job_id,
        "applicant_id": applicant_id,
        "status": "QUEUED",
        "stream_url": f"/v1/assessments/{job_id}/stream",
        "result_url": f"/v1/assessments/{job_id}/result",
    }


@router.get("/{job_id}/status")
async def get_status(job_id: str, _: CurrentUser = Depends(get_current_user)):
    s = await get_job_status(job_id)
    if not s:
        raise HTTPException(404, "Job not found")
    return s


@router.get("/{job_id}/stream")
async def stream_progress(job_id: str, _: CurrentUser = Depends(get_current_user)):
    async def _gen() -> AsyncIterator[str]:
        r = await get_redis()
        pubsub = r.pubsub()
        await pubsub.subscribe(f"progress:{job_id}")
        try:
            async for msg in pubsub.listen():
                if msg["type"] == "message":
                    yield f"data: {msg['data']}\n\n"
                    if json.loads(msg["data"]).get("pct", 0) >= 100:
                        break
        finally:
            await pubsub.unsubscribe(f"progress:{job_id}")

    return StreamingResponse(_gen(), media_type="text/event-stream")


@router.get("/{job_id}/result")
async def get_result(job_id: str, _: CurrentUser = Depends(get_current_user)):
    from celery.result import AsyncResult
    from tasks.assessment_pipeline import celery_app

    result = AsyncResult(job_id, app=celery_app)
    if result.state == "PENDING":
        return {"status": "PENDING"}
    if result.state == "FAILURE":
        raise HTTPException(500, f"Pipeline failed: {result.info}")
    if result.state == "SUCCESS":
        return {"status": "SUCCESS", **result.result}
    return {"status": result.state}
