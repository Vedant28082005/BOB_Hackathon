"""
TrustLayer – Document Forensics Simulator
==========================================
Produces realistic structured document-analysis results.
Outputs are deterministic (doc_hash + scenario) so the same
document always returns the same scores — no random drift.

All outputs mimic a real OCR / tamper-detection pipeline
(confidence, sub-signals, anomaly flags) rather than plain PASS/FAIL.
"""
from __future__ import annotations
import hashlib
from dataclasses import dataclass, field


@dataclass
class DocumentAnalysisResult:
    # Overall
    score: float                       # 0-100
    verdict: str                       # AUTHENTIC | LIKELY_TAMPERED | TAMPERED | UNREADABLE

    # OCR extraction
    ocr_confidence: float              # 0-1
    extracted_name: str
    extracted_dob: str
    extracted_doc_id: str
    name_match_score: float            # 0-1 (vs entered name)
    dob_match: bool

    # Authenticity sub-signals
    font_consistency_score: float      # 0-1
    security_feature_score: float      # 0-1  (holograms, microprint, etc.)
    metadata_integrity_score: float    # 0-1  (EXIF, format consistency)
    edge_tampering_score: float        # 0-1  (higher = more tampering evidence)
    compression_artifact_score: float  # 0-1  (lower = more suspicious re-saves)
    layout_conformance_score: float    # 0-1

    # Flags
    detected_anomalies: list[str] = field(default_factory=list)


# ── Scenario profiles ────────────────────────────────────────────────────────

_PROFILES: dict[str, dict] = {
    "genuine_user": {
        "score": 91,
        "verdict": "AUTHENTIC",
        "ocr_confidence": 0.97,
        "name_match_score": 0.98,
        "dob_match": True,
        "font_consistency_score": 0.96,
        "security_feature_score": 0.94,
        "metadata_integrity_score": 0.97,
        "edge_tampering_score": 0.03,
        "compression_artifact_score": 0.92,
        "layout_conformance_score": 0.95,
        "anomalies": [],
    },
    "synthetic_identity": {
        "score": 50,
        "verdict": "AUTHENTIC",           # doc itself looks OK but has anomalies
        "ocr_confidence": 0.82,
        "name_match_score": 0.72,         # notable mismatch – thin/assembled ID
        "dob_match": True,
        "font_consistency_score": 0.68,
        "security_feature_score": 0.64,
        "metadata_integrity_score": 0.71,
        "edge_tampering_score": 0.18,
        "compression_artifact_score": 0.65,
        "layout_conformance_score": 0.70,
        "anomalies": ["MINOR_FONT_DEVIATION", "LOW_PRINT_RESOLUTION", "INCONSISTENT_METADATA"],
    },
    "deepfake_attempt": {
        "score": 55,
        "verdict": "AUTHENTIC",           # doc may be real – biometric fails
        "ocr_confidence": 0.91,
        "name_match_score": 0.93,
        "dob_match": True,
        "font_consistency_score": 0.90,
        "security_feature_score": 0.88,
        "metadata_integrity_score": 0.89,
        "edge_tampering_score": 0.08,
        "compression_artifact_score": 0.86,
        "layout_conformance_score": 0.90,
        "anomalies": [],
    },
    "tampered_document": {
        "score": 18,
        "verdict": "TAMPERED",
        "ocr_confidence": 0.72,
        "name_match_score": 0.34,         # OCR name doesn't match entered
        "dob_match": False,
        "font_consistency_score": 0.31,
        "security_feature_score": 0.22,
        "metadata_integrity_score": 0.19,
        "edge_tampering_score": 0.87,
        "compression_artifact_score": 0.21,
        "layout_conformance_score": 0.28,
        "anomalies": [
            "PIXEL_LEVEL_INCONSISTENCY",
            "FONT_SUBSTITUTION_DETECTED",
            "METADATA_STRIP_AND_RESAVE",
            "SECURITY_WATERMARK_ABSENT",
            "EDGE_CLONING_ARTIFACTS",
        ],
    },
    "fraud_ring_member": {
        "score": 74,
        "verdict": "AUTHENTIC",
        "ocr_confidence": 0.92,
        "name_match_score": 0.90,
        "dob_match": True,
        "font_consistency_score": 0.88,
        "security_feature_score": 0.86,
        "metadata_integrity_score": 0.90,
        "edge_tampering_score": 0.07,
        "compression_artifact_score": 0.85,
        "layout_conformance_score": 0.89,
        "anomalies": [],
    },
    "duplicate_identity": {
        "score": 83,
        "verdict": "AUTHENTIC",
        "ocr_confidence": 0.95,
        "name_match_score": 0.97,
        "dob_match": True,
        "font_consistency_score": 0.93,
        "security_feature_score": 0.91,
        "metadata_integrity_score": 0.94,
        "edge_tampering_score": 0.04,
        "compression_artifact_score": 0.90,
        "layout_conformance_score": 0.93,
        "anomalies": [],
    },
}

_DEFAULT_PROFILE = _PROFILES["genuine_user"]


def _nudge(base: float, doc_hash: str, factor: float = 0.04) -> float:
    """Add a tiny deterministic jitter so each doc hash gives slightly different numbers."""
    import hashlib
    seed_hex = hashlib.sha256(doc_hash.encode()).hexdigest()[:8] if doc_hash else "00000000"
    seed = int(seed_hex, 16)
    jitter = ((seed % 100) / 100 - 0.5) * factor
    return max(0.0, min(1.0, base + jitter))


def analyse_document(
    doc_hash: str,
    doc_type: str,
    entered_name: str,
    entered_dob: str,
    scenario: str = "genuine_user",
) -> DocumentAnalysisResult:
    p = _PROFILES.get(scenario, _DEFAULT_PROFILE)

    # Deterministic extraction of fictional OCR values
    h = int(hashlib.sha256(doc_hash.encode()).hexdigest()[:8], 16)
    fake_id_suffix = str(h % 900000 + 100000)
    doc_prefix = {"AADHAAR": "XXXX XXXX ", "PAN": "ABCDE", "PASSPORT": "J", "DRIVING_LICENSE": "MH"}.get(doc_type, "XX")
    extracted_doc_id = doc_prefix + fake_id_suffix

    # OCR name: if high match -> use entered name; if low -> introduce a typo
    name_match = _nudge(p["name_match_score"], doc_hash)
    if name_match >= 0.85:
        extracted_name = entered_name
    else:
        parts = entered_name.split()
        if len(parts) > 1:
            parts[0] = parts[0][:-1] + "a" if len(parts[0]) > 1 else parts[0]
        extracted_name = " ".join(parts)

    score = p["score"] + int((h % 11) - 5)   # ±5 deterministic variation
    score = max(0, min(100, score))

    return DocumentAnalysisResult(
        score=float(score),
        verdict=p["verdict"],
        ocr_confidence=_nudge(p["ocr_confidence"], doc_hash),
        extracted_name=extracted_name,
        extracted_dob=entered_dob if p["dob_match"] else "1900-01-01",
        extracted_doc_id=extracted_doc_id,
        name_match_score=name_match,
        dob_match=p["dob_match"],
        font_consistency_score=_nudge(p["font_consistency_score"], doc_hash),
        security_feature_score=_nudge(p["security_feature_score"], doc_hash),
        metadata_integrity_score=_nudge(p["metadata_integrity_score"], doc_hash),
        edge_tampering_score=_nudge(p["edge_tampering_score"], doc_hash, 0.03),
        compression_artifact_score=_nudge(p["compression_artifact_score"], doc_hash),
        layout_conformance_score=_nudge(p["layout_conformance_score"], doc_hash),
        detected_anomalies=list(p["anomalies"]),
    )
