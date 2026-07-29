"""Phase 4 verification: resume CRUD, per-user isolation, dashboard stats."""
from tests.conftest import auth_header

SAMPLE = {
    "title": "Backend Engineer",
    "personal_info": {"name": "Aditya", "phone": "999", "email": "a@x.com"},
    "skills": ["python", "fastapi"],
    "experience": "Built APIs",
    "template_id": "modern",
}


def test_crud_requires_auth(client):
    assert client.get("/api/resumes").status_code == 403
    assert client.post("/api/resumes", json=SAMPLE).status_code == 403


def test_create_and_list(client):
    h = auth_header(client)
    r = client.post("/api/resumes", json=SAMPLE, headers=h)
    assert r.status_code == 201
    rid = r.json()["id"]
    assert r.json()["skills"] == ["python", "fastapi"]

    lst = client.get("/api/resumes", headers=h)
    assert lst.status_code == 200
    assert len(lst.json()) == 1
    assert lst.json()[0]["id"] == rid


def test_get_update_delete(client):
    h = auth_header(client)
    rid = client.post("/api/resumes", json=SAMPLE, headers=h).json()["id"]

    got = client.get(f"/api/resumes/{rid}", headers=h)
    assert got.status_code == 200

    # Partial update: only title changes, skills preserved.
    upd = client.put(f"/api/resumes/{rid}", json={"title": "Senior SDE"}, headers=h)
    assert upd.status_code == 200
    assert upd.json()["title"] == "Senior SDE"
    assert upd.json()["skills"] == ["python", "fastapi"]

    d = client.delete(f"/api/resumes/{rid}", headers=h)
    assert d.status_code == 204
    assert client.get(f"/api/resumes/{rid}", headers=h).status_code == 404


def test_per_user_isolation(client):
    # User A creates a resume; User B must not see or touch it.
    ha = auth_header(client, email="a@x.com", username="usera")
    hb = auth_header(client, email="b@x.com", username="userb")

    rid = client.post("/api/resumes", json=SAMPLE, headers=ha).json()["id"]

    assert client.get("/api/resumes", headers=hb).json() == []
    assert client.get(f"/api/resumes/{rid}", headers=hb).status_code == 404
    assert client.put(f"/api/resumes/{rid}", json={"title": "hax"}, headers=hb).status_code == 404
    assert client.delete(f"/api/resumes/{rid}", headers=hb).status_code == 404


def test_dashboard_stats(client):
    h = auth_header(client)
    empty = client.get("/api/resumes/stats", headers=h).json()
    assert empty == {
        "resumes_created": 0,
        "reports_run": 0,
        "latest_score": None,
        "latest_grade": None,
    }

    client.post("/api/resumes", json=SAMPLE, headers=h)
    client.post("/api/resumes", json=SAMPLE, headers=h)
    stats = client.get("/api/resumes/stats", headers=h).json()
    assert stats["resumes_created"] == 2
