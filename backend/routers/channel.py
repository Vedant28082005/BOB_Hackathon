"""
Channel integration API — for mobile app / net-banking / branch / video-KYC channels.
Uses API-key + HMAC signing instead of OAuth2 JWT.
Returns clean {trust_score, risk_band, decision, reason_codes, assessment_id} envelope.
Supports webhook callback for async results.
"""
from __future__ import annotations
import asyncio
import ipaddress
import json
import socket
import uuid
from typing import Optional
from urllib.parse import urlparse

import httpx
from fastapi import APIRouter, BackgroundTasks, Header, HTTPException
from pydantic import BaseModel, HttpUrl, Field

from config import settings
from storage.redis_client import get_redis, set_job_status
from tasks.assessment_pipeline import run_assessment_pipeline

router = APIRouter()


# ── Simple API-key store (production: PostgreSQL channel_keys table) ──────────
_CHANNEL_KEYS: dict[str, dict] = {
    "ch_mobile_prod_key_001": {
        "secret": "ch_mobile_hmac_secret_001",
        "channel": "MOBILE",
        "name": "TrustLayer Mobile App",
    },
    "ch_branch_prod_key_001": {
        "secret": "ch_branch_hmac_secret_001",
        "channel": "BRANCH",
        "name": "Branch KYC Terminal",
    },
}


def _verify_api_key(key: str) -> dict:
    info = _CHANNEL_KEYS.get(key)
    if not info:
        raise HTTPException(401, "Invalid API key")
    return info


def _validate_callback_url(url: str) -> None:
    """
    Block SSRF: the callback URL must be http(s) and must not resolve to a
    private, loopback, link-local, or reserved address (e.g. cloud metadata
    at 169.254.169.254 or internal services). Raises HTTPException on reject.
    """
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise HTTPException(400, "callback_url must use http or https")
    host = parsed.hostname
    if not host:
        raise HTTPException(400, "callback_url has no host")
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror:
        raise HTTPException(400, "callback_url host could not be resolved")
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if (ip.is_private or ip.is_loopback or ip.is_link_local
                or ip.is_reserved or ip.is_multicast or ip.is_unspecified):
            raise HTTPException(400, "callback_url resolves to a disallowed address")


class ChannelAssessmentRequest(BaseModel):
    full_name: str
    email: str
    phone: str
    dob: str
    pan_number: str
    doc_type: str = "AADHAAR"
    doc_image_b64: str = ""
    selfie_b64: str = ""
    device: dict = Field(default_factory=dict)
    callback_url: Optional[str] = None  # webhook for async result


class ChannelResult(BaseModel):
    assessment_id: str
    trust_score: float
    risk_band: str
    decision: str
    reason_codes: list[dict]
    processing_time_ms: int


@router.post("/assess", response_model=dict, status_code=202)
async def channel_assess(
    req: ChannelAssessmentRequest,
    background_tasks: BackgroundTasks,
    x_tl_api_key: str = Header(...),
):
    channel_info = _verify_api_key(x_tl_api_key)

    # SSRF guard: validate the webhook target before accepting the job.
    if req.callback_url:
        _validate_callback_url(req.callback_url)

    job_id = str(uuid.uuid4())
    applicant_id = str(uuid.uuid4())

    task_payload = req.model_dump()
    task_payload["applicant_id"] = applicant_id
    task_payload["channel"] = channel_info["channel"]

    run_assessment_pipeline.apply_async(args=[job_id, task_payload], task_id=job_id)
    await set_job_status(job_id, {"stage": "QUEUED", "pct": 0})

    # Fire webhook when complete if callback_url provided
    if req.callback_url:
        background_tasks.add_task(
            _fire_webhook_when_done, job_id, req.callback_url, channel_info
        )

    return {
        "assessment_id": job_id,
        "status": "QUEUED",
        "poll_url": f"/v1/assessments/{job_id}/result",
    }


async def _fire_webhook_when_done(job_id: str, callback_url: str, channel_info: dict):
    """Poll Celery result and POST to webhook when pipeline completes."""
    from celery.result import AsyncResult
    from tasks.assessment_pipeline import celery_app

    for _ in range(120):    # wait up to 120 seconds
        await asyncio.sleep(1)
        result = AsyncResult(job_id, app=celery_app)
        if result.state == "SUCCESS":
            payload = {
                "assessment_id": job_id,
                "channel": channel_info["channel"],
                **result.result,
            }
            try:
                # Re-validate before sending (defends against DNS rebinding) and
                # never follow redirects (which could bounce to an internal host).
                _validate_callback_url(callback_url)
                async with httpx.AsyncClient(
                    timeout=settings.webhook_timeout_seconds,
                    follow_redirects=False,
                ) as client:
                    resp = await client.post(callback_url, json=payload)
                    resp.raise_for_status()
            except Exception as e:
                import structlog
                structlog.get_logger().error("webhook_failed", url=callback_url, error=str(e))
            return
        if result.state == "FAILURE":
            return
