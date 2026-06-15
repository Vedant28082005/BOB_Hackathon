"""TrustLayer Backend — production FastAPI application."""
import structlog
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from prometheus_fastapi_instrumentator import Instrumentator

from config import settings
from database import init_db
from graph.neo4j_client import init_schema, close_driver
from storage.redis_client import get_redis

log = structlog.get_logger(__name__)


def _assert_secure_config() -> None:
    """Refuse to start in production with insecure default secrets."""
    if settings.environment != "production":
        return
    problems = []
    if settings.jwt_secret_key == "CHANGE_THIS_SECRET_IN_PRODUCTION_USE_256_BIT_RANDOM":
        problems.append("JWT_SECRET_KEY is the built-in default")
    if set(settings.aes_encryption_key) == {"0"}:
        problems.append("AES encryption key is all zeros (set AES_KEY_HEX)")
    if settings.debug:
        problems.append("DEBUG must be false in production")
    if problems:
        raise RuntimeError(
            "Insecure production configuration: " + "; ".join(problems)
        )


@asynccontextmanager
async def lifespan(app: FastAPI):
    _assert_secure_config()
    log.info("trustlayer_backend_starting", version=settings.app_version, env=settings.environment)
    await init_db()
    await init_schema()
    await get_redis()   # warm the connection pool
    log.info("trustlayer_backend_ready")
    yield
    await close_driver()
    log.info("trustlayer_backend_shutdown")


app = FastAPI(
    title="TrustLayer Identity Trust Framework",
    version=settings.app_version,
    description="Privacy-first KYC risk-decisioning API",
    lifespan=lifespan,
    docs_url="/docs" if settings.debug else None,
    redoc_url=None,
)

# ── Middleware ────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Prometheus ────────────────────────────────────────────────────────────────
Instrumentator(
    should_group_status_codes=True,
    excluded_handlers=["/health", "/metrics"],
).instrument(app).expose(app, endpoint="/metrics", include_in_schema=False)

# ── Routers ───────────────────────────────────────────────────────────────────
from routers import assessment, audit, graph, metrics, auth, admin, channel  # noqa: E402

app.include_router(auth.router,       prefix="/v1/auth",        tags=["auth"])
app.include_router(assessment.router, prefix="/v1/assessments", tags=["assessment"])
app.include_router(audit.router,      prefix="/v1/audit",       tags=["audit"])
app.include_router(graph.router,      prefix="/v1/graph",       tags=["graph"])
app.include_router(metrics.router,    prefix="/v1/metrics",     tags=["metrics"])
app.include_router(admin.router,      prefix="/v1/admin",       tags=["admin"])
app.include_router(channel.router,    prefix="/v1/channel",     tags=["channel"])


# ── Global error handler ──────────────────────────────────────────────────────
@app.exception_handler(Exception)
async def _unhandled(request: Request, exc: Exception):
    log.error("unhandled_exception", path=request.url.path, error=str(exc))
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal server error", "type": type(exc).__name__},
    )


@app.get("/health", tags=["ops"])
async def health():
    return {"status": "ok", "version": settings.app_version, "env": settings.environment}


@app.get("/ready", tags=["ops"])
async def readiness():
    from database import engine
    from sqlalchemy import text
    try:
        async with engine.begin() as conn:
            await conn.execute(text("SELECT 1"))
        return {"status": "ready"}
    except Exception as e:
        return JSONResponse({"status": "not_ready", "detail": str(e)}, status_code=503)
