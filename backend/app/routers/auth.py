"""
Profile endpoints.

Sign-up, login, logout and password handling all happen client-side against
Supabase Auth (GoTrue). What remains server-side is reading and updating the
user's app profile, keyed off the verified access token.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.base import get_db
from app.db.models import Profile
from app.deps import get_current_user
from app.schemas.user import ProfileUpdate, UserOut

router = APIRouter(tags=["auth"])


@router.get("/me", response_model=UserOut)
def me(current_user: Profile = Depends(get_current_user)) -> Profile:
    return current_user


@router.put("/me", response_model=UserOut)
def update_me(
    payload: ProfileUpdate,
    db: Session = Depends(get_db),
    current_user: Profile = Depends(get_current_user),
) -> Profile:
    data = payload.model_dump(exclude_unset=True)

    if "username" in data and data["username"] != current_user.username:
        taken = db.scalar(
            select(Profile).where(
                Profile.username == data["username"], Profile.id != current_user.id
            )
        )
        if taken is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="That username is already taken.",
            )

    for field, value in data.items():
        setattr(current_user, field, value)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="That username is already taken.",
        )
    db.refresh(current_user)
    return current_user
