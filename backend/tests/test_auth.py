"""
Profile endpoint tests (auth itself is Supabase's job now).

We verify:
  * /api/auth/me requires a bearer token (403 when missing),
  * a garbage token is rejected by the real verifier (401),
  * /me returns the resolved profile,
  * /me (PUT) updates full_name/username and enforces username uniqueness.
"""
from tests.conftest import auth_header


def test_me_requires_bearer(client):
    # No Authorization header -> HTTPBearer returns 403 before anything else.
    assert client.get("/api/auth/me").status_code == 403


def test_me_rejects_garbage_token_real_path(raw_client):
    # No SUPABASE_JWT_SECRET / URL configured in tests -> verification fails -> 401.
    r = raw_client.get("/api/auth/me", headers={"Authorization": "Bearer garbage"})
    assert r.status_code == 401


def test_me_returns_profile(client):
    r = client.get("/api/auth/me", headers=auth_header())
    assert r.status_code == 200
    body = r.json()
    assert body["username"] == "testuser"
    assert body["email"] == "test@example.com"
    assert "password" not in body and "password_hash" not in body


def test_update_profile(client):
    h = auth_header()
    r = client.put("/api/auth/me", json={"full_name": "New Name", "username": "newname"}, headers=h)
    assert r.status_code == 200
    assert r.json()["full_name"] == "New Name"
    assert r.json()["username"] == "newname"


def test_update_username_conflict(client):
    # Two users; second tries to take the first's username.
    client.get("/api/auth/me", headers=auth_header(username="alice", email="alice@x.com"))
    hb = auth_header(username="bob", email="bob@x.com")
    client.get("/api/auth/me", headers=hb)  # ensure bob exists

    r = client.put("/api/auth/me", json={"username": "alice"}, headers=hb)
    assert r.status_code == 409


def test_update_validates_username(client):
    r = client.put("/api/auth/me", json={"username": "no spaces!"}, headers=auth_header())
    assert r.status_code == 422
