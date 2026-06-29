"""Rate limiting middleware — adds standard headers, returns 429 when exceeded."""
from collections.abc import Callable

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.logging import get_logger
from app.core.rate_limit import RateLimitTier, check_rate_limit

logger = get_logger(__name__)

# Paths exempt from rate limiting
_EXEMPT_PATHS = {"/api/v1/health", "/api/v1/ready", "/docs", "/openapi.json"}


def _get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if request.url.path in _EXEMPT_PATHS:
            return await call_next(request)

        # Identify caller — prefer authenticated user_id (set by auth middleware later)
        user_id: str | None = getattr(request.state, "user_id", None)
        tier_str: str = getattr(request.state, "subscription_tier", "anonymous")

        try:
            tier = RateLimitTier(tier_str)
        except ValueError:
            tier = RateLimitTier.anonymous

        identifier = user_id or _get_client_ip(request)
        result = await check_rate_limit(identifier, tier)

        if not result.allowed:
            logger.warning(
                "rate_limit.exceeded",
                identifier=identifier,
                tier=tier.value,
                limit=result.limit,
            )
            return JSONResponse(
                status_code=429,
                content={"detail": "Rate limit exceeded. Please upgrade your plan or try later."},
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
