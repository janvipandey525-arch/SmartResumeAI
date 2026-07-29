"""Pydantic schemas for auth/user endpoints (request + response shapes)."""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserCreate(BaseModel):
    full_name: str = Field(min_length=1, max_length=120)
    email: EmailStr
    username: str = Field(min_length=3, max_length=80, pattern=r"^[A-Za-z0-9_.-]+$")
    password: str = Field(min_length=6, max_length=128)


class UserLogin(BaseModel):
    # Accept either email or username in one field for a friendlier login form.
    identifier: str = Field(min_length=3, description="email or username")
    password: str


class UserOut(BaseModel):
    # from_attributes lets FastAPI build this straight from a SQLAlchemy row.
    model_config = ConfigDict(from_attributes=True)

    id: int
    full_name: str
    email: EmailStr
    username: str
    created_at: datetime


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut
