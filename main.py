"""
Vercel entrypoint for SmartResumeAI.

Vercel detects FastAPI from requirements.txt and looks for a top-level `app`
in a root-level entrypoint (app.py / index.py / server.py / main.py / ...).
When it finds one it routes *every* request to it with the original path
intact — which is why this file exists at the repo root rather than under
api/. The legacy api/ + catch-all-rewrite approach handed the app the rewrite
*destination* path ("/api/index.py") instead of the request path, so every
route 404'd.

Nothing about the application changes here: this re-exports the same ASGI app
that uvicorn serves in the Docker/Coolify deployment.
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent

# The app package lives in backend/; make it importable.
sys.path.insert(0, str(ROOT / "backend"))

# Pin static file resolution to the bundle layout rather than the cwd.
os.environ.setdefault("FRONTEND_DIR", str(ROOT / "frontend"))

from app.main import app  # noqa: E402  (re-exported as the Vercel entrypoint)

__all__ = ["app"]
