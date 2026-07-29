"""
Application configuration.

All settings load from environment variables (or a local .env file in dev) via
pydantic-settings. Nothing sensitive is ever hardcoded — on Coolify these values
come from the service's Environment Variables panel.
"""
from functools import lru_cache
from typing import List

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

    # --- Database ---
    # Local dev defaults to a SQLite file so the app runs with zero setup.
    # In production (Coolify), set DATABASE_URL to the Postgres connection string,
    # e.g. postgresql+psycopg://user:pass@host:5432/dbname
    DATABASE_URL: str = "sqlite:///./smartresume.db"

    # --- Auth (JWT) ---
    JWT_SECRET: str = "dev-only-change-me"  # MUST be overridden in production
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24h

    # --- AI (Gemini) ---
    GEMINI_API_KEY: str = ""  # empty => AI features report "disabled"
    # Alias that always tracks the current stable Flash model, so it won't 404
    # when Google retires a dated version (as happened to gemini-2.5-flash).
    GEMINI_MODEL: str = "gemini-flash-latest"

    # --- CORS ---
    # Same-origin deploy (FastAPI serves the frontend) needs no CORS, but we allow
    # local dev servers so Live Server / http.server work during development.
    # NoDecode stops pydantic-settings from JSON-parsing this from .env/env;
    # our validator below parses the Coolify-friendly comma-separated string.
    CORS_ORIGINS: Annotated[List[str], NoDecode] = [
        "http://localhost:5500",
        "http://127.0.0.1:5500",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
    ]

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def _split_origins(cls, v):
        # Allow a comma-separated string in the env var (Coolify-friendly).
        if isinstance(v, str):
            return [o.strip() for o in v.split(",") if o.strip()]
        return v

    @property
    def is_production(self) -> bool:
        return self.ENV.lower() == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
