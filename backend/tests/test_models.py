"""
Phase 2 verification: the ORM models create, relate, persist JSON, and cascade.

Uses an isolated in-memory SQLite DB so it never touches the dev database.
"""
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.db.models import AtsReport, Resume, User


def _session():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def test_tables_created_and_relationships():
    db = _session()

    user = User(
        full_name="Aditya Ajay Singh",
        email="aditya@example.com",
        username="aditya",
        password_hash="not-a-real-hash",
    )
    db.add(user)
    db.flush()  # assigns user.id

    resume = Resume(
        user_id=user.id,
        title="SDE Resume",
        personal_info={"name": "Aditya", "phone": "999", "email": "a@x.com"},
        education=[{"school": "XYZ", "year": 2026}],
        skills=["python", "fastapi", "sql"],
        experience="Built stuff",
        template_id="modern",
    )
    db.add(resume)
    db.flush()

    report = AtsReport(
        user_id=user.id,
        resume_id=resume.id,
        job_description="python backend engineer",
        score=82,
        grade="B",
        breakdown={"keywords": 30, "sections": 20, "verbs": 15, "impact": 10, "readability": 7},
        matched_keywords=["python", "sql"],
        missing_keywords=["docker"],
        ai_feedback="",
    )
    db.add(report)
    db.commit()

    # JSON columns round-trip as native Python types.
    got = db.scalar(select(Resume).where(Resume.id == resume.id))
    assert got.skills == ["python", "fastapi", "sql"]
    assert got.personal_info["name"] == "Aditya"

    # Relationships navigate both directions.
    assert user.resumes[0].title == "SDE Resume"
    assert report.user.username == "aditya"
    assert report.resume.id == resume.id
    assert user.ats_reports[0].score == 82


def test_cascade_delete_cleans_children():
    db = _session()
    user = User(full_name="X", email="x@x.com", username="x", password_hash="h")
    db.add(user)
    db.flush()
    db.add(Resume(user_id=user.id, title="r"))
    db.add(AtsReport(user_id=user.id, score=50, grade="C"))
    db.commit()

    db.delete(user)  # ORM cascade removes owned resumes + reports
    db.commit()

    assert db.scalar(select(Resume)) is None
    assert db.scalar(select(AtsReport)) is None
    assert db.scalar(select(User)) is None


def test_unique_constraints():
    from sqlalchemy.exc import IntegrityError

    db = _session()
    db.add(User(full_name="A", email="dup@x.com", username="a", password_hash="h"))
    db.commit()
    db.add(User(full_name="B", email="dup@x.com", username="b", password_hash="h"))
    try:
        db.commit()
        assert False, "expected unique-email violation"
    except IntegrityError:
        db.rollback()
