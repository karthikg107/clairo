"""Small per-request HTTP helpers shared across endpoints/middleware."""
from __future__ import annotations

from fastapi import HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User


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


async def require_user(request: Request, db: AsyncSession) -> User:
    """
    Resolve the authenticated User row for this request, or raise.

    401 if there's no Clerk id at all; 404 if the Clerk id doesn't map to
    a User row yet (e.g. sign-up hasn't completed provisioning).
    """
    clerk_id = get_clerk_id(request)
    if not clerk_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required"
        )

    result = await db.execute(select(User).where(User.clerk_id == clerk_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User record not found. Complete sign-up first.",
        )
    return user
