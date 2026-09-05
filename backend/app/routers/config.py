"""
Public runtime config for the frontend.

The browser needs the Supabase project URL and the *anon* (public) key to run the
GoTrue client. These are not secrets — the anon key is designed to be shipped to
browsers and is gated by Row Level Security. Serving them from an endpoint (rather
than baking them into the repo) keeps all configuration in Coolify's env panel.
"""
from fastapi import APIRouter

from app.core.config import settings

router = APIRouter(tags=["config"])


@router.get("/config")
def public_config() -> dict:
    return {
        "supabaseUrl": settings.SUPABASE_URL,
        "supabaseAnonKey": settings.SUPABASE_ANON_KEY,
        "aiEnabled": bool(settings.GEMINI_API_KEY),
        "env": settings.ENV,
    }
