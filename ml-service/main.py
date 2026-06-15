"""TrustLayer ML Inference Service — loads all GPU models once at startup."""
import structlog
from contextlib import asynccontextmanager
from fastapi import FastAPI
from prometheus_fastapi_instrumentator import Instrumentator

from config import settings
from api.routes import router

log = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("ml_service_starting", gpu=settings.use_gpu)
    # Pre-warm models on startup
    from models.ocr import _get_ocr_engine
    from models.face import _get_face_app
    from models.deepfake import _load_deepfake_model
    from pathlib import Path

    _get_ocr_engine(settings.ocr_lang, settings.ocr_use_angle, settings.use_gpu)
    _get_face_app(settings.insightface_model, settings.use_gpu)
    _load_deepfake_model(settings.models_dir / settings.deepfake_model, settings.use_gpu)
    log.info("ml_service_ready")
    yield
    log.info("ml_service_shutdown")


app = FastAPI(
    title="TrustLayer ML Service",
    version="2.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url=None,
)

app.include_router(router)
Instrumentator().instrument(app).expose(app, endpoint="/metrics")


@app.get("/health")
async def health():
    return {"status": "ok", "service": "ml-service"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host=settings.service_host, port=settings.service_port,
                reload=False, workers=1)  # single worker to share GPU model state
