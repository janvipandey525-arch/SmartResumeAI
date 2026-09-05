"""
Pydantic schemas for profile endpoints.

Auth (register / login / token issuance) is handled entirely by Supabase on the
client, so there are no password or token schemas here anymore — only the shapes
the API returns/accepts for the user's profile.
"""
import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserOut(BaseModel):
    # from_attributes lets FastAPI build this straight from a SQLAlchemy row.
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    full_name: str
    email: EmailStr
    username: str
    created_at: datetime


class ProfileUpdate(BaseModel):
    """Fields the user may change on their own profile."""
    full_name: Optional[str] = Field(default=None, min_length=1, max_length=120)
    username: Optional[str] = Field(
        default=None, min_length=3, max_length=80, pattern=r"^[A-Za-z0-9_.-]+$"
    )
