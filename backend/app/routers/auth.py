"""Auth endpoints: register, login (JWT), and 'who am I'."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.security import create_access_token, hash_password, verify_password
from app.db.base import get_db
from app.db.models import User
from app.deps import get_current_user
from app.schemas.user import Token, UserCreate, UserLogin, UserOut

router = APIRouter(tags=["auth"])


@router.post("/register", response_model=Token, status_code=status.HTTP_201_CREATED)
def register(payload: UserCreate, db: Session = Depends(get_db)) -> Token:
    # Reject duplicates up front with a clear message (case-insensitive email).
    exists = db.scalar(
        select(User).where(
            or_(
                User.email == payload.email.lower(),
                User.username == payload.username,
            )
        )
    )
    if exists:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with that email or username already exists.",
        )

    user = User(
        full_name=payload.full_name,
        email=payload.email.lower(),
        username=payload.username,
        password_hash=hash_password(payload.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_access_token(subject=user.id)
    return Token(access_token=token, user=UserOut.model_validate(user))


@router.post("/login", response_model=Token)
def login(payload: UserLogin, db: Session = Depends(get_db)) -> Token:
    ident = payload.identifier.strip()
    user = db.scalar(
        select(User).where(
            or_(User.email == ident.lower(), User.username == ident)
        )
    )
    # Same error whether the user is missing or the password is wrong — don't
    # leak which accounts exist (avoids username enumeration).
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials.",
        )

    token = create_access_token(subject=user.id)
    return Token(access_token=token, user=UserOut.model_validate(user))


@router.get("/me", response_model=UserOut)
def me(current_user: User = Depends(get_current_user)) -> UserOut:
    return UserOut.model_validate(current_user)
