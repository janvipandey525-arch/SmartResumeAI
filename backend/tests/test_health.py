"""Phase 1 smoke tests: the app boots and the health/status endpoints work."""
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_ok():
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["app"] == "SmartResumeAI"


def test_status_reports_ai_flag():
    r = client.get("/api/status")
    assert r.status_code == 200
    body = r.json()
    # No key configured in test env => AI disabled.
    assert body["ai_enabled"] is False


def test_frontend_index_served():
    r = client.get("/")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]


def test_openapi_docs_available():
    assert client.get("/openapi.json").status_code == 200
