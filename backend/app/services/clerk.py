"""
Clerk backend API helpers.

Currently one operation: deleting a Clerk user on GDPR account deletion,
which revokes ALL of that user's active sessions (security hardening
item 6 — "invalidate all sessions on account deletion"). Session lifetime,
refresh-token rotation, and concurrent-session caps are Clerk dashboard
settings (see docs/clerk-security-config.md) — they are not enforceable
from our backend.
"""
from __future__ import annotations

import httpx

from app.core.logging import get_logger
from app.core.secrets import get_secret

logger = get_logger(__name__)

CLERK_API_BASE = "https://api.clerk.com/v1"


async def delete_clerk_user(clerk_id: str) -> bool:
    """
    Delete the Clerk user, revoking all their sessions. Best-effort: never
    raises, returns True only on confirmed success. A failure here must not
    block local account deletion (the user's data is already gone).
    """
    if not clerk_id:
        return False
    secret = get_secret("clairo/clerk").get("secret_key", "")
    if not secret:
        logger.warning("clerk.delete_user_no_secret")
        return False
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.delete(
                f"{CLERK_API_BASE}/users/{clerk_id}",
                headers={"Authorization": f"Bearer {secret}"},
            )
        if resp.status_code in (200, 204):
            logger.info("clerk.user_deleted")
            return True
        logger.warning("clerk.delete_user_failed", status=resp.status_code)
        return False
    except Exception as exc:
        logger.warning("clerk.delete_user_error", error=str(exc))
        return False
