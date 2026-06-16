"""Admin router — threshold/weight config, user management (admin role only)."""
import json

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from security.auth import require_role, CurrentUser
from config import settings
from graph.neo4j_client import clear_graph
from storage.redis_client import get_redis

router = APIRouter()

# Config is persisted in Redis so it is shared across the API and the Celery
# worker processes (separate memory spaces) and survives restarts.
RUNTIME_CONFIG_KEY = "runtime_config"


def _default_config() -> dict:
    return {
        "weights": {
            "document":       settings.weight_document,
            "biometric":      settings.weight_biometric,
            "device":         settings.weight_device,
            "behavioural":    settings.weight_behavioural,
            "identity_graph": settings.weight_identity_graph,
        },
        "thresholds": {
            "approve":       settings.threshold_approve,
            "step_up":       settings.threshold_step_up,
            "manual_review": settings.threshold_manual_review,
        },
    }


async def _load_config() -> dict:
    r = await get_redis()
    raw = await r.get(RUNTIME_CONFIG_KEY)
    if raw:
        try:
            return json.loads(raw)
        except (ValueError, TypeError):
            pass
    return _default_config()


@router.get("/config")
async def get_config(user: CurrentUser = Depends(require_role("admin"))):
    return await _load_config()


class ConfigUpdate(BaseModel):
    weights: dict | None = None
    thresholds: dict | None = None


@router.put("/config")
async def update_config(update: ConfigUpdate,
                        user: CurrentUser = Depends(require_role("admin"))):
    cfg = await _load_config()
    if update.weights:
        total = sum(update.weights.values())
        if abs(total - 1.0) > 0.01:
            raise HTTPException(400, f"Weights must sum to 1.0 (got {total:.3f})")
        cfg["weights"].update(update.weights)
    if update.thresholds:
        cfg["thresholds"].update(update.thresholds)
    r = await get_redis()
    await r.set(RUNTIME_CONFIG_KEY, json.dumps(cfg))
    return {"status": "updated", "config": cfg}


@router.post("/graph/reset")
async def reset_identity_graph(
    user: CurrentUser = Depends(require_role("admin", "analyst")),
):
    """Wipe the identity graph — demo control so re-submitted test identities
    are not flagged as duplicates/ring members of earlier runs."""
    removed = await clear_graph()
    return {"status": "ok", "nodes_removed": removed}
