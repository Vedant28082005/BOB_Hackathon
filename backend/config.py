"""Central configuration — all values from environment / .env, no secrets in code."""
from __future__ import annotations
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # ── App ───────────────────────────────────────────────────────────────────
    app_name: str = "TrustLayer"
    app_version: str = "2.0.0"
    environment: str = "development"
    debug: bool = False

    # ── Database (PostgreSQL) ─────────────────────────────────────────────────
    database_url: str = "postgresql+asyncpg://trustlayer:trustlayer@localhost:5432/trustlayer"
    db_pool_size: int = 10
    db_max_overflow: int = 20

    # ── Redis ─────────────────────────────────────────────────────────────────
    redis_url: str = "redis://localhost:6379/0"
    cache_ttl_seconds: int = 300
    rate_limit_per_minute: int = 30

    # ── Neo4j ─────────────────────────────────────────────────────────────────
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "trustlayer_neo4j"

    # ── MinIO ─────────────────────────────────────────────────────────────────
    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "trustlayer_minio"
    minio_secret_key: str = "trustlayer_minio_secret"
    minio_bucket: str = "trustlayer-kyc"
    minio_secure: bool = False
    media_retention_hours: int = 24

    # ── ML Service ────────────────────────────────────────────────────────────
    ml_service_url: str = "http://localhost:8001"
    ml_service_api_key: str = "change_me_in_production"
    ml_timeout_seconds: int = 60

    # ── Celery ────────────────────────────────────────────────────────────────
    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/2"

    # ── Auth / JWT ────────────────────────────────────────────────────────────
    jwt_secret_key: str = "CHANGE_THIS_SECRET_IN_PRODUCTION_USE_256_BIT_RANDOM"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 60
    jwt_refresh_token_expire_days: int = 7

    # ── Encryption ────────────────────────────────────────────────────────────
    aes_encryption_key: str = "0" * 64   # 32-byte hex — override in production

    # ── LLM ──────────────────────────────────────────────────────────────────
    gemini_api_key: str = ""
    llm_provider: str = "gemini"

    # ── GeoIP (MaxMind GeoLite2) ──────────────────────────────────────────────
    geoip_db_path: str = "data/GeoLite2-City.mmdb"

    # ── Fusion weights (admin-editable via DB; these are compile-time defaults) ─
    weight_document: float = 0.30
    weight_biometric: float = 0.25
    weight_device: float = 0.20
    weight_behavioural: float = 0.10
    weight_identity_graph: float = 0.15

    # ── Decision thresholds ───────────────────────────────────────────────────
    threshold_approve: float = 75.0
    threshold_step_up: float = 55.0
    threshold_manual_review: float = 35.0

    # ── Fraud ring detection ──────────────────────────────────────────────────
    ring_min_size: int = 3

    # ── CORS ─────────────────────────────────────────────────────────────────
    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:3000"]

    # ── Webhook ──────────────────────────────────────────────────────────────
    webhook_timeout_seconds: int = 10
    webhook_max_retries: int = 3

    @field_validator("aes_encryption_key")
    @classmethod
    def _pad_key(cls, v: str) -> str:
        clean = v.replace(" ", "")
        return clean.ljust(64, "0")[:64]


settings = Settings()

# Legacy aliases used in older modules
GEMINI_API_KEY = settings.gemini_api_key
WEIGHTS = {
    "document": settings.weight_document,
    "biometric": settings.weight_biometric,
    "device": settings.weight_device,
    "behavioural": settings.weight_behavioural,
    "identity_graph": settings.weight_identity_graph,
}
CORS_ORIGINS = settings.cors_origins
