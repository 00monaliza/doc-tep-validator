"""Who is calling: a Supabase Auth user, from the `Authorization: Bearer <access token>` header.

Auth is on exactly when checks live in Supabase (SUPABASE_URL and SUPABASE_SECRET_KEY are set):
there the service is public and holds client documents. A local run keeps its folder store and
needs no login. The leading underscore keeps Vercel from making this file a function.
"""

from __future__ import annotations

import hashlib
import os
import time

import httpx
from fastapi import Header, HTTPException

TOKEN_TTL_S = 60  # a verified token is trusted this long before Supabase is asked again
_verified: dict[str, tuple[str, str, float]] = {}  # sha256(token) -> (user id, email, expiry)


def enabled() -> bool:
    return bool(os.environ.get("SUPABASE_URL") and os.environ.get("SUPABASE_SECRET_KEY"))


def public_config() -> dict | None:
    """What the browser needs to sign in: the project URL and its publishable key (both public)."""
    url, key = os.environ.get("SUPABASE_URL"), os.environ.get("SUPABASE_PUBLISHABLE_KEY")
    return {"url": url, "key": key} if enabled() and url and key else None


def _verify(token: str) -> tuple[str, str] | None:
    digest = hashlib.sha256(token.encode()).hexdigest()
    hit = _verified.get(digest)
    if hit and hit[2] > time.time():
        return hit[0], hit[1]
    url = os.environ["SUPABASE_URL"].rstrip("/")
    try:
        r = httpx.get(f"{url}/auth/v1/user", timeout=10,
                      headers={"apikey": os.environ["SUPABASE_SECRET_KEY"], "Authorization": f"Bearer {token}"})
    except httpx.HTTPError:
        raise HTTPException(503, "Сервис входа недоступен, повторите позже") from None
    if r.status_code != 200:
        return None
    user = r.json()
    if len(_verified) > 1000:  # a small process-local cache, not a store
        _verified.clear()
    _verified[digest] = (user["id"], user.get("email") or "", time.time() + TOKEN_TTL_S)
    return user["id"], user.get("email") or ""


def current_user(authorization: str | None = Header(default=None)) -> str | None:
    """FastAPI dependency: the user id, or None when auth is off (local run)."""
    if not enabled():
        return None
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Нужно войти")
    found = _verify(authorization.removeprefix("Bearer ").strip())
    if found is None:
        raise HTTPException(401, "Сессия истекла, войдите снова")
    return found[0]
