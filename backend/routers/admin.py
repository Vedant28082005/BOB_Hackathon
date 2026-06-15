"""Admin router — threshold/weight config, user management (admin role only)."""
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from security.auth import require_role, CurrentUser
from config import settings

router = APIRouter()

# In-memory config cache (production: load from DB, invalidate on change)
_runtime_config = {
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


@router.get("/config")
async def get_config(user: CurrentUser = Depends(require_role("admin"))):
    return _runtime_config


class ConfigUpdate(BaseModel):
    weights: dict | None = None
    thresholds: dict | None = None


@router.put("/config")
async def update_config(update: ConfigUpdate,
                        user: CurrentUser = Depends(require_role("admin"))):
    if update.weights:
        total = sum(update.weights.values())
        if abs(total - 1.0) > 0.01:
            from fastapi import HTTPException
            raise HTTPException(400, f"Weights must sum to 1.0 (got {total:.3f})")
        _runtime_config["weights"].update(update.weights)
    if update.thresholds:
        _runtime_config["thresholds"].update(update.thresholds)
    return {"status": "updated", "config": _runtime_config}
