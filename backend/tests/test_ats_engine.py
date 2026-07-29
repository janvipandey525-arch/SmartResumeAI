"""Phase 5 verification: the deterministic ATS engine scores sensibly."""
from app.services import ats_engine

STRONG = """John Doe
Email: john@example.com | Phone: 999 | github.com/john
Summary: Backend engineer with 3 years building scalable APIs.
Education: B.Sc Computer Science, XYZ University, CGPA 8.9
Skills: Python, FastAPI, PostgreSQL, Docker, AWS, SQL
Experience:
- Built a payments API handling 50000 requests/day, cutting latency by 35%
- Reduced infrastructure cost by 20% by migrating to containerized services
- Led a team of 4 engineers and shipped 3 major releases
Projects:
- Developed an ATS analyzer scoring resumes across 5 dimensions
"""

WEAK = """jane
responsible for the website
worked on some tasks
did stuff for the company
"""


def test_strong_resume_beats_weak():
    strong = ats_engine.analyze(STRONG)
    weak = ats_engine.analyze(WEAK)
    assert strong["score"] > weak["score"]
    assert strong["score"] >= 60
    assert 0 <= weak["score"] <= 100


def test_output_shape_and_grade():
    r = ats_engine.analyze(STRONG)
    assert set(r["breakdown"]) == {
        "keywords", "sections", "action_verbs", "impact", "readability"
    }
    assert r["grade"] in {"A", "B", "C", "D", "F"}
    assert r["grade"] == ats_engine.score_to_grade(r["score"])


def test_job_description_keyword_matching():
    jd = "Looking for a Python FastAPI PostgreSQL Docker Kubernetes engineer"
    r = ats_engine.analyze(STRONG, jd)
    # Resume has python/fastapi/postgresql/docker but not kubernetes.
    assert "kubernetes" in r["missing_keywords"]
    assert "python" in r["matched_keywords"]
    assert r["breakdown"]["keywords"] > 0


def test_quantified_impact_rewards_numbers():
    with_numbers = ats_engine.analyze(
        "Increased revenue by 40% and cut costs by 25% over 12 months"
    )
    without = ats_engine.analyze(
        "Increased revenue and cut costs over the year significantly"
    )
    assert with_numbers["breakdown"]["impact"] > without["breakdown"]["impact"]


def test_resume_to_text_flattens_model_like_dict():
    text = ats_engine.resume_to_text(
        {
            "personal_info": {"name": "Aditya", "email": "a@x.com"},
            "skills": ["python", "sql"],
            "experience": "Built APIs",
            "summary": "Engineer",
        }
    )
    assert "Aditya" in text and "python" in text and "Built APIs" in text
