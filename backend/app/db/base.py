"""
Database engine + session setup (SQLAlchemy 2.0).

- Local dev: SQLite file (zero setup).
- Production: PostgreSQL via DATABASE_URL (Coolify Postgres resource).

`Base` is the declarative base every model inherits from. `get_db` is the
FastAPI dependency that hands a request a session and always closes it.
"""
from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import settings

# SQLite needs a special flag for use across FastAPI's threadpool; Postgres does not.
_connect_args = (
    {"check_same_thread": False}
    if settings.DATABASE_URL.startswith("sqlite")
    else {}
)

engine = create_engine(
    settings.DATABASE_URL,
    connect_args=_connect_args,
    pool_pre_ping=True,  # drops dead connections instead of erroring (matters on Coolify)
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency: yields a DB session, guarantees it's closed."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """
    Create tables that don't exist yet.

    For a student project this is simpler and more reliable than Alembic on a
    fresh deploy. Models are imported here so their tables register on Base
    before create_all() runs. (Swap to Alembic migrations later if schema
    versioning is needed for the viva.)
    """
    # Models are imported for their side effect of registering on Base.metadata.
    # (Populated from Milestone 1 onward — safe no-op while empty.)
    from app.db import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
