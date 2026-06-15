"""
Hardened fusion engine.
Weights and thresholds are passed in (loaded from DB / config), not hardcoded.
Hard-fail overrides applied before score-based decision.
Cross-signal consistency penalties applied to weighted score.
"""
from __future__ import annotations
from typing import Any


# ── Hard-fail rules (applied regardless of score) ─────────────────────────────
_HARD_REJECT = {"GRAPH_DUPLICATE", "BIO_DEEPFAKE", "LIVENESS_FAIL"}
_HARD_MANUAL = {"DOC_TAMPERED", "GRAPH_RING_MEMBER"}


def _score_to_decision(score: float, thresholds: dict) -> str:
    if score >= thresholds["approve"]:
        return "APPROVE"
    if score >= thresholds["step_up"]:
        return "STEP_UP"
    if score >= thresholds["manual_review"]:
        return "MANUAL_REVIEW"
    return "REJECT"


def _risk_band(decision: str, score: float) -> str:
    if decision == "APPROVE":
        return "LOW"
    if decision == "STEP_UP":
        return "MEDIUM"
    if decision == "MANUAL_REVIEW":
        return "HIGH"
    return "CRITICAL"


def _build_reason_codes(pipeline: dict) -> list[dict]:
    codes = []

    stage_flags = {
        stage: data.get("flags", [])
        for stage, data in pipeline.items()
    }

    flag_catalog: dict[str, dict] = {
        # Document
        "ELA_ANOMALY":            {"title": "Image Manipulation Detected (ELA)", "severity": "HIGH",     "impact": -18, "code": "DOC_ELA_001"},
        "COPY_MOVE_DETECTED":     {"title": "Clone / Copy-Move Artifacts",       "severity": "HIGH",     "impact": -15, "code": "DOC_CM_001"},
        "EDITING_SOFTWARE_DETECTED": {"title": "Photo Editing Software in EXIF", "severity": "MEDIUM",  "impact": -10, "code": "DOC_EXIF_001"},
        "EXIF_DATETIME_MISMATCH": {"title": "EXIF DateTime Inconsistency",       "severity": "MEDIUM",  "impact": -8,  "code": "DOC_EXIF_002"},
        "NOISE_INCONSISTENCY":    {"title": "Sensor Noise Inconsistency",         "severity": "MEDIUM",  "impact": -8,  "code": "DOC_NOISE_001"},
        "ID_CHECKSUM_FAIL":       {"title": "ID Number Checksum Invalid",         "severity": "CRITICAL","impact": -30, "code": "DOC_CHK_001"},
        "FIELD_MISMATCH:name":    {"title": "Name Mismatch (OCR vs Form)",        "severity": "HIGH",    "impact": -20, "code": "DOC_FIELD_001"},
        "FIELD_MISMATCH:dob":     {"title": "DOB Mismatch (OCR vs Form)",         "severity": "HIGH",    "impact": -15, "code": "DOC_FIELD_002"},
        "DOC_TAMPERED":           {"title": "Document Tampering Confirmed",        "severity": "CRITICAL","impact": -40, "code": "DOC_TAMP_001"},
        "DOC_ML_UNAVAILABLE":     {"title": "Document ML Service Unavailable",     "severity": "INFO",    "impact": 0,   "code": "DOC_SYS_001"},
        # Biometric
        "FACE_MISMATCH":          {"title": "Face Does Not Match Document",        "severity": "CRITICAL","impact": -35, "code": "BIO_FACE_001"},
        "LIVENESS_FAIL":          {"title": "Liveness Check Failed",               "severity": "CRITICAL","impact": -40, "code": "BIO_LIVE_001"},
        "BIO_DEEPFAKE":           {"title": "Deepfake / Synthetic Face Detected",  "severity": "CRITICAL","impact": -50, "code": "BIO_DF_001"},
        "BIO_ML_UNAVAILABLE":     {"title": "Biometric ML Service Unavailable",    "severity": "INFO",    "impact": 0,   "code": "BIO_SYS_001"},
        # Device
        "EMULATOR_DETECTED":      {"title": "Emulator / Virtual Device",           "severity": "HIGH",    "impact": -20, "code": "DEV_EMU_001"},
        "FRAUD_IP":               {"title": "IP Associated with Prior Fraud",      "severity": "HIGH",    "impact": -18, "code": "DEV_IP_001"},
        "TZ_IP_MISMATCH":         {"title": "Timezone / IP Geolocation Mismatch",  "severity": "LOW",     "impact": -5,  "code": "DEV_TZ_001"},
        "VPN_DATACENTER_IP":      {"title": "VPN / Datacenter IP Detected",        "severity": "MEDIUM",  "impact": -10, "code": "DEV_VPN_001"},
        "SHARED_DEVICE_RISKY":    {"title": "Device Fingerprint Shared with Fraudsters","severity":"MEDIUM","impact":-12, "code":"DEV_FP_001"},
        # Behavioural
        "BOT_PATTERN":            {"title": "Bot / Automation Pattern",            "severity": "HIGH",    "impact": -25, "code": "BEH_BOT_001"},
        "PASTE_HEAVY":            {"title": "Excessive Copy-Paste (Prefill Bot)",  "severity": "MEDIUM",  "impact": -10, "code": "BEH_PASTE_001"},
        "INSTANT_FILL":           {"title": "Instant Form Fill (Suspicious Speed)","severity": "MEDIUM",  "impact": -8,  "code": "BEH_SPD_001"},
        # Graph
        "GRAPH_DUPLICATE":        {"title": "Duplicate Identity Detected",         "severity": "CRITICAL","impact": -50, "code": "GR_DUP_001"},
        "GRAPH_RING_MEMBER":      {"title": "Fraud Ring Membership Detected",      "severity": "CRITICAL","impact": -40, "code": "GR_RING_001"},
        "SHARED_DEVICE":          {"title": "Device Shared with Prior Applicants", "severity": "MEDIUM",  "impact": -12, "code": "GR_DEV_001"},
        "SHARED_IP":              {"title": "IP Shared with Prior Applicants",     "severity": "MEDIUM",  "impact": -8,  "code": "GR_IP_001"},
    }

    seen = set()
    for stage, flags in stage_flags.items():
        for flag in flags:
            if flag in seen:
                continue
            seen.add(flag)
            meta = flag_catalog.get(flag)
            if meta:
                codes.append({
                    "code": meta["code"],
                    "title": meta["title"],
                    "severity": meta["severity"],
                    "score_impact": meta["impact"],
                    "message": f"Detected in {stage} stage.",
                    "stage": stage,
                })

    return sorted(codes, key=lambda x: {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3, "INFO": 4}[x["severity"]])


def _cross_signal_penalty(pipeline: dict) -> float:
    """Extra deduction when multiple high-severity stages are simultaneously bad."""
    bad_count = sum(
        1 for stage, data in pipeline.items()
        if data.get("score", 100) < 50
    )
    if bad_count >= 3:
        return 10.0
    if bad_count == 2:
        return 5.0
    return 0.0


def fuse(pipeline: dict, weights: dict, thresholds: dict) -> dict:
    # Weighted base score
    weighted = sum(
        pipeline[stage]["score"] * weights.get(stage, 0.0)
        for stage in weights
        if stage in pipeline
    )
    penalty = _cross_signal_penalty(pipeline)
    trust_score = max(0.0, min(100.0, weighted - penalty))

    # Collect all flags
    all_flags = set()
    for data in pipeline.values():
        all_flags.update(data.get("flags", []))

    # Hard-fail overrides
    override_reject = all_flags & _HARD_REJECT
    override_manual = all_flags & _HARD_MANUAL

    if override_reject:
        decision = "REJECT"
    elif override_manual:
        decision = "MANUAL_REVIEW"
    else:
        decision = _score_to_decision(trust_score, thresholds)

    reason_codes = _build_reason_codes(pipeline)
    risk_band = _risk_band(decision, trust_score)

    return {
        "trust_score": round(trust_score, 1),
        "risk_band": risk_band,
        "decision": decision,
        "reason_codes": reason_codes,
        "cross_signal_penalty": penalty,
        "override": list(override_reject | override_manual),
    }
