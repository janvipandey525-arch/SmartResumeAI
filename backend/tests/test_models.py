"""
ORM model tests: create, relate, persist JSON, cascade, unique constraints.

Identity is a UUID (mirrors auth.users.id) — set explicitly, not generated here.
Uses an isolated in-memory SQLite DB so it never touches a real database.
"""
import uuid

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.db.models import AtsReport, Profile, Resume


def _session():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def _profile(username="aditya", email="aditya@example.com", full_name="Aditya Ajay Singh"):
    return Profile(id=uuid.uuid4(), email=email, full_name=full_name, username=username)


def test_tables_created_and_relationships():
    db = _session()

    user = _profile()
    db.add(user)
    db.flush()

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

    got = db.scalar(select(Resume).where(Resume.id == resume.id))
    assert got.skills == ["python", "fastapi", "sql"]
    assert got.personal_info["name"] == "Aditya"

    assert user.resumes[0].title == "SDE Resume"
    assert report.user.username == "aditya"
    assert report.resume.id == resume.id
    assert user.ats_reports[0].score == 82


def test_cascade_delete_cleans_children():
    db = _session()
    user = _profile(username="x", email="x@x.com", full_name="X")
    db.add(user)
    db.flush()
    db.add(Resume(user_id=user.id, title="r"))
    db.add(AtsReport(user_id=user.id, score=50, grade="C"))
    db.commit()

    db.delete(user)
    db.commit()

    assert db.scalar(select(Resume)) is None
    assert db.scalar(select(AtsReport)) is None
    assert db.scalar(select(Profile)) is None


def test_unique_username_constraint():
    from sqlalchemy.exc import IntegrityError

    db = _session()
    db.add(_profile(username="dup", email="a@x.com"))
    db.commit()
    db.add(_profile(username="dup", email="b@x.com"))
    try:
        db.commit()
        assert False, "expected unique-username violation"
    except IntegrityError:
        db.rollback()
