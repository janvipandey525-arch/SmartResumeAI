"""
Vercel serverless entrypoint for SmartResumeAI.

Vercel ignores the Dockerfile and runs Python files under `api/` as functions.
We simply re-export the existing FastAPI ASGI app so *nothing* about the app's
behaviour changes — the same instance that runs under uvicorn on Coolify also
handles requests here. All routing (API under /api, static frontend with clean
URLs via StaticFiles(html=True)) is preserved because every request is routed
to this function (see vercel.json).
"""
import sys
from pathlib import Path

# The app package lives in backend/; make it importable.
BACKEND_DIR = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND_DIR))

# The frontend is bundled alongside the function (includeFiles in vercel.json).
# Point the app at it explicitly so path resolution is deterministic in the
# lambda filesystem regardless of cwd.
FRONTEND_DIR = Path(__file__).resolve().parents[1] / "frontend"
import os
os.environ.setdefault("FRONTEND_DIR", str(FRONTEND_DIR))

from app.main import app  # noqa: E402  (re-exported for @vercel/python ASGI)
