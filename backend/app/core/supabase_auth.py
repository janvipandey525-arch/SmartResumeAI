"""
Supabase JWT verification.

The frontend authenticates with Supabase (GoTrue) and sends the resulting access
token as `Authorization: Bearer <jwt>`. This module verifies that token and
returns its claims. The backend NEVER issues tokens and never sees passwords —
GoTrue owns all of that.

Two verification modes, chosen automatically:
  * HS256  — when SUPABASE_JWT_SECRET is set (legacy shared secret).
  * JWKS   — otherwise, fetch the project's public signing keys from
             {SUPABASE_URL}/auth/v1/.well-known/jwks.json (asymmetric keys).
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

import httpx
from jose import jwt
from jose.exceptions import JWTError

from app.core.config import settings


class TokenError(Exception):
    """Raised when a bearer token is missing, malformed, or fails verification."""


@dataclass
class TokenClaims:
    sub: str                                   # user UUID (string form)
    email: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)  # user_metadata
    raw: Dict[str, Any] = field(default_factory=dict)


# --- JWKS cache (asymmetric mode) ---------------------------------------------
_JWKS_CACHE: Dict[str, Any] = {"keys": None, "fetched_at": 0.0}
_JWKS_TTL = 3600  # seconds


def _get_jwks() -> Dict[str, Any]:
    url = settings.jwks_url
    if not url:
        raise TokenError("No JWT secret and no SUPABASE_URL configured for JWKS.")
    now = time.time()
    if _JWKS_CACHE["keys"] is None or now - _JWKS_CACHE["fetched_at"] > _JWKS_TTL:
        try:
            resp = httpx.get(url, timeout=5.0)
            resp.raise_for_status()
            _JWKS_CACHE["keys"] = resp.json()
            _JWKS_CACHE["fetched_at"] = now
        except (httpx.HTTPError, ValueError) as e:  # network / bad JSON
            if _JWKS_CACHE["keys"] is None:
                raise TokenError(f"Could not fetch JWKS: {e}") from e
            # fall back to the last good copy on a transient failure
    return _JWKS_CACHE["keys"]


def _decode_hs256(token: str) -> Dict[str, Any]:
    return jwt.decode(
        token,
        settings.SUPABASE_JWT_SECRET,
        algorithms=["HS256"],
        audience=settings.SUPABASE_JWT_AUD,
    )


def _decode_jwks(token: str) -> Dict[str, Any]:
    header = jwt.get_unverified_header(token)
    kid = header.get("kid")
    jwks = _get_jwks()
    key = next((k for k in jwks.get("keys", []) if k.get("kid") == kid), None)
    if key is None:
        # key may have rotated — force one refresh
        _JWKS_CACHE["keys"] = None
        jwks = _get_jwks()
        key = next((k for k in jwks.get("keys", []) if k.get("kid") == kid), None)
    if key is None:
        raise TokenError("No matching JWKS key for token.")
    alg = key.get("alg", "ES256")
    return jwt.decode(
        token,
        key,
        algorithms=[alg],
        audience=settings.SUPABASE_JWT_AUD,
    )


def verify_token(token: str) -> TokenClaims:
    """Verify a Supabase access token and return its claims, or raise TokenError."""
    if not token:
        raise TokenError("Missing bearer token.")
    try:
        payload = _decode_hs256(token) if settings.SUPABASE_JWT_SECRET else _decode_jwks(token)
    except JWTError as e:
        raise TokenError(f"Invalid token: {e}") from e

    sub = payload.get("sub")
    if not sub:
        raise TokenError("Token has no subject (sub).")
    return TokenClaims(
        sub=str(sub),
        email=payload.get("email", "") or "",
        metadata=payload.get("user_metadata", {}) or {},
        raw=payload,
    )
