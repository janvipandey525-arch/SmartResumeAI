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
    from app.core.config import settings

    r = client.get("/api/status")
    assert r.status_code == 200
    body = r.json()
    # ai_enabled must mirror whether a key is actually configured, whatever env.
    assert isinstance(body["ai_enabled"], bool)
    assert body["ai_enabled"] == bool(settings.GEMINI_API_KEY)


def test_health_db_reports_database_up():
    """The keepalive endpoint must actually reach the database, not just 200."""
    r = client.get("/api/health/db")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["database"] == "up"
    assert isinstance(body["latency_ms"], float)


def test_health_db_returns_503_when_database_unreachable():
    """A dead database must surface as 503 so cron/uptime monitors alert."""
    from sqlalchemy.exc import OperationalError

    from app.db.base import get_db

    def broken_db():
        class BrokenSession:
            def execute(self, *_a, **_kw):
                raise OperationalError("SELECT 1", {}, Exception("no connection"))

        yield BrokenSession()

    app.dependency_overrides[get_db] = broken_db
    try:
        r = client.get("/api/health/db")
        assert r.status_code == 503
        body = r.json()
        assert body["database"] == "down"
        # Never leak a connection string / credentials through a public route.
        assert body["error"] == "OperationalError"
        assert "no connection" not in str(body)
    finally:
        app.dependency_overrides.pop(get_db, None)


def test_frontend_index_served():
    r = client.get("/")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]


def test_openapi_docs_available():
    assert client.get("/openapi.json").status_code == 200
