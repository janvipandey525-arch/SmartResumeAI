"""
Deterministic ATS scoring engine.

This is the "objective" half of the hybrid design: a fast, free, fully
explainable score. Every point can be traced to a rule, which is exactly what
you defend in a viva. The AI layer (ai_service.py) adds qualitative advice on
top — it never changes this number.

Score is a weighted blend of five dimensions, each computed to 0..100:

    keywords    0.35   overlap with the job description (or skill richness if none)
    sections    0.20   are the standard resume sections present?
    action_verbs 0.15  do bullets start with strong action verbs?
    impact      0.15   are achievements quantified (numbers, %, metrics)?
    readability 0.15   sane sentence length + bullet structure

Weights sum to 1.0. Final score = round(sum(subscore * weight)).
"""
from __future__ import annotations

import re
from typing import Dict, List, Optional, Tuple

WEIGHTS: Dict[str, float] = {
    "keywords": 0.35,
    "sections": 0.20,
    "action_verbs": 0.15,
    "impact": 0.15,
    "readability": 0.15,
}

# Common words we don't count as meaningful keywords.
STOPWORDS = {
    "the", "a", "an", "and", "or", "but", "for", "to", "of", "in", "on", "at",
    "by", "with", "as", "is", "are", "was", "were", "be", "been", "being", "this",
    "that", "these", "those", "it", "its", "i", "me", "my", "we", "our", "you",
    "your", "he", "she", "they", "them", "from", "up", "down", "out", "over",
    "under", "then", "than", "so", "if", "not", "no", "yes", "can", "will",
    "would", "should", "could", "may", "might", "do", "does", "did", "have",
    "has", "had", "am", "who", "what", "when", "where", "which", "how", "all",
    "any", "each", "more", "most", "other", "some", "such", "only", "own",
    "same", "too", "very", "just", "also", "into", "about", "using", "used",
}

# Strong resume action verbs (past tense + common bases).
ACTION_VERBS = {
    "achieved", "improved", "built", "created", "developed", "designed", "led",
    "managed", "implemented", "launched", "increased", "reduced", "optimized",
    "automated", "engineered", "architected", "delivered", "shipped", "drove",
    "spearheaded", "streamlined", "migrated", "refactored", "deployed", "scaled",
    "analyzed", "researched", "coordinated", "collaborated", "mentored", "owned",
    "founded", "initiated", "established", "generated", "boosted", "cut",
    "accelerated", "resolved", "integrated", "maintained", "tested", "debugged",
    "programmed", "wrote", "produced", "negotiated", "presented", "trained",
}

SECTION_KEYWORDS = {
    "contact": ["email", "phone", "@", "linkedin", "github"],
    "summary": ["summary", "objective", "profile", "about"],
    "experience": ["experience", "employment", "work history", "intern", "worked"],
    "education": ["education", "b.sc", "bachelor", "degree", "university", "college", "cgpa", "gpa"],
    "skills": ["skills", "technologies", "tech stack", "proficient", "languages"],
    "projects": ["project", "projects", "built", "developed"],
}

_WORD_RE = re.compile(r"[a-zA-Z][a-zA-Z0-9+#.\-]*")
_NUMBER_RE = re.compile(r"\b\d+(\.\d+)?%?\b|\b\d+[kKmM]\b|\$\d+")
_SENTENCE_RE = re.compile(r"[.!?\n]+")


def _tokens(text: str) -> List[str]:
    return [w.lower() for w in _WORD_RE.findall(text)]


def _keywords(text: str) -> List[str]:
    """Meaningful, de-duplicated keywords (stopwords + 1-char tokens removed)."""
    seen: Dict[str, None] = {}
    for w in _tokens(text):
        if len(w) > 1 and w not in STOPWORDS:
            seen.setdefault(w, None)
    return list(seen.keys())


def _clamp(x: float) -> float:
    return max(0.0, min(100.0, x))


def _score_keywords(
    resume_text: str, job_description: Optional[str]
) -> Tuple[float, List[str], List[str]]:
    """
    With a JD: overlap ratio between JD keywords and resume keywords.
    Without a JD: reward keyword richness (a proxy for a detailed resume).
    Returns (subscore, matched, missing).
    """
    resume_kw = set(_keywords(resume_text))

    if job_description and job_description.strip():
        jd_kw = _keywords(job_description)
        if not jd_kw:
            return 60.0, [], []
        matched = [k for k in jd_kw if k in resume_kw]
        missing = [k for k in jd_kw if k not in resume_kw]
        subscore = _clamp(100.0 * len(matched) / len(jd_kw))
        # Cap the "missing" list so the UI stays readable.
        return subscore, matched[:40], missing[:40]

    # No JD: richness — 25 distinct meaningful keywords ~= a full resume.
    richness = _clamp(100.0 * len(resume_kw) / 25.0)
    return richness, [], []


def _score_sections(resume_text: str) -> float:
    low = resume_text.lower()
    present = 0
    for _, markers in SECTION_KEYWORDS.items():
        if any(m in low for m in markers):
            present += 1
    return _clamp(100.0 * present / len(SECTION_KEYWORDS))


def _score_action_verbs(resume_text: str) -> float:
    """Fraction of non-trivial lines that open with a strong action verb."""
    lines = [ln.strip() for ln in resume_text.splitlines() if len(ln.strip()) > 12]
    if not lines:
        return 0.0
    strong = 0
    for ln in lines:
        # Strip leading bullet markers / numbering, then look at the first word.
        first = re.sub(r"^[\-\*•\d.\)\s]+", "", ln).split()
        if first and first[0].lower() in ACTION_VERBS:
            strong += 1
    # 60% of lines starting with action verbs already earns full marks.
    return _clamp(100.0 * (strong / len(lines)) / 0.6)


def _score_impact(resume_text: str) -> float:
    """Density of quantified achievements (numbers, %, $, k/m)."""
    # finditer (not findall) — the regex has groups, so findall would miscount.
    count = len(list(_NUMBER_RE.finditer(resume_text)))
    lines = [ln for ln in resume_text.splitlines() if len(ln.strip()) > 12] or [""]
    density = count / max(len(lines), 1)
    # ~0.5 quantified metrics per bullet line = full marks.
    return _clamp(100.0 * density / 0.5)


def _score_readability(resume_text: str) -> float:
    """Reward bullet structure + penalize very long sentences."""
    sentences = [s.strip() for s in _SENTENCE_RE.split(resume_text) if s.strip()]
    if not sentences:
        return 0.0
    avg_words = sum(len(s.split()) for s in sentences) / len(sentences)
    # Ideal average sentence/bullet length ~ 8-18 words.
    if avg_words <= 18:
        length_score = 100.0
    elif avg_words >= 40:
        length_score = 40.0
    else:
        length_score = 100.0 - (avg_words - 18) * (60.0 / 22.0)
    bullet_lines = sum(
        1 for ln in resume_text.splitlines() if ln.strip().startswith(("-", "*", "•"))
    )
    bullet_bonus = min(bullet_lines, 8) * 2.0  # up to +16 for using bullets
    return _clamp(length_score * 0.85 + bullet_bonus)


def score_to_grade(score: int) -> str:
    if score >= 90:
        return "A"
    if score >= 80:
        return "B"
    if score >= 70:
        return "C"
    if score >= 60:
        return "D"
    return "F"


def analyze(resume_text: str, job_description: Optional[str] = None) -> dict:
    """
    Run the full deterministic analysis.

    Returns a dict ready to persist as an AtsReport: score, grade, per-dimension
    breakdown, and matched/missing keyword lists.
    """
    resume_text = resume_text or ""
    kw_score, matched, missing = _score_keywords(resume_text, job_description)
    subs = {
        "keywords": round(kw_score, 1),
        "sections": round(_score_sections(resume_text), 1),
        "action_verbs": round(_score_action_verbs(resume_text), 1),
        "impact": round(_score_impact(resume_text), 1),
        "readability": round(_score_readability(resume_text), 1),
    }
    total = sum(subs[dim] * WEIGHTS[dim] for dim in WEIGHTS)
    score = int(round(_clamp(total)))
    return {
        "score": score,
        "grade": score_to_grade(score),
        "breakdown": subs,
        "weights": WEIGHTS,
        "matched_keywords": matched,
        "missing_keywords": missing,
    }


def resume_to_text(resume) -> str:
    """
    Flatten a Resume ORM object (or dict) into plain text for scoring / AI.

    Accepts either the SQLAlchemy model or a plain dict with the same fields.
    """
    def g(key, default=""):
        if isinstance(resume, dict):
            return resume.get(key, default)
        return getattr(resume, key, default)

    parts: List[str] = []
    pi = g("personal_info", {}) or {}
    if isinstance(pi, dict):
        parts.append(" ".join(str(v) for v in pi.values() if v))
    if g("summary"):
        parts.append(f"Summary: {g('summary')}")
    edu = g("education", []) or []
    if isinstance(edu, list):
        for e in edu:
            parts.append("Education: " + (" ".join(str(v) for v in e.values()) if isinstance(e, dict) else str(e)))
    skills = g("skills", []) or []
    if isinstance(skills, list) and skills:
        parts.append("Skills: " + ", ".join(str(s) for s in skills))
    for field in ("experience", "projects", "certifications"):
        val = g(field)
        if val:
            parts.append(f"{field.title()}:\n{val}")
    return "\n".join(parts)
