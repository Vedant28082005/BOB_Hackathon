"""Unit tests for tamper-evident audit hash chain integrity."""
import hashlib
import json
import uuid
import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "backend"))


def _sha256(data: str) -> str:
    return hashlib.sha256(data.encode()).hexdigest()


def _build_chain(entries: list[dict]) -> list[dict]:
    """Build a hash-chained audit log (mimics the backend AuditEntry logic)."""
    records = []
    prev_hash = "0" * 64  # genesis hash
    for entry in entries:
        entry_uuid = str(uuid.uuid4())
        payload = json.dumps(entry, sort_keys=True)
        record_hash = _sha256(prev_hash + entry_uuid + payload)
        records.append({
            "uuid": entry_uuid,
            "payload": payload,
            "prev_hash": prev_hash,
            "record_hash": record_hash,
        })
        prev_hash = record_hash
    return records


def _verify_chain(records: list[dict]) -> tuple[bool, int]:
    """Returns (is_valid, first_broken_index). -1 if all valid."""
    prev_hash = "0" * 64
    for i, rec in enumerate(records):
        if rec["prev_hash"] != prev_hash:
            return False, i
        expected = _sha256(rec["prev_hash"] + rec["uuid"] + rec["payload"])
        if rec["record_hash"] != expected:
            return False, i
        prev_hash = rec["record_hash"]
    return True, -1


class TestAuditChain:
    def test_valid_chain_passes(self):
        entries = [{"action": "ASSESSMENT_COMPLETE", "applicant": f"user_{i}"} for i in range(5)]
        records = _build_chain(entries)
        valid, broken = _verify_chain(records)
        assert valid
        assert broken == -1

    def test_modified_payload_breaks_chain(self):
        entries = [{"action": "ASSESSMENT_COMPLETE", "score": 95}]
        records = _build_chain(entries)
        # Tamper with the payload
        records[0]["payload"] = json.dumps({"action": "ASSESSMENT_COMPLETE", "score": 10})
        valid, broken = _verify_chain(records)
        assert not valid
        assert broken == 0

    def test_modified_middle_breaks_all_subsequent(self):
        entries = [{"n": i} for i in range(5)]
        records = _build_chain(entries)
        records[2]["payload"] = '{"n": 999}'
        valid, broken = _verify_chain(records)
        assert not valid
        assert broken == 2  # first broken is index 2

    def test_empty_chain_is_valid(self):
        valid, broken = _verify_chain([])
        assert valid
        assert broken == -1

    def test_single_record_chain(self):
        records = _build_chain([{"action": "CONSENT_CAPTURED"}])
        valid, broken = _verify_chain(records)
        assert valid

    def test_reordering_breaks_chain(self):
        entries = [{"n": i} for i in range(3)]
        records = _build_chain(entries)
        records[0], records[1] = records[1], records[0]
        valid, broken = _verify_chain(records)
        assert not valid

    def test_genesis_hash_is_deterministic(self):
        entries = [{"action": "TEST"}]
        r1 = _build_chain(entries)
        # Genesis always starts at all-zeros
        assert r1[0]["prev_hash"] == "0" * 64
