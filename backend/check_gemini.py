"""
Quick check that your Gemini API key (in .env) actually works.

Run from the backend folder with your virtualenv active:
    python test_gemini.py

Interpreting the output:
  status: ok        -> your key works; real AI text is printed below. You're done.
  status: error     -> the key was rejected/failed; the real Google error is printed
                       (e.g. "API_KEY_INVALID" means the key value is wrong).
  status: disabled  -> no key found in .env (check GEMINI_API_KEY is set).
"""
from app.core.config import settings
from app.services import ai_service

print("GEMINI_API_KEY present:", bool(settings.GEMINI_API_KEY))
print("Model:", settings.GEMINI_MODEL)
print("-" * 50)

result = ai_service.rewrite_bullet("responsible for the company website")
print("status:", result["status"])
print("output:\n" + result["text"])
