"""
Identity graph engine — Neo4j-backed.
Wraps neo4j_client calls and produces the StageResult dict used by fusion.
"""
from __future__ import annotations

from config import settings
from graph.neo4j_client import (
    upsert_applicant, check_duplicate, find_shared_resources,
    detect_fraud_rings, get_ego_graph,
)


async def analyse_graph(
    applicant_id: str,
    email_hash: str,
    phone_hash: str,
    pan_hash: str,
    device_fingerprint: str,
    ip_address: str,
    name: str,
) -> dict:
    # 1. Write this applicant into the graph
    await upsert_applicant(
        applicant_id=applicant_id,
        name=name,
        device_fingerprint=device_fingerprint,
        ip_address=ip_address,
        email_hash=email_hash,
        phone_hash=phone_hash,
        pan_hash=pan_hash,
    )

    # 2. Duplicate identity check
    dup_id = await check_duplicate(email_hash, phone_hash, applicant_id)

    # 3. Shared resources
    shared = await find_shared_resources(applicant_id)

    # 4. Fraud ring detection
    rings = await detect_fraud_rings(applicant_id, settings.ring_min_size)

    # 5. Ego graph for visualization
    graph_data = await get_ego_graph(applicant_id)

    # 6. Score
    flags: list[str] = []
    score = 100.0

    if dup_id:
        flags.append("GRAPH_DUPLICATE")
        score -= 60.0

    ring_member = any(applicant_id in ring for ring in rings)
    if ring_member:
        flags.append("GRAPH_RING_MEMBER")
        score -= 40.0

    if "USED_DEVICE" in shared:
        flags.append("SHARED_DEVICE")
        score -= 15.0
    if "USED_IP" in shared:
        flags.append("SHARED_IP")
        score -= 10.0

    score = max(0.0, min(100.0, score))

    return {
        "score": score,
        "signals": {
            "duplicate_id": dup_id,
            "shared_resources": {k: len(v) for k, v in shared.items()},
            "ring_count": len(rings),
            "ring_member": ring_member,
            "ring_sizes": [len(r) for r in rings],
        },
        "flags": flags,
        "graph_data": graph_data,
    }
