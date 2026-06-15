"""
Seed Neo4j identity graph with synthetic applicants including planted fraud rings.
Run: python scripts/seed_graph.py
"""
import asyncio
import hashlib
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from graph.neo4j_client import upsert_applicant, init_schema

random.seed(42)

FIRST_NAMES = ["Aarav","Priya","Rahul","Sunita","Amit","Deepa","Vikram","Neha","Rohit","Kavya",
               "Arjun","Meera","Sanjay","Pooja","Anil","Ritu","Suresh","Anita","Manoj","Geeta"]
LAST_NAMES  = ["Sharma","Patel","Singh","Kumar","Gupta","Joshi","Mishra","Reddy","Nair","Iyer"]

def _sha256(v: str) -> str:
    return hashlib.sha256(v.encode()).hexdigest()

def _name() -> str:
    return f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}"

def _email(name: str, domain: str = "gmail.com") -> str:
    return f"{name.lower().replace(' ', '.')}_{random.randint(10,99)}@{domain}"

def _phone() -> str:
    return f"9{random.randint(100000000, 999999999)}"

def _pan() -> str:
    import string
    letters = string.ascii_uppercase
    return "".join(random.choices(letters, k=5)) + "".join(str(random.randint(0,9)) for _ in range(4)) + random.choice(letters)

# ── Fraud ring definitions ────────────────────────────────────────────────────
RING1_DEVICE = "d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9"
RING1_IP     = "196.245.100.50"

RING2_DOMAIN = "fraudnetwork.biz"
RING2_PHONE_PREFIX = "9000000"

RING3_PAN = "ABCDE1234F"

DUPLICATE_EMAIL = "amit.agarwal.dup@gmail.com"

async def seed():
    await init_schema()
    print("Seeding Neo4j identity graph…")

    created = 0

    # ── Ring 1: shared device + IP (5 members) ────────────────────────────────
    print("  Planting Ring 1 (shared device/IP)…")
    for _ in range(5):
        name = _name()
        await upsert_applicant(
            applicant_id=_sha256(f"ring1_{_}_{name}"),
            name=name,
            device_fingerprint=RING1_DEVICE,
            ip_address=RING1_IP,
            email_hash=_sha256(_email(name)),
            phone_hash=_sha256(_phone()),
            pan_hash=_sha256(_pan()),
            risk_label="RING_MEMBER",
        )
        created += 1

    # ── Ring 2: shared email domain (6 members) ───────────────────────────────
    print("  Planting Ring 2 (shared email domain)…")
    for _ in range(6):
        name = _name()
        await upsert_applicant(
            applicant_id=_sha256(f"ring2_{_}_{name}"),
            name=name,
            device_fingerprint=_sha256(f"dev_ring2_{_}"),
            ip_address=f"45.{random.randint(1,254)}.{random.randint(1,254)}.{random.randint(1,254)}",
            email_hash=_sha256(_email(name, RING2_DOMAIN)),
            phone_hash=_sha256(f"{RING2_PHONE_PREFIX}{random.randint(10,99)}"),
            pan_hash=_sha256(_pan()),
            risk_label="RING_MEMBER",
        )
        created += 1

    # ── Ring 3: shared PAN (4 members) ───────────────────────────────────────
    print("  Planting Ring 3 (shared PAN)…")
    for _ in range(4):
        name = _name()
        await upsert_applicant(
            applicant_id=_sha256(f"ring3_{_}_{name}"),
            name=name,
            device_fingerprint=_sha256(f"dev_ring3_{_}"),
            ip_address=f"91.{random.randint(1,254)}.{random.randint(1,254)}.{random.randint(1,254)}",
            email_hash=_sha256(_email(name)),
            phone_hash=_sha256(_phone()),
            pan_hash=_sha256(RING3_PAN),
            risk_label="RING_MEMBER",
        )
        created += 1

    # ── Duplicate seed ────────────────────────────────────────────────────────
    print("  Planting duplicate identity seed…")
    await upsert_applicant(
        applicant_id=_sha256("duplicate_seed_amit"),
        name="Amit Agarwal",
        device_fingerprint=_sha256("clean_device_amit"),
        ip_address="49.36.100.50",
        email_hash=_sha256(DUPLICATE_EMAIL),
        phone_hash=_sha256("9876543210"),
        pan_hash=_sha256("AGJPA5432B"),
        risk_label="CLEAN",
    )
    created += 1

    # ── 63 clean applicants ───────────────────────────────────────────────────
    print("  Seeding 63 clean applicants…")
    for i in range(63):
        name = _name()
        await upsert_applicant(
            applicant_id=_sha256(f"clean_{i}_{name}"),
            name=name,
            device_fingerprint=_sha256(f"clean_device_{i}"),
            ip_address=f"49.{random.randint(1,254)}.{random.randint(1,254)}.{random.randint(1,254)}",
            email_hash=_sha256(_email(name)),
            phone_hash=_sha256(_phone()),
            pan_hash=_sha256(_pan()),
            risk_label="CLEAN",
        )
        created += 1

    print(f"\nSeeded {created} applicants into Neo4j.")
    print("Rings planted: Ring1 (device/IP, 5 members), Ring2 (email domain, 6 members), Ring3 (PAN, 4 members)")
    print("Duplicate: amit.agarwal.dup@gmail.com")


if __name__ == "__main__":
    asyncio.run(seed())
