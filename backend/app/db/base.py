"""
Database engine + session setup (SQLAlchemy 2.0) for Supabase Postgres.

Connection notes (production):
  * We connect over Supabase's *transaction pooler* (pgbouncer, port 6543).
    In transaction pooling mode server-side prepared statements are not safe,
    so we disable them on psycopg (`prepare_threshold=None`).
  * TLS is required by Supabase; psycopg negotiates it automatically, and the
    pooler host presents a valid cert (`sslmode=require` via the URL is fine too).
  * `pool_pre_ping` drops dead connections instead of erroring — important
    behind a pooler that may recycle server links.

The schema itself (tables, RLS, the auto-profile trigger) is owned by
`supabase/schema.sql`, applied once in the Supabase SQL Editor. The app does NOT
mutate schema at runtime — `init_db()` only verifies connectivity.
"""
from collections.abc import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import settings

_is_sqlite = settings.DATABASE_URL.startswith("sqlite")

if _is_sqlite:
    # Retained only for offline unit tests; production is always Postgres.
    _connect_args = {"check_same_thread": False}
else:
    # psycopg3 in a pgbouncer *transaction* pool: no prepared statements.
    _connect_args = {"prepare_threshold": None}

engine = create_engine(
    settings.DATABASE_URL,
    connect_args=_connect_args,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=5,
    pool_recycle=1800,  # recycle links every 30 min to stay ahead of pooler timeouts
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
    Verify the database is reachable at startup.

    Schema management lives in supabase/schema.sql (run once via the Supabase SQL
    Editor or the Management API). For local SQLite test runs we still create the
    app-owned tables so tests need zero setup.
    """
    if _is_sqlite:
        # A production deploy on SQLite is almost always a misconfiguration —
        # refuse to start rather than silently persist to an ephemeral file.
        if settings.is_production:
            raise RuntimeError(
                "DATABASE_URL points at SQLite but ENV=production. Set it to the "
                "Supabase Postgres (transaction pooler) connection string."
            )
        from app.db import models  # noqa: F401  (register tables on Base.metadata)
        Base.metadata.create_all(bind=engine)
        return

    # Production: just prove we can talk to Supabase. Never swallow the error —
    # a container that can't reach its DB should fail its healthcheck loudly.
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
