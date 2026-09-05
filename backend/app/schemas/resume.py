"""Pydantic schemas for resume CRUD + dashboard stats."""
import uuid
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class ResumeBase(BaseModel):
    title: str = Field(default="My Resume", max_length=160)
    personal_info: dict = Field(default_factory=dict)  # name, email, phone, address
    education: List[dict] = Field(default_factory=list)
    skills: List[str] = Field(default_factory=list)
    projects: str = ""
    experience: str = ""
    certifications: str = ""
    summary: str = ""
    template_id: str = "modern"


class ResumeCreate(ResumeBase):
    pass


class ResumeUpdate(BaseModel):
    # All optional: PATCH-like partial update; only provided fields change.
    title: Optional[str] = Field(default=None, max_length=160)
    personal_info: Optional[dict] = None
    education: Optional[List[dict]] = None
    skills: Optional[List[str]] = None
    projects: Optional[str] = None
    experience: Optional[str] = None
    certifications: Optional[str] = None
    summary: Optional[str] = None
    template_id: Optional[str] = None


class ResumeOut(ResumeBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class DashboardStats(BaseModel):
    resumes_created: int
    reports_run: int
    latest_score: Optional[int] = None
    latest_grade: Optional[str] = None
