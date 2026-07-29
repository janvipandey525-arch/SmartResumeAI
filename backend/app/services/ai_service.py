"""
AI service — the qualitative half of the hybrid design.

All Gemini calls live behind this one module. Routers call generate_feedback()
and rewrite_bullet(), never the Gemini endpoint directly. If Google changes
models or quotas, you fix it here in one place (provider abstraction).

Every function returns a dict: {"status": ok|disabled|error, "text": "..."}.
  - disabled: no GEMINI_API_KEY configured — the app still works, AI is just off.
  - error:    the call failed; the reason is in text (shown in logs, not to users raw).
  - ok:       text holds the model's response.

We call the REST endpoint with httpx rather than the SDK to keep the dependency
surface small and the behavior identical to what we validated by hand.
"""
from __future__ import annotations

import json
from typing import Optional

import httpx

from app.core.config import settings

_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
_TIMEOUT = httpx.Timeout(30.0, connect=10.0)


def _disabled() -> dict:
    return {"status": "disabled", "text": "AI is off (no GEMINI_API_KEY configured)."}


def _call_gemini(prompt: str, *, max_tokens: int = 800, temperature: float = 0.4) -> dict:
    if not settings.GEMINI_API_KEY:
        return _disabled()

    url = _ENDPOINT.format(model=settings.GEMINI_MODEL)
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": temperature,
            "maxOutputTokens": max_tokens,
        },
    }
    headers = {
        "x-goog-api-key": settings.GEMINI_API_KEY,
        "Content-Type": "application/json",
    }
    try:
        with httpx.Client(timeout=_TIMEOUT) as client:
            resp = client.post(url, headers=headers, json=payload)
        if resp.status_code != 200:
            # Surface Google's own error message (truncated) for debugging.
            detail = resp.text[:300]
            return {"status": "error", "text": f"Gemini HTTP {resp.status_code}: {detail}"}
        data = resp.json()
        candidates = data.get("candidates") or []
        if not candidates:
            reason = data.get("promptFeedback", {}).get("blockReason", "no candidates")
            return {"status": "error", "text": f"No output ({reason})."}
        parts = candidates[0].get("content", {}).get("parts", [])
        text = "".join(p.get("text", "") for p in parts).strip()
        return {"status": "ok", "text": text}
    except (httpx.HTTPError, json.JSONDecodeError, KeyError) as e:
        return {"status": "error", "text": f"Gemini call failed: {type(e).__name__}: {e}"}


def generate_feedback(
    resume_text: str,
    score: int,
    breakdown: dict,
    job_description: Optional[str] = None,
) -> dict:
    """
    Career-coach feedback grounded in the deterministic score.

    We hand the model the objective numbers so its advice reinforces (not
    contradicts) the rule engine — the whole point of the hybrid.
    """
    jd_block = (
        f"\n\nTARGET JOB DESCRIPTION:\n{job_description.strip()}"
        if job_description and job_description.strip()
        else "\n\n(No target job description provided — give general improvements.)"
    )
    prompt = (
        "You are an expert resume reviewer and ATS specialist. A deterministic "
        "ATS engine already scored this resume. Your job is to give specific, "
        "actionable improvements — do NOT restate the score or invent new numbers.\n\n"
        f"ATS SCORE: {score}/100\n"
        f"DIMENSION BREAKDOWN (0-100 each): {json.dumps(breakdown)}\n"
        f"RESUME TEXT:\n{resume_text[:6000]}"
        f"{jd_block}\n\n"
        "Return 3-5 prioritized, concrete suggestions as a numbered list. Each "
        "suggestion: one bold pointer phrase, then one sentence of why/how. Focus "
        "on the weakest dimensions. Be direct and practical. No preamble."
    )
    return _call_gemini(prompt, max_tokens=800, temperature=0.4)


def rewrite_bullet(bullet: str) -> dict:
    """Turn a weak resume bullet into 2-3 strong, quantified rewrites."""
    prompt = (
        "Rewrite this weak resume bullet point into 2-3 stronger versions. Each "
        "must start with a strong action verb and include a plausible quantified "
        "result (%, time saved, scale). Return only the rewrites as a numbered "
        f"list, no preamble.\n\nWEAK BULLET: {bullet.strip()}"
    )
    return _call_gemini(prompt, max_tokens=300, temperature=0.6)
