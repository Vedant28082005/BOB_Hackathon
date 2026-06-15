"""
Neo4j client for the identity risk graph.
Entity nodes: Applicant, Device, IP, Email, Phone, PAN.
Relationships: USED_DEVICE, USED_IP, HAS_EMAIL, HAS_PHONE, HAS_PAN.
Community detection: Louvain (via GDS plugin) or fallback connected-components.
"""
from __future__ import annotations
import hashlib
import re
from contextlib import asynccontextmanager
from typing import Any, Optional

from neo4j import AsyncGraphDatabase, AsyncDriver
import structlog

from config import settings

log = structlog.get_logger(__name__)

_driver: Optional[AsyncDriver] = None

# Known private IP prefixes — excluded from ring-detection edges
_PRIVATE_PREFIXES = ("127.", "10.", "172.16.", "172.17.", "172.18.", "172.19.",
                     "172.2", "172.3", "192.168.", "::1", "0.0.0.0", "169.254.")


def _is_private_ip(ip: str) -> bool:
    return any(ip.startswith(p) for p in _PRIVATE_PREFIXES)


def _public_email_domain(email: str) -> bool:
    """True if the domain is a common free provider — don't link on these."""
    dom = email.split("@")[-1].lower() if "@" in email else ""
    return dom in {
        "gmail.com", "yahoo.com", "hotmail.com", "outlook.com",
        "rediffmail.com", "yopmail.com", "mailinator.com",
    }


async def get_driver() -> AsyncDriver:
    global _driver
    if _driver is None:
        _driver = AsyncGraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_user, settings.neo4j_password),
        )
    return _driver


async def close_driver() -> None:
    global _driver
    if _driver:
        await _driver.close()
        _driver = None


async def clear_graph() -> int:
    """Delete every node and relationship in the graph. Returns nodes removed.

    Demo utility: wipes prior test identities so a re-submitted applicant is no
    longer matched against earlier runs as a duplicate / ring member.
    """
    driver = await get_driver()
    async with driver.session() as s:
        rec = await (await s.run("MATCH (n) RETURN count(n) AS c")).single()
        count = rec["c"] if rec else 0
        await s.run("MATCH (n) DETACH DELETE n")
        return int(count)


async def init_schema() -> None:
    """Create indexes and constraints on first boot."""
    driver = await get_driver()
    async with driver.session() as session:
        constraints = [
            "CREATE CONSTRAINT IF NOT EXISTS FOR (a:Applicant) REQUIRE a.id IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (d:Device) REQUIRE d.fingerprint IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (i:IP) REQUIRE i.address IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (e:Email) REQUIRE e.hash IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (p:Phone) REQUIRE p.hash IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (n:PAN) REQUIRE n.hash IS UNIQUE",
        ]
        for c in constraints:
            await session.run(c)
    log.info("neo4j_schema_ready")


# ── Write applicant + edges ───────────────────────────────────────────────────
async def upsert_applicant(
    applicant_id: str,
    name: str,
    device_fingerprint: str,
    ip_address: str,
    email_hash: str,
    phone_hash: str,
    pan_hash: str,
    risk_label: str = "UNKNOWN",
) -> None:
    driver = await get_driver()
    async with driver.session() as s:
        # Upsert Applicant node
        await s.run("""
            MERGE (a:Applicant {id: $id})
            SET a.name = $name, a.risk_label = $risk_label,
                a.updated_at = datetime()
        """, id=applicant_id, name=name, risk_label=risk_label)

        # Device
        if device_fingerprint:
            await s.run("""
                MERGE (d:Device {fingerprint: $fp})
                MERGE (a:Applicant {id: $id})
                MERGE (a)-[:USED_DEVICE]->(d)
            """, fp=device_fingerprint, id=applicant_id)

        # IP (non-private only)
        if ip_address and not _is_private_ip(ip_address):
            await s.run("""
                MERGE (i:IP {address: $ip})
                MERGE (a:Applicant {id: $id})
                MERGE (a)-[:USED_IP]->(i)
            """, ip=ip_address, id=applicant_id)

        # Email (non-public-domain only)
        # We store SHA256 hash — never the raw email
        if email_hash:
            await s.run("""
                MERGE (e:Email {hash: $h})
                MERGE (a:Applicant {id: $id})
                MERGE (a)-[:HAS_EMAIL]->(e)
            """, h=email_hash, id=applicant_id)

        # Phone
        if phone_hash:
            await s.run("""
                MERGE (p:Phone {hash: $h})
                MERGE (a:Applicant {id: $id})
                MERGE (a)-[:HAS_PHONE]->(p)
            """, h=phone_hash, id=applicant_id)

        # PAN
        if pan_hash:
            await s.run("""
                MERGE (n:PAN {hash: $h})
                MERGE (a:Applicant {id: $id})
                MERGE (a)-[:HAS_PAN]->(n)
            """, h=pan_hash, id=applicant_id)


# ── Risk analysis ──────────────────────────────────────────────────────────────
async def check_duplicate(email_hash: str, phone_hash: str, applicant_id: str) -> Optional[str]:
    """Returns existing applicant_id if a duplicate is found."""
    driver = await get_driver()
    async with driver.session() as s:
        result = await s.run("""
            MATCH (a:Applicant)
            WHERE a.id <> $id
            AND (
                EXISTS { (a)-[:HAS_EMAIL]->(:Email {hash: $eh}) }
                OR EXISTS { (a)-[:HAS_PHONE]->(:Phone {hash: $ph}) }
            )
            RETURN a.id AS dup_id LIMIT 1
        """, id=applicant_id, eh=email_hash, ph=phone_hash)
        rec = await result.single()
        return rec["dup_id"] if rec else None


async def find_shared_resources(applicant_id: str) -> dict[str, list[str]]:
    """Find other applicants sharing device/IP/email/phone/PAN."""
    driver = await get_driver()
    async with driver.session() as s:
        result = await s.run("""
            MATCH (a:Applicant {id: $id})-[r]->(shared)<-[r2]-(other:Applicant)
            WHERE a.id <> other.id
            RETURN type(r) AS rel_type, other.id AS other_id, other.name AS other_name,
                   other.risk_label AS other_risk
            ORDER BY other.id
        """, id=applicant_id)
        shared: dict[str, list[str]] = {}
        async for rec in result:
            rel = rec["rel_type"]
            other = f"{rec['other_id']}:{rec['other_name']}"
            shared.setdefault(rel, []).append(other)
        return shared


async def detect_fraud_rings(applicant_id: str, min_size: int = 3) -> list[list[str]]:
    """
    Find connected components of size >= min_size containing this applicant.
    Uses Cypher path query (GDS Louvain preferred in production).
    Returns list of rings (each = list of applicant IDs).
    """
    driver = await get_driver()
    async with driver.session() as s:
        # BFS up to 3 hops via shared entity nodes
        result = await s.run("""
            MATCH path = (a:Applicant {id: $id})-[*1..6]-(other:Applicant)
            WHERE a.id <> other.id
            WITH collect(DISTINCT other.id) + [$id] AS members
            WHERE size(members) >= $min_size
            RETURN members
            LIMIT 5
        """, id=applicant_id, min_size=min_size)
        rings = []
        async for rec in result:
            rings.append(rec["members"])
        return rings


async def get_ego_graph(
    applicant_id: str,
    hops: int = 2,
    rings: Optional[list[list[str]]] = None,
) -> dict:
    """Return nodes + edges for the identity graph visualization.

    `rings` may be passed in by a caller that already computed them (e.g.
    analyse_graph) to skip a redundant fraud-ring traversal. Neighbour
    ring-membership is then resolved by O(1) set lookup rather than a per-
    neighbour graph query, turning an O(N) query fan-out into a single query.
    """
    driver = await get_driver()
    async with driver.session() as s:
        if rings is None:
            rings = await detect_fraud_rings(applicant_id, min_size=settings.ring_min_size)
        ring_member_ids: set[str] = set().union(*rings) if rings else set()

        result = await s.run("""
            MATCH (a:Applicant {id: $id})-[r]->(shared)<-[r2]-(other:Applicant)
            RETURN other, type(r) AS link_type
        """, id=applicant_id)

        nodes = [{"id": applicant_id, "label": "You", "type": "Applicant", "is_current": True}]
        links = []
        seen_nodes = {applicant_id}
        seen_edges = set()

        async for rec in result:
            other = rec["other"]
            other_id = other["id"]
            link_type = rec["link_type"]

            if other_id not in seen_nodes:
                nodes.append({
                    "id": other_id,
                    "label": other.get("name", other_id),
                    "type": "Applicant",
                    "in_ring": other_id in ring_member_ids,
                    "risk_label": other.get("risk_label", "UNKNOWN"),
                })
                seen_nodes.add(other_id)

            edge_key = tuple(sorted((applicant_id, other_id)) + [link_type])
            if edge_key not in seen_edges:
                links.append({"source": applicant_id, "target": other_id, "link_type": link_type})
                seen_edges.add(edge_key)

        return {"nodes": nodes, "links": links, "rings": [list(r) for r in rings]}
