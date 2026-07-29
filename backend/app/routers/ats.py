"""
ATS analysis endpoints — the hybrid engine in action.

Every analyze call:
  1. resolves resume text (from a saved resume, raw text, or an uploaded file),
  2. runs the deterministic engine (always — free, fast, explainable),
  3. optionally layers Gemini feedback (if use_ai and a key is configured),
  4. persists an AtsReport tied to the user, and returns it.
"""
from typing import List, Optional, Tuple

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.core.ratelimit import limiter
from app.db.base import get_db
from app.db.models import AtsReport, Resume, User
from app.deps import get_current_user
from app.schemas.ats import AiResult, AnalyzeRequest, AtsReportOut, BulletRewriteRequest
from app.services import ai_service, ats_engine
from app.services.file_parse import extract_text

router = APIRouter(tags=["ats"])


def _resolve_resume_text(db: Session, user: User, resume_id, resume_text) -> Tuple[str, Optional[int]]:
    """Return (text, resume_id) from either a saved resume or provided raw text."""
    if resume_id:
        resume = db.get(Resume, resume_id)
        if resume is None or resume.user_id != user.id:
            raise HTTPException(status_code=404, detail="Resume not found.")
        return ats_engine.resume_to_text(resume), resume.id
    return resume_text or "", None


def _run_and_store(
    db: Session,
    user: User,
    text: str,
    job_description,
    resume_id,
    use_ai: bool,
) -> AtsReport:
    result = ats_engine.analyze(text, job_description)

    ai_feedback = ""
    if use_ai:
        ai = ai_service.generate_feedback(
            text, result["score"], result["breakdown"], job_description
        )
        # Store real feedback only; on disabled/error leave it empty (UI shows "off").
        if ai["status"] == "ok":
            ai_feedback = ai["text"]

    report = AtsReport(
        user_id=user.id,
        resume_id=resume_id,
        job_description=job_description or "",
        score=result["score"],
        grade=result["grade"],
        breakdown=result["breakdown"],
        matched_keywords=result["matched_keywords"],
        missing_keywords=result["missing_keywords"],
        ai_feedback=ai_feedback,
    )
    db.add(report)
    db.commit()
    db.refresh(report)
    return report


@router.post("/analyze", response_model=AtsReportOut)
@limiter.limit("30/minute")
def analyze(
    request: Request,
    payload: AnalyzeRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> AtsReport:
    text, resume_id = _resolve_resume_text(db, user, payload.resume_id, payload.resume_text)
    return _run_and_store(
        db, user, text, payload.job_description, resume_id, payload.use_ai
    )


@router.post("/analyze-file", response_model=AtsReportOut)
@limiter.limit("15/minute")
def analyze_file(
    request: Request,
    file: UploadFile = File(...),
    job_description: str = Form(default=""),
    use_ai: bool = Form(default=True),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> AtsReport:
    raw = file.file.read()
    try:
        text = extract_text(file.filename, raw)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not text.strip():
        raise HTTPException(status_code=400, detail="No readable text found in the file.")
    return _run_and_store(db, user, text, job_description, None, use_ai)


@router.post("/rewrite-bullet", response_model=AiResult)
@limiter.limit("20/minute")
def rewrite_bullet(
    request: Request,
    payload: BulletRewriteRequest,
    user: User = Depends(get_current_user),
) -> AiResult:
    return AiResult(**ai_service.rewrite_bullet(payload.bullet))


@router.get("/reports", response_model=list[AtsReportOut])
def list_reports(
    db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> List[AtsReport]:
    return list(
        db.scalars(
            select(AtsReport)
            .where(AtsReport.user_id == user.id)
            .order_by(desc(AtsReport.created_at))
        )
    )
