"""Health + status endpoints (used by Coolify healthchecks and the frontend)."""
from fastapi import APIRouter

from app.core.config import settings

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict:
    """Liveness probe. Coolify hits this to know the container is up."""
    return {"status": "ok", "app": settings.APP_NAME, "env": settings.ENV}


@router.get("/status")
def status() -> dict:
    """
    Feature-availability snapshot for the frontend.

    `ai_enabled` reflects whether a Gemini key is configured — the UI uses this to
    show AI feedback as available vs. "off", without ever seeing the key itself.
    """
    return {
        "app": settings.APP_NAME,
        "env": settings.ENV,
        "ai_enabled": bool(settings.GEMINI_API_KEY),
        "ai_model": settings.GEMINI_MODEL if settings.GEMINI_API_KEY else None,
    }
