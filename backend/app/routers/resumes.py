"""
Resume CRUD + dashboard stats. Every endpoint is scoped to the logged-in user,
so one user can never read or modify another user's resumes (per-user isolation).
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.db.base import get_db
from app.db.models import AtsReport, Resume, User
from app.deps import get_current_user
from app.schemas.resume import (
    DashboardStats,
    ResumeCreate,
    ResumeOut,
    ResumeUpdate,
)

router = APIRouter(tags=["resumes"])


def _owned_or_404(db: Session, resume_id: int, user: User) -> Resume:
    resume = db.get(Resume, resume_id)
    # Treat "not yours" the same as "not found" — don't reveal other users' ids.
    if resume is None or resume.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resume not found.")
    return resume


@router.get("/stats", response_model=DashboardStats)
def stats(
    db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> DashboardStats:
    resumes_created = db.scalar(
        select(func.count()).select_from(Resume).where(Resume.user_id == user.id)
    )
    reports_run = db.scalar(
        select(func.count()).select_from(AtsReport).where(AtsReport.user_id == user.id)
    )
    latest = db.scalar(
        select(AtsReport)
        .where(AtsReport.user_id == user.id)
        .order_by(desc(AtsReport.created_at))
        .limit(1)
    )
    return DashboardStats(
        resumes_created=resumes_created or 0,
        reports_run=reports_run or 0,
        latest_score=latest.score if latest else None,
        latest_grade=latest.grade if latest else None,
    )


@router.get("", response_model=list[ResumeOut])
def list_resumes(
    db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> list[Resume]:
    return list(
        db.scalars(
            select(Resume)
            .where(Resume.user_id == user.id)
            .order_by(desc(Resume.updated_at))
        )
    )


@router.post("", response_model=ResumeOut, status_code=status.HTTP_201_CREATED)
def create_resume(
    payload: ResumeCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Resume:
    resume = Resume(user_id=user.id, **payload.model_dump())
    db.add(resume)
    db.commit()
    db.refresh(resume)
    return resume


@router.get("/{resume_id}", response_model=ResumeOut)
def get_resume(
    resume_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Resume:
    return _owned_or_404(db, resume_id, user)


@router.put("/{resume_id}", response_model=ResumeOut)
def update_resume(
    resume_id: int,
    payload: ResumeUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Resume:
    resume = _owned_or_404(db, resume_id, user)
    # exclude_unset => only overwrite fields the client actually sent.
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(resume, field, value)
    db.commit()
    db.refresh(resume)
    return resume


@router.delete("/{resume_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_resume(
    resume_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> None:
    resume = _owned_or_404(db, resume_id, user)
    db.delete(resume)
    db.commit()
