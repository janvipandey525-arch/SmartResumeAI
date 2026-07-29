"""
Shared rate limiter (slowapi).

Protects the AI-backed endpoints so nobody can spam Gemini and burn the free
daily quota. Keyed by client IP. Wired into the app in main.py.
"""
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
