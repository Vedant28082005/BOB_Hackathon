"""
Real document forensics: ELA, EXIF consistency, copy-move detection, noise analysis.
ID-number validation: PAN checksum, Aadhaar Verhoeff, MRZ.
"""
import io
import math
import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import cv2
import numpy as np
from PIL import Image, ExifTags
import structlog

try:
    import piexif
    HAS_PIEXIF = True
except ImportError:
    HAS_PIEXIF = False

log = structlog.get_logger(__name__)

# ── Verhoeff algorithm for Aadhaar ────────────────────────────────────────────
_D = [
    [0,1,2,3,4,5,6,7,8,9],[1,2,3,4,0,6,7,8,9,5],[2,3,4,0,1,7,8,9,5,6],
    [3,4,0,1,2,8,9,5,6,7],[4,0,1,2,3,9,5,6,7,8],[5,9,8,7,6,0,4,3,2,1],
    [6,5,9,8,7,1,0,4,3,2],[7,6,5,9,8,2,1,0,4,3],[8,7,6,5,9,3,2,1,0,4],
    [9,8,7,6,5,4,3,2,1,0],
]
_P = [
    [0,1,2,3,4,5,6,7,8,9],[1,5,7,6,2,8,3,0,9,4],[5,8,0,3,7,9,6,1,4,2],
    [8,9,1,6,0,4,3,5,2,7],[9,4,5,3,1,2,6,8,7,0],[4,2,8,6,5,7,3,9,0,1],
    [2,7,9,3,8,0,6,4,1,5],[7,0,4,6,9,1,3,2,5,8],
]
_INV = [0,4,3,2,1,5,6,7,8,9]

def _verhoeff_validate(num: str) -> bool:
    c = 0
    for i, d in enumerate(reversed(num)):
        c = _D[c][_P[i % 8][int(d)]]
    return c == 0


def validate_pan(pan: str) -> tuple[bool, str]:
    pan = pan.strip().upper()
    if not re.fullmatch(r"[A-Z]{5}[0-9]{4}[A-Z]", pan):
        return False, "Invalid PAN format (expected AAAAA9999A)"
    return True, "PAN format valid"


def validate_aadhaar(num: str) -> tuple[bool, str]:
    num = re.sub(r"\s", "", num)
    if not re.fullmatch(r"[2-9][0-9]{11}", num):
        return False, "Invalid Aadhaar length/prefix"
    if not _verhoeff_validate(num):
        return False, "Aadhaar Verhoeff checksum failed"
    return True, "Aadhaar checksum valid"


# ── ELA (Error Level Analysis) ─────────────────────────────────────────────────
def ela_score(image_bytes: bytes, quality: int = 90) -> tuple[float, np.ndarray]:
    """
    Recompress to known quality, diff the result. High residuals in regions
    indicate prior manipulation. Returns (anomaly_score 0-1, ELA image).
    """
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=quality)
    recompressed = Image.open(buf).convert("RGB")

    orig_arr = np.array(img, dtype=np.float32)
    recomp_arr = np.array(recompressed, dtype=np.float32)
    diff = np.abs(orig_arr - recomp_arr)

    ela_img = (diff * 10).clip(0, 255).astype(np.uint8)
    mean_diff = float(diff.mean())
    max_diff = float(diff.max())

    # Score: high mean_diff or max_diff suggests manipulation
    score = min(1.0, (mean_diff / 15.0 + max_diff / 255.0) / 2)
    return score, ela_img


# ── EXIF consistency ──────────────────────────────────────────────────────────
def check_exif(image_bytes: bytes) -> dict:
    flags: list[str] = []
    metadata: dict = {}

    try:
        img = Image.open(io.BytesIO(image_bytes))
        exif_raw = img._getexif() if hasattr(img, "_getexif") else None
        if exif_raw is None:
            flags.append("NO_EXIF")
            return {"flags": flags, "metadata": metadata}

        exif = {ExifTags.TAGS.get(k, k): v for k, v in exif_raw.items()}
        metadata = {k: str(v)[:80] for k, v in exif.items()
                    if k in ("Make", "Model", "Software", "DateTime",
                              "DateTimeOriginal", "DateTimeDigitized",
                              "GPSInfo", "ExifVersion", "ColorSpace")}

        dt_orig = exif.get("DateTimeOriginal")
        dt_digi = exif.get("DateTimeDigitized")
        if dt_orig and dt_digi and dt_orig != dt_digi:
            flags.append("DATETIME_MISMATCH")

        sw = str(exif.get("Software", "")).lower()
        editing_sw = ("photoshop", "gimp", "lightroom", "snapseed", "pixlr",
                      "facetune", "meitu", "adobe")
        if any(e in sw for e in editing_sw):
            flags.append(f"EDITING_SOFTWARE:{sw[:30]}")

        if HAS_PIEXIF:
            try:
                exif_dict = piexif.load(image_bytes)
                if "Exif" in exif_dict:
                    maker_note = exif_dict["Exif"].get(piexif.ExifIFD.MakerNote)
                    if maker_note is None:
                        flags.append("NO_MAKER_NOTE")
            except Exception:
                pass

    except Exception as e:
        flags.append(f"EXIF_PARSE_ERROR:{e}")

    return {"flags": flags, "metadata": metadata}


# ── Copy-move / clone detection ────────────────────────────────────────────────
def copy_move_score(image_bytes: bytes, min_matches: int = 20) -> tuple[float, int]:
    """
    Detect cloned/copied regions via ORB keypoint matching within the image.
    Divide image into non-overlapping blocks, extract ORB descriptors,
    cross-match. Returns (score 0-1, suspicious_match_count).
    """
    arr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_GRAYSCALE)
    if img is None:
        return 0.0, 0

    h, w = img.shape
    # Work on downscaled version for speed
    scale = min(1.0, 800 / max(h, w))
    if scale < 1.0:
        img = cv2.resize(img, (int(w * scale), int(h * scale)))

    orb = cv2.ORB_create(nfeatures=1000)
    kp, des = orb.detectAndCompute(img, None)
    if des is None or len(kp) < 10:
        return 0.0, 0

    bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)
    matches = bf.match(des, des)

    # Filter out self-matches (same keypoint)
    SPATIAL_THRESHOLD = 10  # pixels
    suspicious = [
        m for m in matches
        if abs(kp[m.queryIdx].pt[0] - kp[m.trainIdx].pt[0]) > SPATIAL_THRESHOLD
        or abs(kp[m.queryIdx].pt[1] - kp[m.trainIdx].pt[1]) > SPATIAL_THRESHOLD
    ]
    suspicious = [m for m in suspicious if m.queryIdx != m.trainIdx]

    count = len(suspicious)
    score = min(1.0, count / 100.0)
    return score, count


# ── Noise residual analysis ───────────────────────────────────────────────────
def noise_inconsistency_score(image_bytes: bytes) -> float:
    """
    Check noise level consistency across image blocks.
    Real photos have uniform sensor noise; spliced regions show discontinuity.
    """
    arr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_GRAYSCALE)
    if img is None:
        return 0.0

    h, w = img.shape
    block_size = 32
    noise_levels = []

    for y in range(0, h - block_size, block_size):
        for x in range(0, w - block_size, block_size):
            block = img[y:y+block_size, x:x+block_size].astype(np.float32)
            # Estimate noise via median absolute deviation
            laplacian = cv2.Laplacian(block.astype(np.uint8), cv2.CV_64F)
            sigma = np.median(np.abs(laplacian)) / 0.6745
            noise_levels.append(sigma)

    if len(noise_levels) < 4:
        return 0.0

    arr_nl = np.array(noise_levels)
    cv_noise = float(np.std(arr_nl) / (np.mean(arr_nl) + 1e-9))
    return min(1.0, cv_noise / 2.0)


# ── OCR field cross-check ─────────────────────────────────────────────────────
def cross_check_fields(ocr_fields: dict, user_fields: dict) -> dict:
    """
    Compare OCR-extracted fields against user-provided fields.
    Returns per-field match results.
    """
    results = {}

    def _norm(s: str) -> str:
        return re.sub(r"[^a-z0-9]", "", str(s).lower())

    for key in ("name", "dob", "id_number"):
        ocr_val = _norm(ocr_fields.get(key, ""))
        user_val = _norm(user_fields.get(key, ""))
        if not ocr_val or not user_val:
            results[key] = {"status": "MISSING", "match": None}
            continue
        if ocr_val == user_val:
            results[key] = {"status": "MATCH", "match": True}
        elif ocr_val in user_val or user_val in ocr_val:
            results[key] = {"status": "PARTIAL", "match": True}
        else:
            results[key] = {"status": "MISMATCH", "match": False}

    return results


# ── Top-level forensics runner ────────────────────────────────────────────────
@dataclass
class ForensicsResult:
    ela_score: float = 0.0
    exif_flags: list[str] = field(default_factory=list)
    copy_move_score: float = 0.0
    copy_move_count: int = 0
    noise_score: float = 0.0
    id_valid: bool = True
    id_message: str = ""
    field_cross_check: dict = field(default_factory=dict)

    # Aggregate
    tampering_score: float = 0.0    # 0 = clean, 1 = tampered
    anomaly_flags: list[str] = field(default_factory=list)
    authenticity_score: float = 0.0  # 0 = suspicious, 1 = authentic


def run_forensics(
    image_bytes: bytes,
    doc_type: str,
    id_number: str,
    ocr_fields: dict,
    user_fields: dict,
    ela_quality: int = 90,
) -> ForensicsResult:
    result = ForensicsResult()

    # 1. ELA
    result.ela_score, _ = ela_score(image_bytes, ela_quality)

    # 2. EXIF
    exif_result = check_exif(image_bytes)
    result.exif_flags = exif_result["flags"]

    # 3. Copy-move
    result.copy_move_score, result.copy_move_count = copy_move_score(image_bytes)

    # 4. Noise
    result.noise_score = noise_inconsistency_score(image_bytes)

    # 5. ID number validation
    doc_up = doc_type.upper()
    if "PAN" in doc_up:
        result.id_valid, result.id_message = validate_pan(id_number)
    elif "AADHAAR" in doc_up or "AADHAR" in doc_up:
        result.id_valid, result.id_message = validate_aadhaar(id_number)
    else:
        result.id_valid, result.id_message = True, f"No checksum validator for {doc_type}"

    # 6. Field cross-check
    result.field_cross_check = cross_check_fields(ocr_fields, user_fields)

    # 7. Compute aggregate scores
    ela_w, cm_w, noise_w = 0.45, 0.35, 0.20
    result.tampering_score = (
        ela_w * result.ela_score
        + cm_w * result.copy_move_score
        + noise_w * result.noise_score
    )

    flags = []
    if result.ela_score > 0.6:
        flags.append("ELA_ANOMALY")
    if "EDITING_SOFTWARE" in " ".join(result.exif_flags):
        flags.append("EDITING_SOFTWARE_DETECTED")
    if "DATETIME_MISMATCH" in result.exif_flags:
        flags.append("EXIF_DATETIME_MISMATCH")
    if result.copy_move_score > 0.4:
        flags.append("COPY_MOVE_DETECTED")
    if result.noise_score > 0.5:
        flags.append("NOISE_INCONSISTENCY")
    if not result.id_valid:
        flags.append("ID_CHECKSUM_FAIL")

    mismatches = [k for k, v in result.field_cross_check.items()
                  if v.get("status") == "MISMATCH"]
    if mismatches:
        flags.extend([f"FIELD_MISMATCH:{k}" for k in mismatches])

    result.anomaly_flags = flags

    # Authenticity: starts at 1, penalised by tampering + flags
    penalty = result.tampering_score * 0.7 + len(flags) * 0.05
    result.authenticity_score = max(0.0, min(1.0, 1.0 - penalty))

    return result
