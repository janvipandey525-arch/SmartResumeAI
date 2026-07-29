"""Shared FastAPI dependencies: DB session + current authenticated user."""
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.security import decode_access_token
from app.db.base import get_db
from app.db.models import User

# HTTPBearer pulls the token out of the "Authorization: Bearer <token>" header
# and shows a lock icon in Swagger so you can authorize and try endpoints live.
_bearer = HTTPBearer(auto_error=True)

_credentials_exc = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Invalid or expired token",
    headers={"WWW-Authenticate": "Bearer"},
)


def get_current_user(
    creds: HTTPAuthorizationCredentials = Depends(_bearer),
    db: Session = Depends(get_db),
) -> User:
    subject = decode_access_token(creds.credentials)
    if subject is None:
        raise _credentials_exc
    try:
        user_id = int(subject)
    except (TypeError, ValueError):
        raise _credentials_exc

    user = db.get(User, user_id)
    if user is None:
        raise _credentials_exc
    return user
