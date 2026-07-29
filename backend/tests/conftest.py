"""
Shared test fixtures.

Every test gets a fresh in-memory SQLite database (isolated, fast) by overriding
the app's get_db dependency. This never touches the real dev database.
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base, get_db
from app.main import app


@pytest.fixture
def client():
    # StaticPool keeps one shared in-memory DB across the connection pool so the
    # schema created here is visible to the request handlers.
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    def _override_get_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def register(client, **over):
    body = {
        "full_name": "Test User",
        "email": "test@example.com",
        "username": "testuser",
        "password": "secret123",
    }
    body.update(over)
    return client.post("/api/auth/register", json=body)


def auth_header(client, **over):
    """Register a user and return an Authorization header with their JWT."""
    r = register(client, **over)
    token = r.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
