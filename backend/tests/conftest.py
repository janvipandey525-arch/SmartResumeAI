"""
Shared test fixtures.

Auth is now owned by Supabase, so tests don't call register/login. Instead we
override `get_current_user` with a fake that derives a stable identity from the
bearer token (format: "test:<username>:<email>"). Because the override still
depends on HTTPBearer, requests with no Authorization header correctly get a 403
before the fake runs — so the "requires auth" tests keep working. Profiles are
auto-created per identity, which also gives us multi-user isolation tests.

Every test gets a fresh in-memory SQLite database (isolated, fast) via a get_db
override. This never touches a real database.
"""
import uuid

import pytest
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base, get_db
from app.db.models import Profile
from app.deps import get_current_user
from app.main import app

_NS = uuid.NAMESPACE_DNS
_bearer = HTTPBearer(auto_error=True)


def _make_engine():
    # StaticPool keeps one shared in-memory DB across the connection pool so the
    # schema created here is visible to the request handlers.
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return engine


def _db_override(TestingSession):
    def _override_get_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()
    return _override_get_db


def _fake_current_user(
    creds: HTTPAuthorizationCredentials = Depends(_bearer),
    db: Session = Depends(get_db),
) -> Profile:
    """Turn a 'test:<username>:<email>' token into a real (auto-created) Profile."""
    token = creds.credentials
    if not token.startswith("test:"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="bad test token")
    _, username, email = (token.split(":", 2) + ["", ""])[:3]
    username = username or "testuser"
    email = email or "test@example.com"
    uid = uuid.uuid5(_NS, username)

    profile = db.get(Profile, uid)
    if profile is None:
        profile = Profile(id=uid, email=email, full_name="Test User", username=username)
        db.add(profile)
        db.commit()
        db.refresh(profile)
    return profile


@pytest.fixture
def client():
    """Authenticated client: get_current_user is faked from the bearer token."""
    engine = _make_engine()
    TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    app.dependency_overrides[get_db] = _db_override(TestingSession)
    app.dependency_overrides[get_current_user] = _fake_current_user
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def raw_client():
    """Client WITHOUT the auth override — exercises real token verification."""
    engine = _make_engine()
    TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    app.dependency_overrides[get_db] = _db_override(TestingSession)
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def auth_header(client=None, username="testuser", email="test@example.com", **over):
    """Return an Authorization header the fake resolver understands."""
    username = over.get("username", username)
    email = over.get("email", email)
    return {"Authorization": f"Bearer test:{username}:{email}"}
