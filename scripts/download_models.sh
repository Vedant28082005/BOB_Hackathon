#!/bin/bash
# TrustLayer model weight downloader
# Run from project root: bash scripts/download_models.sh

set -e

MODEL_DIR="ml-service/model_weights"
mkdir -p "$MODEL_DIR"

echo "=== TrustLayer Model Weight Downloader ==="
echo "Target: $MODEL_DIR"
echo ""

# ── PaddleOCR (auto-downloaded by paddleocr on first use) ─────────────────────
echo "[1/4] PaddleOCR — will auto-download on first inference (no manual step needed)"

# ── InsightFace buffalo_l (auto-downloaded by insightface on first use) ────────
echo "[2/4] InsightFace buffalo_l — will auto-download on first inference"
echo "      Default cache: ~/.insightface/models/buffalo_l/"

# ── Silent-Face-Anti-Spoofing (MiniFASNet ONNX) ───────────────────────────────
echo "[3/4] Downloading MiniFASNet liveness models…"
FAS_BASE="https://github.com/minivision-ai/Silent-Face-Anti-Spoofing/raw/master/resources/anti_spoof_models"
wget -q --show-progress -O "$MODEL_DIR/2.7_80x80_MiniFASNetV2.onnx" \
    "$FAS_BASE/2.7_80x80_MiniFASNetV2.onnx" 2>/dev/null || \
    echo "  WARNING: Could not download MiniFASNetV2. Manual download from:"
    echo "  https://github.com/minivision-ai/Silent-Face-Anti-Spoofing"

wget -q --show-progress -O "$MODEL_DIR/4_0_0_80x80_MiniFASNetV1SE.onnx" \
    "$FAS_BASE/4_0_0_80x80_MiniFASNetV1SE.onnx" 2>/dev/null || \
    echo "  WARNING: Could not download MiniFASNetV1SE."

# ── Deepfake detector (EfficientNet-B4) ───────────────────────────────────────
echo "[4/4] Deepfake detector weights…"
echo "  Option A: Selim Seferbekov's DFDC winning solution weights:"
echo "    https://www.kaggle.com/models/selimsef/dfdc-deepfake-challenge"
echo ""
echo "  Option B: Use any EfficientNet-B4 binary classifier fine-tuned on"
echo "    FaceForensics++. Place the .pt file at:"
echo "    $MODEL_DIR/efficientnet_b4_deepfake.pt"
echo ""
echo "  Option C (Hugging Face — if available):"
if python3 -c "from huggingface_hub import hf_hub_download" 2>/dev/null; then
    python3 -c "
from huggingface_hub import hf_hub_download
import shutil, os
try:
    path = hf_hub_download(
        repo_id='selimsef/dfdc_deepfake_challenge',
        filename='efficientnet_b4_deepfake.pt',
        local_dir='$MODEL_DIR',
    )
    print('  Downloaded deepfake model from Hugging Face:', path)
except Exception as e:
    print('  Could not download from HF:', e)
    print('  Model will run in GAN-artifact-only fallback mode.')
" || true
else
    echo "  huggingface_hub not installed. pip install huggingface_hub"
fi

echo ""
echo "=== Download complete ==="
echo "Model directory contents:"
ls -lh "$MODEL_DIR" 2>/dev/null || echo "(empty)"
echo ""
echo "GeoIP database (MaxMind GeoLite2-City.mmdb):"
echo "  1. Register free account at https://dev.maxmind.com/"
echo "  2. Download GeoLite2-City.mmdb"
echo "  3. Place at: backend/data/GeoLite2-City.mmdb"
