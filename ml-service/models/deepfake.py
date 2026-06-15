"""
Deepfake detection via EfficientNet-B4 pretrained on FaceForensics++ / DFDC.

Model weights download: scripts/download_models.sh
  - Source: https://github.com/selimsef/dfdc_deepfake_challenge (Selim Seferbekov's
    solution, weights publicly available) OR any compatible EfficientNet-B4 binary
    classifier (sigmoid output: 0=real, 1=fake).

IMPORTANT (production note, written in code per spec):
  Deepfake detection is probabilistic. This implementation uses an open-source
  frame-based detector and should be augmented by a certified vendor solution
  (e.g., iProov, Veriff, or a dedicated deepfake detection API) in regulated
  production environments. Treat probability > threshold as a signal requiring
  human review, not an automatic rejection without additional evidence.
"""
from __future__ import annotations
import io
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
import numpy as np
import structlog

log = structlog.get_logger(__name__)

try:
    import torch
    import torch.nn.functional as F
    import torchvision.transforms as T
    from PIL import Image
    HAS_TORCH = True
except ImportError:
    HAS_TORCH = False
    log.warning("torch not installed; deepfake detection unavailable")

try:
    import timm
    HAS_TIMM = True
except ImportError:
    HAS_TIMM = False


# ── Model loading ──────────────────────────────────────────────────────────────
_deepfake_model: Optional["torch.nn.Module"] = None
_deepfake_device: Optional["torch.device"] = None


def _load_deepfake_model(model_path: Path, use_gpu: bool) -> Optional["torch.nn.Module"]:
    global _deepfake_model, _deepfake_device
    if _deepfake_model is not None:
        return _deepfake_model

    if not HAS_TORCH or not HAS_TIMM:
        log.warning("torch/timm not installed; deepfake model unavailable")
        return None

    device = torch.device("cuda" if use_gpu and torch.cuda.is_available() else "cpu")
    _deepfake_device = device

    # Build EfficientNet-B4 binary classifier
    try:
        model = timm.create_model("efficientnet_b4", pretrained=False, num_classes=1)

        if model_path.exists():
            checkpoint = torch.load(str(model_path), map_location=device)
            # Handle various checkpoint formats
            state_dict = checkpoint.get("state_dict", checkpoint.get("model", checkpoint))
            # Strip "model." prefix if present (some checkpoints have it)
            state_dict = {k.replace("model.", ""): v for k, v in state_dict.items()}
            missing, unexpected = model.load_state_dict(state_dict, strict=False)
            if missing:
                log.warning("deepfake_weights_partial", missing=len(missing))
            log.info("deepfake_model_loaded", path=str(model_path), device=str(device))
        else:
            log.warning("deepfake_weights_missing", path=str(model_path),
                        note="Model will use random weights — download via scripts/download_models.sh")

        model = model.to(device).eval()
        _deepfake_model = model
        return model

    except Exception as e:
        log.error("deepfake_model_load_failed", error=str(e))
        return None


# ── Preprocessing ──────────────────────────────────────────────────────────────
_TRANSFORM = None

def _get_transform():
    global _TRANSFORM
    if _TRANSFORM is None and HAS_TORCH:
        _TRANSFORM = T.Compose([
            T.Resize((380, 380)),
            T.ToTensor(),
            T.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
        ])
    return _TRANSFORM


def _predict_frame(model, device, img_bytes: bytes) -> float:
    """Returns deepfake probability for a single frame (0=real, 1=fake)."""
    try:
        img = Image.open(io.BytesIO(img_bytes)).convert("RGB")
        transform = _get_transform()
        tensor = transform(img).unsqueeze(0).to(device)
        with torch.no_grad():
            logit = model(tensor)
            prob = torch.sigmoid(logit).item()
        return float(prob)
    except Exception as e:
        log.warning("deepfake_frame_predict_error", error=str(e))
        return 0.5   # neutral on error


# ── GAN artifact detection (texture-based heuristic) ─────────────────────────
def _gan_artifact_score(image_bytes: bytes) -> float:
    """
    Detect GAN-specific high-frequency artifacts in the DCT domain.
    Real images show natural falloff; GAN images often have periodic peaks.
    """
    try:
        import cv2
        arr = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_GRAYSCALE)
        if img is None:
            return 0.0
        img = cv2.resize(img, (512, 512)).astype(np.float32)
        dct = cv2.dct(img)
        # Look at energy in high-frequency region vs low-frequency
        h, w = dct.shape
        low = np.sum(np.abs(dct[:h//8, :w//8]))
        high = np.sum(np.abs(dct[h//8:, w//8:]))
        ratio = high / (low + 1e-9)
        # GAN images tend to have elevated high-freq energy
        score = min(1.0, ratio / 50.0)
        return float(score)
    except Exception:
        return 0.0


# ── Result dataclass ──────────────────────────────────────────────────────────
@dataclass
class DeepfakeResult:
    deepfake_probability: float = 0.0
    is_deepfake: bool = False
    frame_probabilities: list[float] = field(default_factory=list)
    gan_artifact_score: float = 0.0
    frames_analyzed: int = 0
    model_used: str = ""
    threshold: float = 0.55
    error: Optional[str] = None
    # Production note
    note: str = (
        "Detection is probabilistic. In regulated production, augment with a "
        "certified deepfake vendor API (iProov, Veriff, etc.)."
    )


def run_deepfake_detection(
    selfie_bytes: bytes,
    video_frames: list[bytes],
    models_dir: Path,
    threshold: float = 0.55,
    use_gpu: bool = True,
) -> DeepfakeResult:
    result = DeepfakeResult(threshold=threshold)

    model_path = models_dir / "efficientnet_b4_deepfake.pt"
    model = _load_deepfake_model(model_path, use_gpu)

    # GAN artifact check (CPU, always available)
    result.gan_artifact_score = _gan_artifact_score(selfie_bytes)

    if model is None:
        # Fallback to GAN artifact score only
        result.deepfake_probability = result.gan_artifact_score * 0.6
        result.is_deepfake = result.deepfake_probability > threshold
        result.model_used = "GAN_ARTIFACT_ONLY"
        result.error = "EfficientNet weights not loaded; using GAN artifact heuristic"
        return result

    # Collect frames to analyze: selfie + up to 8 video frames
    frames_to_check = [selfie_bytes]
    if video_frames:
        # Sample evenly from video
        step = max(1, len(video_frames) // 8)
        frames_to_check.extend(video_frames[::step][:8])

    device = _deepfake_device
    probs = []
    for fb in frames_to_check:
        p = _predict_frame(model, device, fb)
        probs.append(p)

    result.frame_probabilities = probs
    result.frames_analyzed = len(probs)

    if probs:
        # Aggregate: weighted mean (selfie gets 2x weight)
        weights = [2.0] + [1.0] * (len(probs) - 1)
        result.deepfake_probability = float(
            sum(p * w for p, w in zip(probs, weights)) / sum(weights)
        )
        # Incorporate GAN artifact (minor weight)
        result.deepfake_probability = (
            0.85 * result.deepfake_probability + 0.15 * result.gan_artifact_score
        )

    result.is_deepfake = result.deepfake_probability > threshold
    result.model_used = "EfficientNet-B4/FaceForensics++"
    return result
