"""
Phase 5+6 verification: the /api/ats endpoints.

AI is turned off (use_ai=False) so the suite stays fast and offline — the live
Gemini path is validated separately. These tests prove the deterministic path,
persistence, auth, and per-user isolation of reports.
"""
import io

from tests.conftest import auth_header

RESUME_TEXT = (
    "Aditya | aditya@example.com\n"
    "Skills: Python, FastAPI, PostgreSQL, Docker\n"
    "- Built an API handling 50000 requests/day, cutting latency by 35%\n"
    "- Led a team of 4 and shipped 3 releases\n"
)


def test_analyze_requires_auth(client):
    r = client.post("/api/ats/analyze", json={"resume_text": RESUME_TEXT, "use_ai": False})
    assert r.status_code == 403


def test_analyze_from_text_persists_report(client):
    h = auth_header(client)
    r = client.post(
        "/api/ats/analyze",
        json={"resume_text": RESUME_TEXT, "job_description": "python fastapi docker", "use_ai": False},
        headers=h,
    )
    assert r.status_code == 200
    body = r.json()
    assert 0 <= body["score"] <= 100
    assert body["grade"] in {"A", "B", "C", "D", "F"}
    assert "python" in body["matched_keywords"]
    assert body["ai_feedback"] == ""  # AI off

    # It was saved and shows up in stats + reports list.
    reports = client.get("/api/ats/reports", headers=h).json()
    assert len(reports) == 1
    stats = client.get("/api/resumes/stats", headers=h).json()
    assert stats["reports_run"] == 1
    assert stats["latest_score"] == body["score"]


def test_analyze_requires_a_source(client):
    h = auth_header(client)
    r = client.post("/api/ats/analyze", json={"use_ai": False}, headers=h)
    assert r.status_code == 422  # neither resume_id nor resume_text


def test_analyze_saved_resume(client):
    h = auth_header(client)
    rid = client.post(
        "/api/resumes",
        json={"title": "R", "skills": ["python", "sql"], "experience": "Built APIs, cut cost 20%"},
        headers=h,
    ).json()["id"]
    r = client.post("/api/ats/analyze", json={"resume_id": rid, "use_ai": False}, headers=h)
    assert r.status_code == 200
    assert r.json()["resume_id"] == rid


def test_analyze_foreign_resume_404(client):
    ha = auth_header(client, email="a@x.com", username="usera")
    hb = auth_header(client, email="b@x.com", username="userb")
    rid = client.post("/api/resumes", json={"title": "R"}, headers=ha).json()["id"]
    r = client.post("/api/ats/analyze", json={"resume_id": rid, "use_ai": False}, headers=hb)
    assert r.status_code == 404


def test_analyze_file_txt(client):
    h = auth_header(client)
    files = {"file": ("resume.txt", io.BytesIO(RESUME_TEXT.encode()), "text/plain")}
    r = client.post("/api/ats/analyze-file", files=files, data={"use_ai": "false"}, headers=h)
    assert r.status_code == 200
    assert r.json()["score"] >= 0


def test_analyze_file_rejects_unknown_type(client):
    h = auth_header(client)
    files = {"file": ("resume.exe", io.BytesIO(b"MZ..."), "application/octet-stream")}
    r = client.post("/api/ats/analyze-file", files=files, data={"use_ai": "false"}, headers=h)
    assert r.status_code == 400
