"""Phase 3 verification: register, login, JWT-protected access."""
from tests.conftest import auth_header, register


def test_register_returns_token_and_user(client):
    r = register(client)
    assert r.status_code == 201
    body = r.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]
    assert body["user"]["email"] == "test@example.com"
    assert "password" not in body["user"]  # never leak the password/hash


def test_register_rejects_duplicate(client):
    register(client)
    r = register(client)  # same email/username
    assert r.status_code == 409


def test_register_validates_input(client):
    r = register(client, password="123")  # too short
    assert r.status_code == 422
    r = register(client, email="not-an-email")
    assert r.status_code == 422


def test_login_with_email_and_username(client):
    register(client)
    for ident in ("test@example.com", "testuser"):
        r = client.post("/api/auth/login", json={"identifier": ident, "password": "secret123"})
        assert r.status_code == 200, ident
        assert r.json()["access_token"]


def test_login_wrong_password_401(client):
    register(client)
    r = client.post("/api/auth/login", json={"identifier": "testuser", "password": "nope"})
    assert r.status_code == 401


def test_login_unknown_user_401_same_message(client):
    r = client.post("/api/auth/login", json={"identifier": "ghost", "password": "x"})
    assert r.status_code == 401
    assert r.json()["detail"] == "Invalid credentials."


def test_me_requires_valid_token(client):
    assert client.get("/api/auth/me").status_code == 403  # no bearer -> HTTPBearer 403
    assert client.get(
        "/api/auth/me", headers={"Authorization": "Bearer garbage"}
    ).status_code == 401


def test_me_returns_current_user(client):
    headers = auth_header(client)
    r = client.get("/api/auth/me", headers=headers)
    assert r.status_code == 200
    assert r.json()["username"] == "testuser"


def test_password_is_hashed_not_plaintext(client):
    # Prove the stored hash is bcrypt, not the raw password.
    from app.core.security import verify_password

    register(client)
    # Pull the row straight from the app's overridden DB session.
    from app.db.base import get_db

    gen = client.app.dependency_overrides[get_db]()
    db = next(gen)
    from app.db.models import User

    user = db.query(User).first()
    assert user.password_hash != "secret123"
    assert user.password_hash.startswith("$2")  # bcrypt marker
    assert verify_password("secret123", user.password_hash)
