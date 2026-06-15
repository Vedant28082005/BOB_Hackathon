"""
TrustLayer – data models.
SQLModel tables (ORM + schema in one) + pure-Pydantic request/response models.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Optional
from sqlmodel import SQLModel, Field
from pydantic import BaseModel, field_validator


# ══════════════════════════════════════════════════════════════════════════════
# DB TABLES
# ══════════════════════════════════════════════════════════════════════════════

class Applicant(SQLModel, table=True):
    """Minimal applicant record – raw PII is never stored in full."""
    id: Optional[int] = Field(default=None, primary_key=True)
    applicant_uuid: str = Field(default_factory=lambda: str(uuid.uuid4()), index=True)

    # Hashed / minimised identity fields
    name_hash: str
    email_hash: str
    phone_hash: str
    pan_hash: str

    # Non-sensitive or low-sensitivity fields
    full_name: str          # stored for investigator readability (no raw PAN/Aadhaar)
    doc_type: str
    dob: str
    device_fingerprint: str = Field(index=True)
    ip_address: str = Field(index=True)
    email_domain: str = Field(index=True)    # for ring detection
    phone_prefix: str = Field(index=True)    # first 7 digits, for ring detection

    # Scenario tag (used internally by simulators; not sensitive)
    scenario: str = Field(default="genuine_user")

    created_at: datetime = Field(default_factory=datetime.utcnow)


class Assessment(SQLModel, table=True):
    """Full risk-assessment record linked to an Applicant."""
    id: Optional[int] = Field(default=None, primary_key=True)
    assessment_uuid: str = Field(default_factory=lambda: str(uuid.uuid4()), index=True)
    applicant_uuid: str = Field(index=True)
    applicant_id: Optional[str] = Field(default=None, index=True)  # FK alias for production flow

    # Stage scores (0-100)
    document_score: float
    biometric_score: float
    device_score: float
    behavioural_score: float
    identity_graph_score: float
    trust_score: float

    risk_band: str      # LOW | MEDIUM | HIGH | CRITICAL
    decision: str       # APPROVE | STEP_UP | MANUAL_REVIEW | REJECT

    reason_codes_json: str          # JSON list of ReasonCode dicts
    signals_json: str               # Full pipeline detail (JSON)
    llm_explanation: str = Field(default="")

    processing_time_ms: float = 0.0
    created_at: datetime = Field(default_factory=datetime.utcnow)


class AuditEntry(SQLModel, table=True):
    """Immutable, hash-chained audit log record."""
    id: Optional[int] = Field(default=None, primary_key=True)
    entry_uuid: str = Field(default_factory=lambda: str(uuid.uuid4()), index=True)
    assessment_uuid: Optional[str] = Field(default=None, index=True)
    applicant_uuid: Optional[str] = Field(default=None, index=True)
    # Aliases used by production audit router
    applicant_id: Optional[str] = Field(default=None, index=True)

    event_type: str        # e.g. ASSESSMENT_COMPLETE, MANUAL_REVIEW_TRIGGERED
    summary: str = Field(default="")
    payload_json: str = Field(default="{}")   # full snapshot at write time
    payload: Optional[str] = Field(default=None)  # alias for payload_json

    prev_hash: str
    record_hash: str
    created_at: datetime = Field(default_factory=datetime.utcnow)


# ══════════════════════════════════════════════════════════════════════════════
# REQUEST / RESPONSE SCHEMAS
# ══════════════════════════════════════════════════════════════════════════════

class DeviceSignals(BaseModel):
    user_agent: str
    platform: str
    timezone: str
    language: str
    screen_resolution: str
    color_depth: int
    device_fingerprint: str

class BehaviouralSignals(BaseModel):
    keystroke_intervals_ms: list[float]   # raw inter-keystroke gaps
    form_fill_duration_s: float
    paste_events: int
    focus_losses: int

class AssessmentRequest(BaseModel):
    # Personal info
    full_name: str
    email: str
    phone: str
    dob: str            # YYYY-MM-DD
    address: str
    pan_number: str     # will be hashed immediately, never stored raw

    # Document (client-side hashed)
    doc_type: str       # AADHAAR | PAN | PASSPORT | DRIVING_LICENSE
    doc_hash: str       # SHA-256 of the document file
    doc_name_on_doc: str  # name as entered from document (for cross-check)

    # Selfie (client-side hashed)
    selfie_hash: str

    # Live signals
    device: DeviceSignals
    behavioural: BehaviouralSignals

    # Demo steering
    scenario: str = "genuine_user"


# ── Sub-result models ────────────────────────────────────────────────────────

class ReasonCode(BaseModel):
    code: str
    severity: str       # INFO | LOW | MEDIUM | HIGH | CRITICAL
    title: str
    message: str
    score_impact: float  # how much it dragged / boosted the score

class StageResult(BaseModel):
    score: float
    signals: dict[str, Any]
    flags: list[str] = []

class PipelineResult(BaseModel):
    document: StageResult
    biometric: StageResult
    device: StageResult
    behavioural: StageResult
    identity_graph: StageResult

class GraphNode(BaseModel):
    id: str
    label: str
    is_current: bool = False
    in_fraud_ring: bool = False
    scenario: str = ""

class GraphLink(BaseModel):
    source: str
    target: str
    link_type: str   # SHARED_DEVICE | SHARED_IP | SHARED_PHONE | SHARED_EMAIL | SHARED_PAN

class GraphData(BaseModel):
    nodes: list[GraphNode]
    links: list[GraphLink]
    rings: list[list[str]]   # each inner list = member applicant_uuids of a ring

class AssessmentResponse(BaseModel):
    assessment_uuid: str
    applicant_uuid: str
    trust_score: float
    risk_band: str
    decision: str
    reason_codes: list[ReasonCode]
    llm_explanation: str
    pipeline: PipelineResult
    graph_data: GraphData
    data_retained: list[str]
    data_discarded: list[str]
    processing_time_ms: float

class MetricsResponse(BaseModel):
    total_assessments: int
    approved: int
    step_up: int
    manual_review: int
    rejected: int
    approval_rate: float
    fraud_caught: int
    avg_decision_time_ms: float
    avg_trust_score: float
    assessments_today: int
