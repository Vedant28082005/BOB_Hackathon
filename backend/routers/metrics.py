"""Metrics router — decision distribution, throughput, model latency."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_session
from security.auth import get_current_user, CurrentUser

router = APIRouter()


@router.get("")
async def get_metrics(
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(get_current_user),
):
    # Total and today counts
    totals = (await session.execute(text("""
        SELECT
            COUNT(*) AS total,
            COUNT(*) FILTER (WHERE decision = 'APPROVE') AS approved,
            COUNT(*) FILTER (WHERE decision = 'REJECT') AS rejected,
            COUNT(*) FILTER (WHERE decision = 'MANUAL_REVIEW') AS manual_review,
            COUNT(*) FILTER (WHERE decision = 'STEP_UP') AS step_up,
            COUNT(*) FILTER (WHERE decision IN ('REJECT','MANUAL_REVIEW')) AS fraud_caught,
            AVG(trust_score) AS avg_trust_score,
            AVG(processing_time_ms) AS avg_processing_ms,
            COUNT(*) FILTER (WHERE created_at::date = CURRENT_DATE) AS today
        FROM assessment
    """))).mappings().one()

    total = totals["total"] or 0
    approved = totals["approved"] or 0
    approval_rate = round((approved / total * 100) if total else 0, 1)

    return {
        "total_assessments": total,
        "approved": approved,
        "rejected": totals["rejected"] or 0,
        "manual_review": totals["manual_review"] or 0,
        "step_up": totals["step_up"] or 0,
        "fraud_caught": totals["fraud_caught"] or 0,
        "approval_rate": approval_rate,
        "avg_trust_score": round(float(totals["avg_trust_score"] or 0), 1),
        "avg_processing_time_ms": round(float(totals["avg_processing_ms"] or 0)),
        "today": totals["today"] or 0,
    }
