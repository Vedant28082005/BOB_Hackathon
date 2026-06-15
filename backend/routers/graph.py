"""Graph router — on-demand ego-graph queries backed by Neo4j."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from graph.neo4j_client import get_ego_graph, detect_fraud_rings
from security.auth import get_current_user, CurrentUser
from config import settings

router = APIRouter()


@router.get("/{applicant_id}")
async def get_applicant_graph(
    applicant_id: str,
    user: CurrentUser = Depends(get_current_user),
):
    """Return the ego-graph (nodes + links + rings) for an applicant."""
    try:
        graph_data = await get_ego_graph(applicant_id)
        rings = await detect_fraud_rings(applicant_id, settings.ring_min_size)
        return {
            **graph_data,
            "ring_count": len(rings),
            "ring_member": any(applicant_id in r for r in rings),
        }
    except Exception as e:
        raise HTTPException(500, f"Graph query failed: {e}")


@router.get("/{applicant_id}/rings")
async def get_rings(
    applicant_id: str,
    user: CurrentUser = Depends(get_current_user),
):
    """Return fraud rings containing this applicant."""
    rings = await detect_fraud_rings(applicant_id, settings.ring_min_size)
    return {"applicant_id": applicant_id, "rings": rings, "ring_count": len(rings)}
