"""
TrustLayer – Biometric Verification Simulator
=============================================
Produces realistic face-match / liveness / deepfake scores.
Outputs are deterministic (selfie_hash + scenario).
"""
from __future__ import annotations
import hashlib
from dataclasses import dataclass, field


@dataclass
class BiometricResult:
    score: float                   # 0-100 composite

    # Face match
    face_match_score: float        # 0-1  (selfie vs document photo)
    face_match_confidence: float   # model confidence in the match score

    # Liveness
    liveness_score: float          # 0-1
    liveness_passed: bool
    blink_detected: bool
    head_pose_variance: float      # 0-1  (higher = more natural movement)
    texture_liveness_score: float  # 0-1  (anti-spoofing texture analysis)

    # Deepfake / injection
    deepfake_probability: float    # 0-1
    injection_attack_probability: float  # 0-1  (virtual camera / image injection)
    gan_artifact_score: float      # 0-1  (higher = more GAN artifacts detected)

    # Quality
    image_quality_score: float     # 0-1
    lighting_score: float          # 0-1
    occlusion_score: float         # 0-1  (glasses / mask / hand obscuring face)

    flags: list[str] = field(default_factory=list)


_PROFILES: dict[str, dict] = {
    "genuine_user": {
        "score": 93,
        "face_match_score": 0.96,
        "face_match_confidence": 0.98,
        "liveness_score": 0.97,
        "liveness_passed": True,
        "blink_detected": True,
        "head_pose_variance": 0.82,
        "texture_liveness_score": 0.95,
        "deepfake_probability": 0.02,
        "injection_attack_probability": 0.01,
        "gan_artifact_score": 0.03,
        "image_quality_score": 0.94,
        "lighting_score": 0.91,
        "occlusion_score": 0.02,
        "flags": [],
    },
    "synthetic_identity": {
        "score": 46,
        "face_match_score": 0.52,       # face doesn't match doc photo (assembled from stock)
        "face_match_confidence": 0.68,
        "liveness_score": 0.71,
        "liveness_passed": True,
        "blink_detected": True,
        "head_pose_variance": 0.48,
        "texture_liveness_score": 0.55,
        "deepfake_probability": 0.29,
        "injection_attack_probability": 0.22,
        "gan_artifact_score": 0.38,
        "image_quality_score": 0.72,
        "lighting_score": 0.64,
        "occlusion_score": 0.18,
        "flags": ["LOW_FACE_MATCH", "POSSIBLE_STOCK_PHOTO", "MODERATE_GAN_SIGNAL"],
    },
    "deepfake_attempt": {
        "score": 7,
        "face_match_score": 0.88,       # deepfake trained on the target – looks like a match
        "face_match_confidence": 0.54,  # but model confidence is low (inconsistencies)
        "liveness_score": 0.09,
        "liveness_passed": False,
        "blink_detected": False,
        "head_pose_variance": 0.11,
        "texture_liveness_score": 0.08,
        "deepfake_probability": 0.94,
        "injection_attack_probability": 0.88,
        "gan_artifact_score": 0.91,
        "image_quality_score": 0.71,
        "lighting_score": 0.65,
        "occlusion_score": 0.05,
        "flags": [
            "LIVENESS_FAILED",
            "DEEPFAKE_HIGH_CONFIDENCE",
            "INJECTION_ATTACK_SUSPECTED",
            "GAN_ARTIFACTS_DETECTED",
            "NO_NATURAL_BLINK",
        ],
    },
    "tampered_document": {
        "score": 61,
        "face_match_score": 0.58,       # photo on tampered doc doesn't match
        "face_match_confidence": 0.80,
        "liveness_score": 0.84,
        "liveness_passed": True,
        "blink_detected": True,
        "head_pose_variance": 0.75,
        "texture_liveness_score": 0.82,
        "deepfake_probability": 0.08,
        "injection_attack_probability": 0.06,
        "gan_artifact_score": 0.07,
        "image_quality_score": 0.86,
        "lighting_score": 0.83,
        "occlusion_score": 0.05,
        "flags": ["FACE_DOC_MISMATCH"],
    },
    "fraud_ring_member": {
        "score": 82,
        "face_match_score": 0.89,
        "face_match_confidence": 0.93,
        "liveness_score": 0.91,
        "liveness_passed": True,
        "blink_detected": True,
        "head_pose_variance": 0.79,
        "texture_liveness_score": 0.88,
        "deepfake_probability": 0.06,
        "injection_attack_probability": 0.04,
        "gan_artifact_score": 0.05,
        "image_quality_score": 0.89,
        "lighting_score": 0.86,
        "occlusion_score": 0.04,
        "flags": [],
    },
    "duplicate_identity": {
        "score": 89,
        "face_match_score": 0.95,
        "face_match_confidence": 0.97,
        "liveness_score": 0.94,
        "liveness_passed": True,
        "blink_detected": True,
        "head_pose_variance": 0.84,
        "texture_liveness_score": 0.93,
        "deepfake_probability": 0.03,
        "injection_attack_probability": 0.02,
        "gan_artifact_score": 0.03,
        "image_quality_score": 0.92,
        "lighting_score": 0.90,
        "occlusion_score": 0.02,
        "flags": [],
    },
}

_DEFAULT_PROFILE = _PROFILES["genuine_user"]


def _nudge(base: float, h: int, factor: float = 0.03) -> float:
    jitter = ((h % 100) / 100 - 0.5) * factor
    return round(max(0.0, min(1.0, base + jitter)), 4)


def analyse_biometrics(
    selfie_hash: str,
    doc_hash: str,
    scenario: str = "genuine_user",
) -> BiometricResult:
    p = _PROFILES.get(scenario, _DEFAULT_PROFILE)
    h = int(hashlib.sha256((selfie_hash + doc_hash).encode()).hexdigest()[:8], 16)

    score = p["score"] + int((h % 9) - 4)
    score = max(0, min(100, score))

    return BiometricResult(
        score=float(score),
        face_match_score=_nudge(p["face_match_score"], h),
        face_match_confidence=_nudge(p["face_match_confidence"], h),
        liveness_score=_nudge(p["liveness_score"], h),
        liveness_passed=p["liveness_passed"],
        blink_detected=p["blink_detected"],
        head_pose_variance=_nudge(p["head_pose_variance"], h),
        texture_liveness_score=_nudge(p["texture_liveness_score"], h),
        deepfake_probability=_nudge(p["deepfake_probability"], h, 0.02),
        injection_attack_probability=_nudge(p["injection_attack_probability"], h, 0.02),
        gan_artifact_score=_nudge(p["gan_artifact_score"], h, 0.02),
        image_quality_score=_nudge(p["image_quality_score"], h),
        lighting_score=_nudge(p["lighting_score"], h),
        occlusion_score=_nudge(p["occlusion_score"], h, 0.02),
        flags=list(p["flags"]),
    )
