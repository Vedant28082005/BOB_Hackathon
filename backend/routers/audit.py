"""Tamper-evident audit log router — read-only for analyst/auditor/admin."""
from __future__ import annotations
import hashlib
import json
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_session
from security.auth import get_current_user, CurrentUser

router = APIRouter()


# ── Schema ─────────────────────────────────────────────────────────────────────
class AuditEntry(BaseModel):
    id: int
    entry_uuid: str
    event_type: str
    applicant_id: Optional[str]
    assessment_uuid: Optional[str]
    payload: dict
    prev_hash: str
    record_hash: str
    created_at: str


class ChainVerifyResult(BaseModel):
    valid: bool
    total_records: int
    first_broken_index: Optional[int]
    message: str


# ── Helpers ────────────────────────────────────────────────────────────────────
def _verify_entry(prev_hash: str, entry_uuid: str, payload_json: str, record_hash: str) -> bool:
    expected = hashlib.sha256(
        (prev_hash + entry_uuid + payload_json).encode()
    ).hexdigest()
    return expected == record_hash


# ── Endpoints ──────────────────────────────────────────────────────────────────
@router.get("")
async def list_audit_log(
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    event_type: Optional[str] = None,
    applicant_id: Optional[str] = None,
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(get_current_user),
):
    """Return paginated audit entries, newest first."""
    # Build dynamic query (raw SQL for flexibility with optional filters)
    where_clauses = []
    params: dict = {"limit": limit, "offset": offset}

    if event_type:
        where_clauses.append("event_type = :event_type")
        params["event_type"] = event_type
    if applicant_id:
        where_clauses.append("applicant_id = :applicant_id")
        params["applicant_id"] = applicant_id

    where_sql = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

    q = text(f"""
        SELECT id, entry_uuid, event_type, applicant_id, assessment_uuid,
               payload, prev_hash, record_hash, created_at
        FROM auditentry
        {where_sql}
        ORDER BY id DESC
        LIMIT :limit OFFSET :offset
    """)

    result = await session.execute(q, params)
    rows = result.mappings().all()

    entries = []
    for row in rows:
        payload = row["payload"]
        if isinstance(payload, str):
            try:
                payload = json.loads(payload)
            except Exception:
                payload = {"raw": payload}
        entries.append({
            "id": row["id"],
            "entry_uuid": row["entry_uuid"],
            "event_type": row["event_type"],
            "applicant_id": row["applicant_id"],
            "assessment_uuid": row["assessment_uuid"],
            "payload": payload,
            "prev_hash": row["prev_hash"][:16] + "…",
            "record_hash": row["record_hash"][:16] + "…",
            "created_at": str(row["created_at"]),
        })

    count_q = text(f"SELECT COUNT(*) FROM auditentry {where_sql}")
    total = (await session.execute(count_q, params)).scalar()

    return {"entries": entries, "total": total, "limit": limit, "offset": offset}


@router.get("/verify", response_model=ChainVerifyResult)
async def verify_chain(
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(get_current_user),
):
    """Walk the entire audit chain and verify hash integrity."""
    rows = (await session.execute(text(
        "SELECT entry_uuid, payload, prev_hash, record_hash FROM auditentry ORDER BY id ASC"
    ))).mappings().all()

    for i, row in enumerate(rows):
        payload_str = row["payload"] if isinstance(row["payload"], str) else json.dumps(row["payload"])
        if not _verify_entry(row["prev_hash"], row["entry_uuid"], payload_str, row["record_hash"]):
            return ChainVerifyResult(
                valid=False,
                total_records=len(rows),
                first_broken_index=i,
                message=f"Chain broken at record index {i} (uuid={row['entry_uuid'][:8]}…). Prior records tampered.",
            )

    return ChainVerifyResult(
        valid=True,
        total_records=len(rows),
        first_broken_index=None,
        message="All records verified. Audit chain is intact.",
    )
