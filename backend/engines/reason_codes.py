"""
TrustLayer – Reason Code Registry
===================================
Canonical catalogue of all reason codes the system can emit.
"""
from __future__ import annotations
from dataclasses import dataclass


@dataclass(frozen=True)
class RCDefinition:
    code: str
    severity: str   # INFO | LOW | MEDIUM | HIGH | CRITICAL
    title: str
    message_template: str
    score_impact: float   # typical negative impact on trust score


REGISTRY: dict[str, RCDefinition] = {rc.code: rc for rc in [
    # ── Document ────────────────────────────────────────────────────────────
    RCDefinition("DOC_AUTHENTIC",       "INFO",     "Document Verified",
        "Document forensics returned a high-confidence authenticity verdict.", 0.0),
    RCDefinition("DOC_LOW_QUALITY",     "LOW",      "Low Document Image Quality",
        "The document image quality is below acceptable thresholds; re-capture may improve accuracy.", -3.0),
    RCDefinition("DOC_NAME_MISMATCH",   "HIGH",     "Name Mismatch: Document vs Application",
        "The name extracted via OCR ({extracted}) differs significantly from the name provided ({entered}).", -18.0),
    RCDefinition("DOC_DOB_MISMATCH",    "HIGH",     "Date-of-Birth Mismatch",
        "The date of birth on the document does not match the submitted application data.", -15.0),
    RCDefinition("DOC_MINOR_ANOMALY",   "LOW",      "Minor Document Anomalies Detected",
        "Low-severity formatting anomalies detected; may indicate a low-resolution scan rather than tampering.", -4.0),
    RCDefinition("DOC_TAMPER_SUSPECTED","HIGH",     "Document Tampering Suspected",
        "Multiple forensic signals indicate the document may have been digitally altered.", -25.0),
    RCDefinition("DOC_TAMPERED",        "CRITICAL", "Document Confirmed Tampered",
        "High-confidence tampering detection: pixel-level inconsistencies, font substitution, and metadata anomalies present.", -40.0),

    # ── Biometric ────────────────────────────────────────────────────────────
    RCDefinition("BIO_CLEAR",           "INFO",     "Biometrics Verified",
        "Face match, liveness, and anti-spoofing checks all passed with high confidence.", 0.0),
    RCDefinition("BIO_LOW_FACE_MATCH",  "HIGH",     "Low Face-Match Score",
        "The selfie does not sufficiently match the document photograph (match score: {score:.0%}).", -20.0),
    RCDefinition("BIO_LIVENESS_FAIL",   "CRITICAL", "Liveness Check Failed",
        "The selfie did not pass liveness detection — a static image or replay attack may be in use.", -35.0),
    RCDefinition("BIO_DEEPFAKE",        "CRITICAL", "Deepfake / AI-Generated Face Detected",
        "Model confidence of AI-generated or manipulated face imagery: {prob:.0%}. Submission rejected.", -45.0),
    RCDefinition("BIO_INJECTION",       "CRITICAL", "Virtual Camera Injection Suspected",
        "Signals consistent with image injection via virtual camera or emulator detected.", -30.0),
    RCDefinition("BIO_FACE_DOC_MISMATCH","HIGH",    "Face–Document Photo Mismatch",
        "The submitted selfie does not match the photo on the provided identity document.", -22.0),

    # ── Device ────────────────────────────────────────────────────────────────
    RCDefinition("DEV_CLEAN",           "INFO",     "Device Signals Normal",
        "No suspicious device or network signals detected.", 0.0),
    RCDefinition("DEV_TZ_IP_MISMATCH",  "LOW",      "Timezone / IP-Geolocation Mismatch",
        "The browser's reported timezone ({tz}) is inconsistent with the inferred IP geolocation region.", -5.0),
    RCDefinition("DEV_EMULATOR",        "HIGH",     "Emulator or Virtual Device Suspected",
        "User-agent and platform signals suggest the session may be running inside an emulator or virtual machine.", -20.0),
    RCDefinition("DEV_AUTOMATION",      "HIGH",     "Browser Automation Signals Detected",
        "WebDriver or headless browser flags detected in the browser environment.", -25.0),
    RCDefinition("DEV_KNOWN_FRAUD_IP",  "HIGH",     "IP Associated with Prior Fraud",
        "The originating IP address is linked to prior flagged assessment(s) in this system.", -18.0),
    RCDefinition("DEV_SHARED_DEVICE",   "MEDIUM",   "Device Fingerprint Shared with Another Applicant",
        "The device fingerprint matches that of a prior applicant. Possible shared device or spoofing.", -12.0),

    # ── Behavioural ──────────────────────────────────────────────────────────
    RCDefinition("BEH_NORMAL",          "INFO",     "Behavioural Biometrics Normal",
        "Typing cadence and form-fill behaviour are consistent with human interaction.", 0.0),
    RCDefinition("BEH_BOT_SPEED",       "HIGH",     "Superhuman Typing Speed Detected",
        "Average inter-keystroke interval of {avg_ms:.0f} ms is below the human threshold of 40 ms.", -22.0),
    RCDefinition("BEH_BOT_CONSISTENCY", "MEDIUM",   "Unnaturally Consistent Keystroke Timing",
        "Keystroke interval variance ({std:.1f} ms std-dev) is atypically low, suggesting automated input.", -12.0),
    RCDefinition("BEH_FAST_FORM",       "MEDIUM",   "Suspiciously Rapid Form Completion",
        "The form was completed in {duration:.0f} seconds, significantly below the expected minimum.", -10.0),
    RCDefinition("BEH_PASTE_ABUSE",     "MEDIUM",   "Excessive Paste Events",
        "{count} paste events detected. Pre-filled or scripted submissions may indicate automation.", -8.0),

    # ── Identity Graph ────────────────────────────────────────────────────────
    RCDefinition("GRAPH_CLEAN",         "INFO",     "No Graph Anomalies",
        "The applicant has no shared attributes with flagged entities in the identity graph.", 0.0),
    RCDefinition("GRAPH_SHARED_ATTR",   "MEDIUM",   "Shared Attribute with Prior Applicant",
        "One or more identity attributes (device, IP, phone, email) are shared with existing applicant(s).", -10.0),
    RCDefinition("GRAPH_RING_MEMBER",   "CRITICAL", "Fraud Ring Membership Detected",
        "The applicant is connected to a cluster of {size} applicants sharing {attr}. This pattern is consistent with organised fraud.", -40.0),
    RCDefinition("GRAPH_DUPLICATE",     "CRITICAL", "Duplicate Identity Detected",
        "Core identity attributes match an existing applicant ({uuid}). Possible identity reuse or account farming.", -50.0),
]}


def get_definition(code: str) -> RCDefinition:
    return REGISTRY.get(code, RCDefinition(
        code=code, severity="INFO", title=code, message_template=code, score_impact=0.0
    ))
