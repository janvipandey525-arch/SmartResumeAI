"""
SmartResumeAI — FastAPI application entrypoint.

One app does two jobs:
  1. Serves the JSON API under /api/...  (with interactive docs at /docs)
  2. Serves the static frontend (HTML/CSS/JS) at /

Because the frontend and API share an origin, there is no CORS problem in
production. CORS is only enabled for local dev servers (see settings.CORS_ORIGINS).
"""
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.core.config import settings
from app.core.ratelimit import limiter
from app.db.base import init_db
from app.routers import ats, auth, health, resumes

# Resolve the frontend directory: repo_root/frontend by default, overridable in Docker.
FRONTEND_DIR = Path(
    os.getenv("FRONTEND_DIR", Path(__file__).resolve().parents[2] / "frontend")
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: ensure tables exist. Safe no-op until models are defined.
    init_db()
    yield
    # Shutdown: nothing to clean up yet.


app = FastAPI(
    title=settings.APP_NAME,
    version="0.1.0",
    description="AI-powered resume builder + ATS analyzer (deterministic score + Gemini feedback).",
    lifespan=lifespan,
)

# --- Rate limiting (protects the AI endpoints from quota abuse) ---
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# --- CORS (local dev only; same-origin in prod needs none) ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- API routers (everything lives under /api) ---
app.include_router(health.router, prefix="/api")
app.include_router(auth.router, prefix="/api/auth")
app.include_router(resumes.router, prefix="/api/resumes")
app.include_router(ats.router, prefix="/api/ats")

# --- Static frontend (mounted last so /api and /docs win first) ---
if FRONTEND_DIR.is_dir():
    # html=True => "/" serves index.html and "/login" resolves login.html
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")
