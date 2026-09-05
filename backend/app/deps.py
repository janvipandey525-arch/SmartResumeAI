"""
Shared FastAPI dependencies: DB session + current authenticated profile.

Auth flow: the client sends a Supabase access token. We verify it (see
core/supabase_auth), then look up the matching row in `public.profiles`. A
database trigger (supabase/schema.sql) normally creates that row the moment the
user signs up; this dependency also creates it lazily as a fallback so the app
never 500s if the trigger is missing or the profile was deleted.
"""
import re
import uuid

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.supabase_auth import TokenClaims, TokenError, verify_token
from app.db.base import get_db
from app.db.models import Profile

_bearer = HTTPBearer(auto_error=True)

_credentials_exc = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Invalid or expired token",
    headers={"WWW-Authenticate": "Bearer"},
)


def _slugify_username(base: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9_.-]", "", (base or "").strip()) or "user"
    return slug[:72]


def _get_or_create_profile(db: Session, claims: TokenClaims) -> Profile:
    uid = uuid.UUID(claims.sub)
    profile = db.get(Profile, uid)
    if profile is not None:
        return profile

    # Fallback creation (trigger normally handles this at signup).
    desired = _slugify_username(
        claims.metadata.get("username")
        or (claims.email.split("@", 1)[0] if claims.email else "")
        or f"user{uid.hex[:8]}"
    )
    full_name = (claims.metadata.get("full_name") or "").strip()

    # Ensure username uniqueness with a short suffix on collision.
    username = desired
    for _ in range(5):
        exists = db.scalar(select(Profile).where(Profile.username == username))
        if exists is None:
            break
        username = f"{desired[:66]}_{uuid.uuid4().hex[:5]}"

    profile = Profile(id=uid, email=claims.email, full_name=full_name, username=username)
    db.add(profile)
    try:
        db.commit()
    except IntegrityError:
        # Race: the trigger (or a concurrent request) created it first.
        db.rollback()
        profile = db.get(Profile, uid)
        if profile is None:
            raise
    else:
        db.refresh(profile)
    return profile


def get_current_user(
    creds: HTTPAuthorizationCredentials = Depends(_bearer),
    db: Session = Depends(get_db),
) -> Profile:
    try:
        claims = verify_token(creds.credentials)
        return _get_or_create_profile(db, claims)
    except TokenError:
        raise _credentials_exc
    except ValueError:  # bad UUID in sub
        raise _credentials_exc
