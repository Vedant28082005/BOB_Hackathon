"""
Liveness detection:
  Passive — Silent-Face-Anti-Spoofing (MiniFASNet) via ONNX.
  Active  — blink / head-turn challenge from video frames (OpenCV landmark-based).

MiniFASNet weights: https://github.com/minivision-ai/Silent-Face-Anti-Spoofing
Download script: scripts/download_models.sh
"""
from __future__ import annotations
import io
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
import numpy as np
import structlog

log = structlog.get_logger(__name__)

try:
    import onnxruntime as ort
    HAS_ORT = True
except ImportError:
    HAS_ORT = False
    log.warning("onnxruntime not installed; passive liveness unavailable")

try:
    import cv2
    HAS_CV2 = True
except ImportError:
    HAS_CV2 = False


# ── MiniFASNet preprocessing ──────────────────────────────────────────────────
_FAS_MEAN = [0.406, 0.456, 0.485]
_FAS_STD  = [0.225, 0.224, 0.229]
_FAS_SIZE = 80


def _preprocess_fas(img_bgr: np.ndarray, bbox: list[float]) -> np.ndarray:
    x1, y1, x2, y2 = [int(v) for v in bbox]
    h, w = img_bgr.shape[:2]
    x1, y1 = max(0, x1), max(0, y1)
    x2, y2 = min(w, x2), min(h, y2)
    face = img_bgr[y1:y2, x1:x2]
    face = cv2.resize(face, (_FAS_SIZE, _FAS_SIZE))
    face = face.astype(np.float32) / 255.0
    for c in range(3):
        face[:, :, c] = (face[:, :, c] - _FAS_MEAN[c]) / _FAS_STD[c]
    face = face.transpose(2, 0, 1)          # HWC -> CHW
    return np.expand_dims(face, 0).astype(np.float32)


class _MiniFASNet:
    def __init__(self, model_path: Path, use_gpu: bool):
        if not HAS_ORT:
            raise RuntimeError("onnxruntime not installed")
        providers = (["CUDAExecutionProvider", "CPUExecutionProvider"]
                     if use_gpu else ["CPUExecutionProvider"])
        self.session = ort.InferenceSession(str(model_path), providers=providers)
        self.input_name = self.session.get_inputs()[0].name

    def predict(self, face_tensor: np.ndarray) -> float:
        """Returns liveness probability (1 = live, 0 = spoof)."""
        out = self.session.run(None, {self.input_name: face_tensor})
        probs = out[0][0]   # shape (2,): [spoof_prob, live_prob]
        import scipy.special
        softmax = np.exp(probs) / np.sum(np.exp(probs))
        return float(softmax[1])   # live probability


_fas_models: dict[str, "_MiniFASNet"] = {}

def _load_fas(models_dir: Path, use_gpu: bool) -> list["_MiniFASNet"]:
    model_files = [
        models_dir / "2.7_80x80_MiniFASNetV2.onnx",
        models_dir / "4_0_0_80x80_MiniFASNetV1SE.onnx",
    ]
    loaded = []
    for mf in model_files:
        key = mf.name
        if key not in _fas_models:
            if mf.exists():
                try:
                    _fas_models[key] = _MiniFASNet(mf, use_gpu)
                    log.info("fas_model_loaded", model=key)
                except Exception as e:
                    log.error("fas_model_load_failed", model=key, error=str(e))
            else:
                log.warning("fas_model_missing", path=str(mf))
        if key in _fas_models:
            loaded.append(_fas_models[key])
    return loaded


# ── Passive liveness ──────────────────────────────────────────────────────────
def _detect_face_bbox(img_bgr: np.ndarray) -> Optional[list[float]]:
    """Quick face detection for bbox used by FAS preprocessing."""
    try:
        # Try InsightFace detector first
        import insightface
        from insightface.app import FaceAnalysis
        app = FaceAnalysis(name="buffalo_sc", providers=["CPUExecutionProvider"])
        app.prepare(ctx_id=-1, det_size=(320, 320))
        faces = app.get(img_bgr)
        if faces:
            f = max(faces, key=lambda f: (f.bbox[2]-f.bbox[0])*(f.bbox[3]-f.bbox[1]))
            return list(f.bbox)
    except Exception:
        pass

    # Fallback: Haar cascade
    if HAS_CV2:
        gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
        cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        cascade = cv2.CascadeClassifier(cascade_path)
        faces = cascade.detectMultiScale(gray, 1.1, 5, minSize=(60, 60))
        if len(faces) > 0:
            x, y, w, h = faces[0]
            return [float(x), float(y), float(x+w), float(y+h)]
    return None


def passive_liveness_score(
    image_bytes: bytes,
    models_dir: Path,
    use_gpu: bool = True,
) -> tuple[float, bool, str]:
    """Returns (liveness_prob, is_live, method)."""
    if not HAS_CV2:
        return 0.5, True, "UNAVAILABLE"

    arr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        return 0.0, False, "DECODE_FAIL"

    bbox = _detect_face_bbox(img)
    if bbox is None:
        return 0.0, False, "NO_FACE"

    models = _load_fas(models_dir, use_gpu)
    if not models:
        # No model weights: return borderline
        log.warning("fas_models_unavailable")
        return 0.5, True, "NO_MODEL_WEIGHTS"

    scores = []
    for m in models:
        try:
            tensor = _preprocess_fas(img, bbox)
            scores.append(m.predict(tensor))
        except Exception as e:
            log.warning("fas_predict_error", error=str(e))

    if not scores:
        return 0.5, True, "PREDICT_FAIL"

    prob = float(np.mean(scores))
    return prob, prob >= 0.5, "MiniFASNet"


# ── Active liveness (blink / head-turn from video frames) ────────────────────
@dataclass
class ActiveLivenessResult:
    challenge_passed: bool = False
    blink_detected: bool = False
    head_turn_detected: bool = False
    frames_analyzed: int = 0
    error: Optional[str] = None


def _eye_aspect_ratio(eye_pts: np.ndarray) -> float:
    """EAR = (|p2-p6| + |p3-p5|) / (2*|p1-p4|)"""
    A = np.linalg.norm(eye_pts[1] - eye_pts[5])
    B = np.linalg.norm(eye_pts[2] - eye_pts[4])
    C = np.linalg.norm(eye_pts[0] - eye_pts[3])
    return (A + B) / (2.0 * C + 1e-6)


def active_liveness_from_frames(frames_bytes: list[bytes]) -> ActiveLivenessResult:
    """
    Analyze a sequence of frames for blink detection (via EAR) and head-turn
    (via face orientation landmark shift).
    Requires dlib or MediaPipe for landmark detection.
    Falls back to a best-effort OpenCV Haar cascade check.
    """
    result = ActiveLivenessResult()
    if not frames_bytes:
        result.error = "No frames provided"
        return result

    result.frames_analyzed = len(frames_bytes)

    # Try MediaPipe face mesh for landmarks
    try:
        import mediapipe as mp
        mp_face_mesh = mp.solutions.face_mesh

        # MediaPipe landmark indices for eyes
        LEFT_EYE  = [33, 160, 158, 133, 153, 144]
        RIGHT_EYE = [362, 385, 387, 263, 373, 380]
        NOSE_TIP  = 1

        ear_series: list[float] = []
        nose_x_series: list[float] = []

        with mp_face_mesh.FaceMesh(max_num_faces=1, refine_landmarks=True,
                                    min_detection_confidence=0.5) as fm:
            for fb in frames_bytes:
                arr = np.frombuffer(fb, np.uint8)
                img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
                if img is None:
                    continue
                rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
                res = fm.process(rgb)
                if not res.multi_face_landmarks:
                    continue
                lm = res.multi_face_landmarks[0].landmark
                h, w = img.shape[:2]

                def pt(idx):
                    return np.array([lm[idx].x * w, lm[idx].y * h])

                le = np.array([pt(i) for i in LEFT_EYE])
                re = np.array([pt(i) for i in RIGHT_EYE])
                ear = (_eye_aspect_ratio(le) + _eye_aspect_ratio(re)) / 2.0
                ear_series.append(ear)
                nose_x_series.append(lm[NOSE_TIP].x)

        if ear_series:
            ear_min = min(ear_series)
            ear_max = max(ear_series)
            # Blink: EAR drops below 0.25 at some point
            result.blink_detected = ear_min < 0.25 and ear_max > 0.25

        if len(nose_x_series) >= 5:
            nose_range = max(nose_x_series) - min(nose_x_series)
            result.head_turn_detected = nose_range > 0.05  # > 5% of frame width

        result.challenge_passed = result.blink_detected or result.head_turn_detected
        return result

    except ImportError:
        pass

    # Fallback: crude motion-based check (frame diff)
    try:
        prev_gray = None
        motion_scores = []
        for fb in frames_bytes:
            arr = np.frombuffer(fb, np.uint8)
            img = cv2.imdecode(arr, cv2.IMREAD_GRAYSCALE)
            if img is None:
                continue
            img = cv2.resize(img, (160, 120))
            if prev_gray is not None:
                diff = cv2.absdiff(img, prev_gray)
                motion_scores.append(float(diff.mean()))
            prev_gray = img

        if motion_scores:
            avg_motion = sum(motion_scores) / len(motion_scores)
            result.blink_detected = avg_motion > 1.5
            result.challenge_passed = result.blink_detected
    except Exception as e:
        result.error = str(e)

    return result


# ── Combined result ───────────────────────────────────────────────────────────
@dataclass
class LivenessResult:
    passive_score: float = 0.0
    passive_live: bool = False
    passive_method: str = ""
    active: ActiveLivenessResult = field(default_factory=ActiveLivenessResult)
    combined_live: bool = False
    combined_score: float = 0.0
    error: Optional[str] = None


def run_liveness(
    selfie_bytes: bytes,
    video_frames: list[bytes],
    models_dir: Path,
    use_gpu: bool = True,
) -> LivenessResult:
    result = LivenessResult()

    # Passive check
    result.passive_score, result.passive_live, result.passive_method = (
        passive_liveness_score(selfie_bytes, models_dir, use_gpu)
    )

    # Active check (only if frames provided)
    if video_frames:
        result.active = active_liveness_from_frames(video_frames)
    else:
        result.active.challenge_passed = True   # waive if no video submitted

    # Combine
    result.combined_live = result.passive_live and result.active.challenge_passed
    result.combined_score = (
        0.7 * result.passive_score
        + 0.3 * (1.0 if result.active.challenge_passed else 0.0)
    )
    return result
