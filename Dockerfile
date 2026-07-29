# SmartResumeAI — single container: FastAPI serves both the API and the frontend.
# Build context is the repo root so we can copy both backend/ and frontend/.
FROM python:3.12-slim

# Keep Python lean and unbuffered (logs show up immediately in Coolify).
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install dependencies first (layer cached unless requirements change).
COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# App code + the static frontend it serves.
COPY backend/ ./backend/
COPY frontend/ ./frontend/

# The app looks here for static files (overrides the path-relative default).
ENV FRONTEND_DIR=/app/frontend

WORKDIR /app/backend
EXPOSE 8000

# Coolify sets $PORT; default to 8000 for local `docker run`.
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
