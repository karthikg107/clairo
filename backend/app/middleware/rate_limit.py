"""
Rate limiting middleware (CLR-030).

Two planes:
  1. Hourly per-endpoint limit (this middleware) — upload, auth, default
  2. Daily analysis quota — enforced inside the analyse endpoint

Limits:
  /api/v1/upload   — 3/hr anonymous, 20/hr authenticated
  /api/v1/auth/*   — 10/hr per IP
  everything else  — 3/hr anonymous, 20/hr authenticated

Sentry alert fires when any identifier crosses 50 req/hr.
"""
from collections.abc import Callable

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.http import get_client_ip
from app.core.logging import get_logger
from app.core.rate_limit import RateLimitTier, check_endpoint_rate_limit, check_rate_limit

logger = get_logger(__name__)

# Paths that bypass ALL rate limiting
_EXEMPT_PATHS = {
    "/api/v1/health",
    "/api/v1/ready",
    "/docs",
    "/openapi.json",
    "/api/v1/billing/webhook",  # called by Stripe, not end users (CLR-026)
}

# Path-prefix → endpoint key for hourly limits
_ENDPOINT_KEYS: list[tuple[str, str]] = [
    ("/api/v1/upload", "upload"),
    ("/api/v1/auth",   "auth"),
    ("/api/v1/sign",   "auth"),   # Clerk webhook paths
]


def _endpoint_key(path: str) -> str:
    for prefix, key in _ENDPOINT_KEYS:
        if path.startswith(prefix):
            return key
    return "default"


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if request.url.path in _EXEMPT_PATHS:
            return await call_next(request)

        # Authenticated user_id and tier populated by JWTMiddleware (CLR-031)
        # They may be None here if middleware order puts rate limit before JWT
        user_id: str | None = getattr(request.state, "user_id", None)
        authenticated = user_id is not None

        # For hourly endpoint limiting: prefer user_id, fall back to IP
        identifier = user_id or get_client_ip(request)
        endpoint = _endpoint_key(request.url.path)

        result = await check_endpoint_rate_limit(
            identifier=identifier,
            endpoint=endpoint,
            authenticated=authenticated,
        )

        if not result.allowed:
            return JSONResponse(
                status_code=429,
                content={
                    "detail": "Rate limit exceeded. Please wait before trying again.",
                    "retry_after": result.reset_in_seconds,
                },
                headers={
                    "X-RateLimit-Limit": str(result.limit),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(result.reset_in_seconds),
                    "Retry-After": str(result.reset_in_seconds),
                },
            )

        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(result.limit)
        response.headers["X-RateLimit-Remaining"] = str(result.remaining)
        response.headers["X-RateLimit-Reset"] = str(result.reset_in_seconds)
        return response
