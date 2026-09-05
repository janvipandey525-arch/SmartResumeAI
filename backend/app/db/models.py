"""
SQLAlchemy ORM models.

Identity lives in Supabase Auth (`auth.users`, UUID primary key). We mirror the
non-sensitive profile fields into `public.profiles` (same UUID as the auth user)
so the app can join name/username without touching the auth schema. Resumes and
ATS reports are owned by a profile.

  auth.users (Supabase) 1──1 Profile
  Profile 1──* Resume
  Profile 1──* AtsReport
  Resume  1──* AtsReport   (nullable when the analysis came from an upload)

Portability: `Uuid` maps to native uuid on Postgres and CHAR on SQLite (test
runs); `JSON` maps to JSONB on Postgres and TEXT-backed JSON on SQLite.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Profile(Base):
    __tablename__ = "profiles"

    # Same value as auth.users.id — set from the verified JWT `sub`, never generated here.
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    email: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    full_name: Mapped[str] = mapped_column(String(120), default="")
    username: Mapped[str] = mapped_column(String(80), unique=True, index=True, nullable=False)
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
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("profiles.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(160), default="My Resume")

    personal_info: Mapped[Optional[dict]] = mapped_column(JSON, default=dict)
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

    user: Mapped["Profile"] = relationship(back_populates="resumes")
    ats_reports: Mapped[list["AtsReport"]] = relationship(
        back_populates="resume", cascade="all, delete-orphan"
    )


class AtsReport(Base):
    __tablename__ = "ats_reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("profiles.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    resume_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("resumes.id", ondelete="SET NULL"), nullable=True
    )

    job_description: Mapped[Optional[str]] = mapped_column(Text, default="")
    score: Mapped[int] = mapped_column(Integer, default=0)      # 0..100
    grade: Mapped[str] = mapped_column(String(2), default="F")  # A..F

    breakdown: Mapped[Optional[dict]] = mapped_column(JSON, default=dict)
    matched_keywords: Mapped[Optional[list]] = mapped_column(JSON, default=list)
    missing_keywords: Mapped[Optional[list]] = mapped_column(JSON, default=list)

    # Path of the uploaded source file in Supabase Storage (null when analysis
    # came from a saved resume or raw pasted text).
    storage_path: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)

    ai_feedback: Mapped[Optional[str]] = mapped_column(Text, default="")

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    user: Mapped["Profile"] = relationship(back_populates="ats_reports")
    resume: Mapped["Resume"] = relationship(back_populates="ats_reports")
