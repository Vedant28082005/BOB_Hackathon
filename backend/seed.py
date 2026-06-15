"""
TrustLayer – Database Seed Script
===================================
Populates SQLite with ~80 synthetic past applicants including:
  • Ring 1: 5 applicants sharing device_fingerprint (organised device fraud)
  • Ring 2: 6 applicants sharing phone prefix + suspicious email domain
  • Ring 3: 4 applicants sharing PAN hash (PAN farming)
  • 1 duplicate-identity seed (for the duplicate_identity demo scenario)
  • ~64 clean applicants

Run:  python -m backend.seed
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import hashlib
from datetime import datetime, timedelta
import random

from sqlmodel import Session, select
from backend.database import init_db, engine
from backend.models import Applicant
from backend.config import (
    HASH_SALT, RING1_DEVICE, RING1_IP,
    RING2_PHONE_PREFIX, RING2_EMAIL_DOMAIN,
    RING3_PAN_HASH, DUPLICATE_EMAIL, DUPLICATE_PHONE,
)


def _hash(value: str) -> str:
    return hashlib.sha256(f"{HASH_SALT}:{value}".encode()).hexdigest()


CLEAN_NAMES = [
    "Arjun Mehta", "Priya Nair", "Rohit Sharma", "Sneha Iyer", "Vikram Bose",
    "Deepa Pillai", "Kiran Rao", "Anjali Singh", "Suresh Patel", "Lakshmi Devi",
    "Rahul Gupta", "Pooja Verma", "Aditya Kumar", "Nisha Reddy", "Manish Joshi",
    "Sunita Agarwal", "Rajesh Krishnamurthy", "Geeta Nambiar", "Amit Saxena",
    "Kavitha Menon", "Sanjay Desai", "Meena Shetty", "Dinesh Yadav", "Radha Pande",
    "Vinod Chauhan", "Seema Bhatt", "Ganesh Murthy", "Lata Kulkarni", "Ankit Tiwari",
    "Ritu Garg", "Mahesh Naik", "Divya Jain", "Sunil Khanna", "Rekha Mishra",
    "Naresh Patil", "Anita Rajan", "Vijay Shukla", "Suman Roy", "Girish Nayak",
    "Poonam Banerjee", "Hemant Chaudhary", "Alka Dubey", "Pramod Ghosh",
    "Savita Mukherjee", "Devesh Tripathi", "Usha Pandey", "Ramesh Bhatia",
    "Neha Kapoor", "Sandeep Chopra", "Jyoti Malhotra", "Tarun Ahuja",
    "Sudha Thakur", "Prakash Srivastava", "Mala Bajaj", "Suresh Chandra",
    "Meenakshi Oommen", "Rajan Nithya", "Lalitha Krishnan", "Shobha Menon",
    "Babu Rajan", "Sridevi Nair", "Chandran Pillai", "Leela Thomas",
]

RING1_NAMES = ["Mohan Lal", "Sunita Devi", "Anil Kumar Verma", "Priya Sharma", "Rajesh Mehta"]
RING2_NAMES = ["John D Smith", "Mike R Johnson", "Sarah K Williams", "David L Brown", "Emily T Davis", "Robert J Wilson"]
RING3_NAMES = ["Vikram Singh", "V. Singh", "Vikraam Singh", "Vikram S."]
DUPLICATE_NAME = "Amit Agarwal"

random.seed(42)


def _random_ip_india() -> str:
    prefixes = ["103.", "106.", "117.", "122.", "125.", "182.", "202."]
    p = random.choice(prefixes)
    return p + ".".join(str(random.randint(1, 254)) for _ in range(3))


def _random_device() -> str:
    return hashlib.sha256(str(random.getrandbits(128)).encode()).hexdigest()[:32]


def _random_pan() -> str:
    chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    digits = "0123456789"
    pan = "".join(random.choices(chars, k=5)) + "".join(random.choices(digits, k=4)) + random.choice(chars)
    return pan


def _make_applicant(
    name: str,
    email: str,
    phone: str,
    pan: str,
    device: str,
    ip: str,
    scenario: str = "genuine_user",
    offset_days: int = 0,
) -> Applicant:
    domain = email.split("@")[-1] if "@" in email else "unknown"
    prefix = phone[:7] if len(phone) >= 7 else phone
    created = datetime.utcnow() - timedelta(days=offset_days)
    return Applicant(
        name_hash=_hash(name.lower()),
        email_hash=_hash(email.lower()),
        phone_hash=_hash(phone),
        pan_hash=_hash(pan),
        full_name=name,
        doc_type=random.choice(["AADHAAR", "PAN", "PASSPORT", "DRIVING_LICENSE"]),
        dob=f"{random.randint(1965,2000)}-{random.randint(1,12):02d}-{random.randint(1,28):02d}",
        device_fingerprint=device,
        ip_address=ip,
        email_domain=domain,
        phone_prefix=prefix,
        scenario=scenario,
        created_at=created,
    )


def seed():
    init_db()
    with Session(engine) as session:
        # Check if already seeded
        existing = session.exec(select(Applicant)).first()
        if existing:
            print("Database already seeded. Delete trustlayer.db to re-seed.")
            return

        applicants = []

        # ── Ring 1: device-sharing ring ──────────────────────────────────────
        for i, name in enumerate(RING1_NAMES):
            email = f"ring1user{i+1}@mailtemp.net"
            phone = f"8{random.randint(100000000,999999999)}"
            pan = _random_pan()
            a = _make_applicant(name, email, phone, pan,
                                device=RING1_DEVICE, ip=RING1_IP,
                                scenario="fraud_ring_member",
                                offset_days=random.randint(5, 60))
            applicants.append(a)

        # ── Ring 2: email-domain + phone-prefix ring ─────────────────────────
        for i, name in enumerate(RING2_NAMES):
            email = f"user{i+1}@{RING2_EMAIL_DOMAIN}"
            phone = f"{RING2_PHONE_PREFIX}{random.randint(100,999)}"
            pan = _random_pan()
            a = _make_applicant(name, email, phone, pan,
                                device=_random_device(), ip=_random_ip_india(),
                                scenario="synthetic_identity",
                                offset_days=random.randint(3, 45))
            applicants.append(a)

        # ── Ring 3: shared PAN hash ──────────────────────────────────────────
        # Force same pan_hash for all four by using the same raw PAN value
        shared_pan = "ABCDE1234F"   # all ring3 members claim this PAN
        for i, name in enumerate(RING3_NAMES):
            email = f"pan.ring.{i+1}@ymail.com"
            phone = f"7{random.randint(100000000,999999999)}"
            from backend.config import HASH_SALT as SALT
            a = _make_applicant(name, email, phone, shared_pan,
                                device=_random_device(), ip=_random_ip_india(),
                                scenario="duplicate_identity",
                                offset_days=random.randint(10, 90))
            applicants.append(a)

        # ── Duplicate identity seed ──────────────────────────────────────────
        dup = _make_applicant(
            DUPLICATE_NAME, DUPLICATE_EMAIL, DUPLICATE_PHONE, _random_pan(),
            device=_random_device(), ip=_random_ip_india(),
            scenario="genuine_user", offset_days=120,
        )
        applicants.append(dup)

        # ── Clean applicants ─────────────────────────────────────────────────
        for i, name in enumerate(CLEAN_NAMES):
            email_domains = ["gmail.com", "yahoo.com", "hotmail.com", "outlook.com", "rediffmail.com"]
            first = name.split()[0].lower()
            email = f"{first}.{random.randint(100,999)}@{random.choice(email_domains)}"
            phone = f"9{random.randint(100000000,999999999)}"
            pan = _random_pan()
            a = _make_applicant(name, email, phone, pan,
                                device=_random_device(), ip=_random_ip_india(),
                                scenario="genuine_user",
                                offset_days=random.randint(1, 180))
            applicants.append(a)

        for a in applicants:
            session.add(a)
        session.commit()
        print(f"Seeded {len(applicants)} applicants.")
        print(f"  Ring 1 (device): {len(RING1_NAMES)} members")
        print(f"  Ring 2 (email+phone): {len(RING2_NAMES)} members")
        print(f"  Ring 3 (PAN sharing): {len(RING3_NAMES)} members")
        print(f"  Duplicate seed: {DUPLICATE_NAME} ({DUPLICATE_EMAIL})")
        print(f"  Clean: {len(CLEAN_NAMES)} applicants")


if __name__ == "__main__":
    seed()
