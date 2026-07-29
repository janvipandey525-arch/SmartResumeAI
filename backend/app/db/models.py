"""
SQLAlchemy ORM models — the three real tables that replace the old
localStorage blobs (resumeai_account, resumeai_resume, resumeai_last_score).

Relationships:
  User 1──* Resume       (a user owns many resumes)
  User 1──* AtsReport    (a user has many analyses)
  Resume 1──* AtsReport  (a report may reference a built resume, or be null
                          when the analysis came from an uploaded file)

Portability note: we use JSON columns for structured sub-objects (personal_info,
education, breakdown, keyword lists). SQLAlchemy's generic JSON type maps to
JSONB on Postgres and to TEXT-backed JSON on SQLite, so the same models run in
both local dev and production.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    full_name: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    username: Mapped[str] = mapped_column(String(80), unique=True, index=True, nullable=False)
    # bcrypt hash only — the raw password is never stored.
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    resumes: Mapped[list["Resume"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    ats_reports: Mapped[list["AtsReport"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class Resume(Base):
    __tablename__ = "resumes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    title: Mapped[str] = mapped_column(String(160), default="My Resume")

    # Structured content stored as JSON (portable across SQLite/Postgres).
    personal_info: Mapped[Optional[dict]] = mapped_column(JSON, default=dict)  # name, email, phone, address
    education: Mapped[Optional[list]] = mapped_column(JSON, default=list)
    skills: Mapped[Optional[list]] = mapped_column(JSON, default=list)
    projects: Mapped[Optional[str]] = mapped_column(Text, default="")
    experience: Mapped[Optional[str]] = mapped_column(Text, default="")
    certifications: Mapped[Optional[str]] = mapped_column(Text, default="")
    summary: Mapped[Optional[str]] = mapped_column(Text, default="")
    template_id: Mapped[str] = mapped_column(String(40), default="modern")

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )

    user: Mapped["User"] = relationship(back_populates="resumes")
    ats_reports: Mapped[list["AtsReport"]] = relationship(
        back_populates="resume", cascade="all, delete-orphan"
    )


class AtsReport(Base):
    __tablename__ = "ats_reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    # Nullable: the analysis may come from an uploaded file rather than a saved resume.
    resume_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("resumes.id", ondelete="SET NULL"), nullable=True
    )

    job_description: Mapped[Optional[str]] = mapped_column(Text, default="")
    score: Mapped[int] = mapped_column(Integer, default=0)      # 0..100
    grade: Mapped[str] = mapped_column(String(2), default="F")  # A..F

    # Per-dimension scores + keyword lists from the deterministic engine.
    breakdown: Mapped[Optional[dict]] = mapped_column(JSON, default=dict)
    matched_keywords: Mapped[Optional[list]] = mapped_column(JSON, default=list)
    missing_keywords: Mapped[Optional[list]] = mapped_column(JSON, default=list)

    # Natural-language advice from Gemini (Milestone 5). Empty when AI is off.
    ai_feedback: Mapped[Optional[str]] = mapped_column(Text, default="")

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    user: Mapped["User"] = relationship(back_populates="ats_reports")
    resume: Mapped["Resume"] = relationship(back_populates="ats_reports")
