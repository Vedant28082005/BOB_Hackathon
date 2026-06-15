from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    service_host: str = "0.0.0.0"
    service_port: int = 8001
    log_level: str = "INFO"

    # GPU / compute
    use_gpu: bool = True
    gpu_device_id: int = 0

    # Model paths (auto-downloaded if missing)
    models_dir: Path = Path("./model_weights")

    # InsightFace model name (buffalo_l = ArcFace R100)
    insightface_model: str = "buffalo_l"
    face_match_threshold: float = 0.40   # cosine distance; < threshold = same person

    # Silent-Face-Anti-Spoofing model paths
    fas_model_2_7: str = "2.7_80x80_MiniFASNetV2.onnx"
    fas_model_4:   str = "4_0_0_80x80_MiniFASNetV1SE.onnx"

    # Deepfake detector
    deepfake_model: str = "efficientnet_b4_deepfake.pt"
    deepfake_threshold: float = 0.55   # prob > threshold = deepfake

    # PaddleOCR
    ocr_lang: str = "en"              # "en" handles PAN/Aadhaar mixed script
    ocr_use_angle: bool = True

    # ELA forensics
    ela_quality: int = 90             # JPEG recompression quality for ELA

    # Internal API auth
    internal_api_key: str = "change_me_in_production"


settings = Settings()
