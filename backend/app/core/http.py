"""Small per-request HTTP helpers shared across endpoints/middleware."""
from __future__ import annotations

from fastapi import Request


def get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def get_clerk_id(request: Request) -> str | None:
    """
    Resolve the authenticated user's Clerk id, if any.

    Populated by JWTAuthMiddleware (CLR-031); falls back to the
    X-Clerk-User-Id header for local development without Clerk configured.
    Returns None for anonymous requests — callers must handle that case.
    """
    clerk_id: str | None = getattr(request.state, "clerk_id", None)
    return clerk_id or request.headers.get("X-Clerk-User-Id")
