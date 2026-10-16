"""Health + status endpoints (used by Coolify healthchecks and the frontend)."""
import time

from fastapi import APIRouter, Depends, Response
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.base import get_db

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict:
    """Liveness probe. Coolify hits this to know the container is up."""
    return {"status": "ok", "app": settings.APP_NAME, "env": settings.ENV}


@router.get("/health/db")
def health_db(response: Response, db: Session = Depends(get_db)) -> dict:
    """
    Readiness probe that actually talks to Supabase Postgres.

    This exists because `/health` answers without ever opening a connection, so
    polling it would keep the web app warm while Supabase still paused the
    database for inactivity. Free-tier projects pause after ~7 days with no
    activity, so the scheduled job in .github/workflows/keepalive.yml hits THIS
    route (not /health) to count as real database activity.

    Returns 503 on failure so a cron/uptime monitor treats it as a hard failure
    instead of a silent 200.
    """
    started = time.perf_counter()
    try:
        # A trivial read is enough to count as activity and prove the pooler,
        # TLS and credentials all still work end to end.
        db.execute(text("SELECT 1"))
        latency_ms = round((time.perf_counter() - started) * 1000, 1)
        return {
            "status": "ok",
            "database": "up",
            "latency_ms": latency_ms,
            "env": settings.ENV,
        }
    except Exception as exc:  # noqa: BLE001 - surface any driver/network error
        response.status_code = 503
        return {
            "status": "error",
            "database": "down",
            # Class name only: connection strings and credentials must never
            # leak through a public, unauthenticated endpoint.
            "error": type(exc).__name__,
            "env": settings.ENV,
        }


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
