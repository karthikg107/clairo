"""
CLR-031 — JWT authentication middleware.

Verifies Clerk-issued JWTs on every non-public request.

- Fetches Clerk JWKS once at startup, caches with TTL
- Verifies RS256 signature, iss, aud, exp, nbf
- Populates request.state.clerk_id, user_id, subscription_tier
- Returns 401 {"detail": "Unauthorized"} with NO system information on any failure
- Public routes are explicitly exempt (no auth required)

SECURITY:
- Token is extracted from Authorization: Bearer <token> header only
- JWKS cached for 1 hour — refreshed on 401 from upstream or TTL expiry
- Any exception → 401 (never leaks error detail to caller)
- audit_log write is intentionally skipped here (done per endpoint)
"""
from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

import httpx
import jwt
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.http import get_client_ip
from app.core.logging import get_logger
from app.core.rate_limit import auth_failure_alert_threshold, record_auth_failure
from app.core.security_events import (
    EVENT_AUTH_FAILED,
    EVENT_AUTH_FAILURE_SPIKE,
    log_security_event,
)

logger = get_logger(__name__)

# Routes that do NOT require a valid JWT
_PUBLIC_PREFIXES = (
    "/api/v1/health",
    "/api/v1/ready",
    "/docs",
    "/redoc",
    "/openapi.json",
    # Called by Stripe, not the frontend — no Clerk JWT is ever present.
    # Authenticity is verified separately via the Stripe webhook signature
    # (CLR-026, app/services/billing.py:verify_webhook_signature).
    "/api/v1/billing/webhook",
    # Public shared-analysis reads (CLR-041) — recipients have no account.
    # ONLY the read path: /api/v1/share-links (create/revoke) stays auth'd.
    "/api/v1/shared/",
    # RFC 9116 security.txt — public by definition.
    "/.well-known/",
)

_JWKS_TTL_SECONDS = 3600  # refresh JWKS every hour
_UNAUTHORIZED = JSONResponse(
    status_code=401,
    content={"detail": "Unauthorized"},
    # No WWW-Authenticate header — avoids leaking scheme info
)


class _JwksCache:
    """Thread-safe (GIL) in-process JWKS cache with TTL."""

    def __init__(self) -> None:
        self._keys: list[dict] = []
        self._fetched_at: float = 0.0
        self._jwks_url: str = ""

    def configure(self, jwks_url: str) -> None:
        self._jwks_url = jwks_url

    def _is_stale(self) -> bool:
        return (time.monotonic() - self._fetched_at) > _JWKS_TTL_SECONDS

    async def get_keys(self, force_refresh: bool = False) -> list[dict]:
        if self._keys and not self._is_stale() and not force_refresh:
            return self._keys
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(self._jwks_url)
            resp.raise_for_status()
            data = resp.json()
        self._keys = data.get("keys", [])
        self._fetched_at = time.monotonic()
        logger.info("jwks.refreshed", key_count=len(self._keys))
        return self._keys


_jwks_cache = _JwksCache()


def _extract_bearer(request: Request) -> str | None:
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return auth[7:]
    return None


def _is_public(path: str) -> bool:
    return any(path.startswith(prefix) for prefix in _PUBLIC_PREFIXES)


class JWTAuthMiddleware(BaseHTTPMiddleware):
    """
    Verifies Clerk JWT on every non-public request.
    Sets request.state: clerk_id, user_id, subscription_tier.
    """

    def __init__(self, app, *, clerk_jwks_url: str, clerk_issuer: str) -> None:
        super().__init__(app)
        _jwks_cache.configure(clerk_jwks_url)
        self._issuer = clerk_issuer

    async def _note_auth_failure(self, request: Request, reason: str) -> None:
        """
        Record an invalid-token 401 (security hardening items 1/7). This is
        NOT a login limiter — logins happen in Clerk — but it gives us an
        audit trail and a Sentry spike alert for token-guessing / credential-
        stuffing against our API. Never affects the response (fail-open).
        """
        try:
            ip = get_client_ip(request)
            count = await record_auth_failure(ip)
            await log_security_event(
                action=EVENT_AUTH_FAILED,
                request=request,
                metadata={"reason": reason, "path": request.url.path},
            )
            if count == auth_failure_alert_threshold() + 1:
                await log_security_event(
                    action=EVENT_AUTH_FAILURE_SPIKE,
                    request=request,
                    metadata={"count": count, "window_seconds": 300},
                    alert=True,
                    alert_message=(
                        f"Auth-failure spike: {count} invalid-token 401s "
                        f"from {ip} in 5 minutes"
                    ),
                )
        except Exception:
            pass

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if _is_public(request.url.path):
            return await call_next(request)

        token = _extract_bearer(request)
        if not token:
            await self._note_auth_failure(request, "missing_token")
            return _UNAUTHORIZED

        try:
            payload = await self._verify_token(token)
        except Exception:
            # Never leak the reason — just 401
            await self._note_auth_failure(request, "invalid_token")
            return _UNAUTHORIZED

        # Populate request state for downstream middleware + endpoints
        sub: str = payload.get("sub", "")
        request.state.clerk_id = sub
        request.state.user_id = sub  # same value; user_id used by rate limiter
        # Clerk puts subscription tier in public metadata; default to "free"
        public_meta: dict = payload.get("public_metadata", {})
        request.state.subscription_tier = public_meta.get("tier", "free")

        return await call_next(request)

    async def _verify_token(self, token: str) -> dict[str, Any]:
        """
        Verify JWT using cached JWKS.
        Retries with fresh JWKS on first signature failure (handles key rotation).
        """
        try:
            return await self._decode(token, force_refresh=False)
        except jwt.exceptions.PyJWKClientError:
            # KID not found in cache — might be a newly rotated key
            return await self._decode(token, force_refresh=True)

    async def _decode(self, token: str, *, force_refresh: bool) -> dict[str, Any]:
        keys = await _jwks_cache.get_keys(force_refresh=force_refresh)

        # Find the matching JWK by 'kid' header
        unverified_header = jwt.get_unverified_header(token)
        kid = unverified_header.get("kid")

        matching_key = None
        for k in keys:
            if k.get("kid") == kid:
                matching_key = jwt.algorithms.RSAAlgorithm.from_jwk(k)
                break

        if matching_key is None:
            raise jwt.exceptions.PyJWKClientError(f"No matching key for kid={kid}")

        return jwt.decode(
            token,
            key=matching_key,
            algorithms=["RS256"],
            issuer=self._issuer,
            options={
                "verify_exp": True,
                "verify_nbf": True,
                "verify_iss": True,
                # Clerk tokens don't always have an audience claim
                "verify_aud": False,
            },
        )
