"""
PaddleOCR-based OCR for KYC documents (Aadhaar, PAN, Passport, Driving Licence).
Extracts structured fields: name, DOB, ID number, address.
Supports Hindi + English (multilingual).
"""
import re
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Optional
import structlog

log = structlog.get_logger(__name__)

try:
    from paddleocr import PaddleOCR
    HAS_PADDLE = True
except ImportError:
    HAS_PADDLE = False
    log.warning("PaddleOCR not installed; OCR stage will return empty results")


@lru_cache(maxsize=1)
def _get_ocr_engine(lang: str = "en", use_angle: bool = True, use_gpu: bool = True):
    if not HAS_PADDLE:
        return None
    return PaddleOCR(
        use_angle_cls=use_angle,
        lang=lang,
        use_gpu=use_gpu,
        show_log=False,
        enable_mkldnn=False,
    )


@dataclass
class OCRResult:
    raw_text: str = ""
    confidence: float = 0.0
    fields: dict = field(default_factory=dict)  # name, dob, id_number, address
    doc_type_detected: str = ""
    lines: list[dict] = field(default_factory=list)   # [{text, conf, bbox}]
    error: Optional[str] = None


# ── Field extractors ──────────────────────────────────────────────────────────

def _extract_pan_fields(text: str) -> dict:
    fields: dict = {}
    lines = [l.strip() for l in text.splitlines() if l.strip()]

    # PAN number: 5 letters + 4 digits + 1 letter
    for line in lines:
        m = re.search(r"\b([A-Z]{5}[0-9]{4}[A-Z])\b", line.upper())
        if m:
            fields["id_number"] = m.group(1)
            break

    # DOB: DD/MM/YYYY or DD-MM-YYYY
    for line in lines:
        m = re.search(r"\b(\d{2}[/\-]\d{2}[/\-]\d{4})\b", line)
        if m:
            fields["dob"] = m.group(1).replace("-", "/")
            break

    # Name: usually the line after "Name" or the second line
    for i, line in enumerate(lines):
        if re.search(r"\bname\b", line, re.I):
            if i + 1 < len(lines) and not re.search(r"\bfather\b", lines[i+1], re.I):
                fields["name"] = lines[i + 1]
                break

    return fields


def _extract_aadhaar_fields(text: str) -> dict:
    fields: dict = {}
    lines = [l.strip() for l in text.splitlines() if l.strip()]

    # Aadhaar number: 12 digits (may be space-separated in groups of 4)
    full_text = " ".join(lines)
    m = re.search(r"\b(\d{4}\s?\d{4}\s?\d{4})\b", full_text)
    if m:
        fields["id_number"] = re.sub(r"\s", "", m.group(1))

    # DOB
    for line in lines:
        m = re.search(r"\b(\d{2}[/\-]\d{2}[/\-]\d{4})\b", line)
        if m:
            fields["dob"] = m.group(1).replace("-", "/")
            break

    # Name: usually the first large-text line
    for line in lines:
        if re.search(r"\baadhaar\b|\buidai\b|\bunique\b", line, re.I):
            continue
        if len(line) > 4 and re.match(r"^[A-Za-z\s\.]+$", line):
            fields["name"] = line.strip()
            break

    # Address: multi-line after "Address"
    addr_lines = []
    in_addr = False
    for line in lines:
        if re.search(r"\baddress\b", line, re.I):
            in_addr = True
            continue
        if in_addr:
            if re.search(r"\bpin\b|\bpin code\b|\d{6}", line, re.I):
                addr_lines.append(line)
                break
            addr_lines.append(line)
    if addr_lines:
        fields["address"] = ", ".join(addr_lines)

    return fields


def _extract_passport_fields(text: str) -> dict:
    fields: dict = {}
    lines = [l.strip() for l in text.splitlines() if l.strip()]

    # MRZ lines (2 lines of 44 chars for TD3)
    mrz = [l for l in lines if re.match(r"^[A-Z0-9<]{40,}$", l.upper())]
    if len(mrz) >= 2:
        line1, line2 = mrz[0].upper(), mrz[1].upper()
        fields["mrz_line1"] = line1
        fields["mrz_line2"] = line2
        # Passport number: positions 1-9 of line 2
        fields["id_number"] = line2[:9].rstrip("<")
        # DOB: positions 14-19 of line 2 (YYMMDD)
        dob_raw = line2[13:19]
        if re.match(r"\d{6}", dob_raw):
            fields["dob"] = f"{dob_raw[4:6]}/{dob_raw[2:4]}/{'19' if int(dob_raw[:2])>30 else '20'}{dob_raw[:2]}"
        # Name: from line 1 positions 6+
        name_raw = line1[5:].replace("<<", " / ").replace("<", " ").strip()
        fields["name"] = name_raw

    return fields


_DOC_EXTRACTORS = {
    "PAN": _extract_pan_fields,
    "AADHAAR": _extract_aadhaar_fields,
    "PASSPORT": _extract_passport_fields,
}


def _detect_doc_type(text: str) -> str:
    text_upper = text.upper()
    if "INCOME TAX" in text_upper or "PERMANENT ACCOUNT" in text_upper:
        return "PAN"
    if "AADHAAR" in text_upper or "UIDAI" in text_upper or "UNIQUE IDENTIFICATION" in text_upper:
        return "AADHAAR"
    if "PASSPORT" in text_upper or "REPUBLIC OF INDIA" in text_upper:
        return "PASSPORT"
    if "DRIVING LICENCE" in text_upper or "MOTOR VEHICLE" in text_upper:
        return "DRIVING_LICENSE"
    return "UNKNOWN"


# ── Main entry point ──────────────────────────────────────────────────────────

def run_ocr(
    image_bytes: bytes,
    doc_type_hint: str = "",
    use_gpu: bool = True,
    lang: str = "en",
) -> OCRResult:
    result = OCRResult()

    engine = _get_ocr_engine(lang=lang, use_gpu=use_gpu)
    if engine is None:
        result.error = "PaddleOCR not available"
        result.confidence = 0.0
        return result

    try:
        import numpy as np
        arr = np.frombuffer(image_bytes, np.uint8)
        import cv2
        img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if img is None:
            result.error = "Failed to decode image"
            return result

        ocr_output = engine.ocr(img, cls=True)
    except Exception as e:
        result.error = str(e)
        log.error("ocr_failed", error=str(e))
        return result

    if not ocr_output or not ocr_output[0]:
        result.error = "No text detected"
        return result

    lines = []
    texts = []
    confs = []
    for item in ocr_output[0]:
        if item is None:
            continue
        bbox, (text, conf) = item
        lines.append({"text": text, "confidence": round(float(conf), 3), "bbox": [list(map(float, pt)) for pt in bbox]})
        texts.append(text)
        confs.append(float(conf))

    result.lines = lines
    result.raw_text = "\n".join(texts)
    result.confidence = float(sum(confs) / len(confs)) if confs else 0.0

    # Detect doc type
    detected = _detect_doc_type(result.raw_text)
    result.doc_type_detected = detected if detected != "UNKNOWN" else doc_type_hint.upper()

    # Extract structured fields
    extractor = _DOC_EXTRACTORS.get(result.doc_type_detected.upper())
    if extractor:
        result.fields = extractor(result.raw_text)
    else:
        # Generic extraction fallback
        result.fields = {}

    return result
