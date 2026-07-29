"""Pydantic schemas for the ATS analyze + AI endpoints."""
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


class AnalyzeRequest(BaseModel):
    # Provide exactly one source of resume content: a saved resume id OR raw text.
    resume_id: Optional[int] = None
    resume_text: Optional[str] = None
    job_description: Optional[str] = None
    use_ai: bool = True  # run Gemini feedback too (if a key is configured)

    @model_validator(mode="after")
    def _one_source(self):
        if not self.resume_id and not (self.resume_text and self.resume_text.strip()):
            raise ValueError("Provide either resume_id or resume_text.")
        return self


class BulletRewriteRequest(BaseModel):
    bullet: str = Field(min_length=3, max_length=500)


class AiResult(BaseModel):
    status: str  # ok | disabled | error
    text: str


class AtsReportOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    resume_id: Optional[int]
    job_description: Optional[str]
    score: int
    grade: str
    breakdown: dict
    matched_keywords: List[str]
    missing_keywords: List[str]
    ai_feedback: Optional[str]
    created_at: datetime
