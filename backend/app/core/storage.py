"""
Thin Supabase Storage client (server-side).

We talk to the Storage REST API directly with httpx (already a dependency) using
the service_role key, rather than pulling in the full supabase-py stack. Only two
operations are needed: upload an object and mint a short-lived signed URL to read
it back.

The bucket (default "resumes") must exist and should be PRIVATE — objects are
never public; the frontend fetches them through signed URLs only. Bucket creation
lives in supabase/schema.sql / the setup notes.

All functions are best-effort: if Storage isn't configured they no-op (return
None) so uploads still get analyzed even without persistence.
"""
from __future__ import annotations

import logging
from typing import Optional

import httpx

from app.core.config import settings

log = logging.getLogger("smartresume.storage")


def _headers(content_type: Optional[str] = None) -> dict:
    key = settings.SUPABASE_SERVICE_ROLE_KEY
    h = {"Authorization": f"Bearer {key}", "apikey": key}
    if content_type:
        h["Content-Type"] = content_type
    return h


def upload(path: str, data: bytes, content_type: str = "application/octet-stream") -> Optional[str]:
    """
    Upload bytes to <bucket>/<path>. Returns the storage path on success, else None.
    Uses upsert so re-uploading the same path overwrites rather than 409s.
    """
    if not settings.storage_enabled:
        return None
    bucket = settings.SUPABASE_STORAGE_BUCKET
    url = f"{settings.SUPABASE_URL.rstrip('/')}/storage/v1/object/{bucket}/{path}"
    headers = _headers(content_type)
    headers["x-upsert"] = "true"
    try:
        resp = httpx.post(url, content=data, headers=headers, timeout=15.0)
        resp.raise_for_status()
        return path
    except httpx.HTTPError as e:
        log.warning("Storage upload failed for %s: %s", path, e)
        return None


def signed_url(path: str, expires_in: int = 3600) -> Optional[str]:
    """Return a temporary signed URL to read <bucket>/<path>, or None on failure."""
    if not settings.storage_enabled or not path:
        return None
    bucket = settings.SUPABASE_STORAGE_BUCKET
    url = f"{settings.SUPABASE_URL.rstrip('/')}/storage/v1/object/sign/{bucket}/{path}"
    try:
        resp = httpx.post(url, json={"expiresIn": expires_in}, headers=_headers("application/json"), timeout=10.0)
        resp.raise_for_status()
        signed = resp.json().get("signedURL")
        if not signed:
            return None
        return f"{settings.SUPABASE_URL.rstrip('/')}/storage/v1{signed}"
    except (httpx.HTTPError, ValueError) as e:
        log.warning("Signed URL failed for %s: %s", path, e)
        return None
