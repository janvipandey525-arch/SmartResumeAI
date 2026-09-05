"""
Application configuration.

All settings load from environment variables (or a local .env file in dev) via
pydantic-settings. Nothing sensitive is ever hardcoded — on Coolify these values
come from the service's Environment Variables panel.

Supabase powers three things:
  * Auth  — GoTrue issues the JWTs the frontend sends; the backend verifies them
            (SUPABASE_JWT_SECRET for legacy HS256, or the JWKS endpoint for the
            newer asymmetric signing keys).
  * DB    — Postgres, reached over the transaction pooler via DATABASE_URL.
  * Storage — a private bucket for uploaded resume files, written server-side with
            the service_role key.
"""
from functools import lru_cache
from typing import List, Optional

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict
from typing_extensions import Annotated


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- App ---
    APP_NAME: str = "SmartResumeAI"
    ENV: str = "development"  # "development" | "production"

    # --- Database (Supabase Postgres) ---
    # Local dev / tests default to SQLite (zero setup). Production MUST set this to
    # the Supabase *transaction pooler* connection string (port 6543):
    #   postgresql+psycopg://postgres.<ref>:<PW>@aws-0-<region>.pooler.supabase.com:6543/postgres
    # The pooler runs pgbouncer in transaction mode, so server-side prepared
    # statements are disabled in db/base.py. A production start with a SQLite URL
    # fails fast (see db.base.init_db).
    DATABASE_URL: str = "sqlite:///./smartresume.db"

    # --- Supabase project ---
    SUPABASE_URL: str = ""                 # https://<ref>.supabase.co
    SUPABASE_ANON_KEY: str = ""            # public — safe to expose to the browser
    SUPABASE_SERVICE_ROLE_KEY: str = ""    # SECRET — server-only (Storage writes)

    # Token verification. Provide ONE of these:
    #   * SUPABASE_JWT_SECRET — legacy shared HS256 secret
    #     (Settings -> API -> JWT Settings -> JWT Secret), or
    #   * leave it blank and we verify via the project's JWKS endpoint
    #     (new asymmetric signing keys).
    SUPABASE_JWT_SECRET: str = ""
    SUPABASE_JWT_AUD: str = "authenticated"

    # --- Storage ---
    SUPABASE_STORAGE_BUCKET: str = "resumes"
    STORE_UPLOADS: bool = True             # persist uploaded files to the bucket

    # --- AI (Gemini) ---
    GEMINI_API_KEY: str = ""  # empty => AI features report "disabled"
    GEMINI_MODEL: str = "gemini-flash-latest"

    # --- CORS ---
    # Same-origin deploy (FastAPI serves the frontend) needs no CORS, but we allow
    # local dev servers so Live Server / http.server work during development.
    CORS_ORIGINS: Annotated[List[str], NoDecode] = [
        "http://localhost:5500",
        "http://127.0.0.1:5500",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
    ]

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def _split_origins(cls, v):
        if isinstance(v, str):
            return [o.strip() for o in v.split(",") if o.strip()]
        return v

    @property
    def is_production(self) -> bool:
        return self.ENV.lower() == "production"

    @property
    def jwks_url(self) -> Optional[str]:
        if not self.SUPABASE_URL:
            return None
        return self.SUPABASE_URL.rstrip("/") + "/auth/v1/.well-known/jwks.json"

    @property
    def storage_enabled(self) -> bool:
        return bool(
            self.STORE_UPLOADS
            and self.SUPABASE_URL
            and self.SUPABASE_SERVICE_ROLE_KEY
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
