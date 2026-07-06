"""
Sliding-window rate limiter backed by Redis (CLR-030).

Two limit planes:
  1. Daily analysis quota (per user tier) — guarded in analyse endpoint
  2. Per-endpoint hourly limits — enforced via check_endpoint_rate_limit()

Hourly endpoint limits:
  upload  — 3/hr anonymous, 20/hr authenticated
  auth    — 10/hr per IP (protects magic-link endpoint)
  default — same as upload

Sentry alert fires when any IP exceeds 50 requests/hr on any endpoint.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from enum import Enum

import redis.asyncio as aioredis

from app.core.logging import get_logger
from app.core.redis import PREFIX_RATE, get_redis

logger = get_logger(__name__)


def _sentry_capture(msg: str, extra: dict) -> None:
    try:
        import sentry_sdk
        with sentry_sdk.new_scope() as scope:
            scope.set_extra("rate_limit_data", extra)
            sentry_sdk.capture_message(msg, level="warning")
    except Exception:
        pass


class RateLimitTier(str, Enum):
    anonymous  = "anonymous"
    free       = "free"
    pro        = "pro"
    enterprise = "enterprise"


# Daily limits (analyses per day)
DAILY_LIMITS: dict[RateLimitTier, int] = {
    RateLimitTier.anonymous:  3,
    RateLimitTier.free:       10,
    RateLimitTier.pro:        100,
    RateLimitTier.enterprise: 1000,
}

_SECONDS_PER_DAY = 86_400
_SECONDS_PER_HOUR = 3_600

# (anonymous_limit, authenticated_limit)
_ENDPOINT_HOURLY_LIMITS: dict[str, tuple[int, int]] = {
    "upload":  (3, 20),
    "auth":    (10, 10),
    "default": (3, 20),
    # CLR-041 — public shared-analysis reads. Two planes:
    #   share_view — per-IP ceiling (middleware), generous enough for a
    #                human re-reading a shared page, tight enough to slow
    #                single-IP scraping.
    #   share_link — 100 views/hour PER LINK (checked in the endpoint,
    #                keyed by share id), the CLR-041 spec limit.
    "share_view": (30, 30),
    "share_link": (100, 100),
}

_SENTRY_ALERT_THRESHOLD = 50

# Per-user upload limits (uploads per hour) — security hardening item 9.
# Layered ON TOP of the per-endpoint hourly limit; keyed by user identity
# (or IP for anonymous) so a single account can't burst uploads.
_UPLOAD_HOURLY_LIMITS = {"free": 10, "paid": 50}

# Auth-failure monitoring — security hardening items 1/7. Not a login
# limiter (auth is Clerk); this tracks INVALID-TOKEN 401s at our API surface
# per IP, to alert on credential-stuffing / token-guessing spikes.
_AUTH_FAILURE_WINDOW_SECONDS = 300  # 5 minutes
_AUTH_FAILURE_ALERT_THRESHOLD = 10


@dataclass
class RateLimitResult:
    allowed: bool
    limit: int
    remaining: int
    reset_in_seconds: int


async def _redis_incr_window(key: str, window: int) -> tuple[int, int]:
    client: aioredis.Redis = await get_redis()
    pipe = client.pipeline(transaction=True)
    await pipe.incr(key)
    await pipe.ttl(key)
    count_raw, ttl = await pipe.execute()
    count = int(count_raw)
    if ttl == -1:
        await client.expire(key, window)
        ttl = window
    return count, (ttl if ttl > 0 else window)


async def check_rate_limit(
    identifier: str,
    tier: RateLimitTier = RateLimitTier.anonymous,
) -> RateLimitResult:
    limit = DAILY_LIMITS[tier]
    key = f"{PREFIX_RATE}daily:{tier.value}:{identifier}"
    try:
        count, ttl = await _redis_incr_window(key, _SECONDS_PER_DAY)
        remaining = max(0, limit - count)
        return RateLimitResult(
            allowed=count <= limit,
            limit=limit,
            remaining=remaining,
            reset_in_seconds=ttl,
        )
    except Exception as exc:
        logger.error("rate_limit.redis_error", identifier=identifier, error=str(exc))
        return RateLimitResult(allowed=True, limit=limit, remaining=limit, reset_in_seconds=_SECONDS_PER_DAY)


async def check_endpoint_rate_limit(
    identifier: str,
    endpoint: str = "default",
    authenticated: bool = False,
) -> RateLimitResult:
    anon_limit, auth_limit = _ENDPOINT_HOURLY_LIMITS.get(
        endpoint, _ENDPOINT_HOURLY_LIMITS["default"]
    )
    limit = auth_limit if authenticated else anon_limit
    key = f"{PREFIX_RATE}hourly:{endpoint}:{identifier}"

    try:
        count, ttl = await _redis_incr_window(key, _SECONDS_PER_HOUR)
        remaining = max(0, limit - count)
        allowed = count <= limit

        if count == _SENTRY_ALERT_THRESHOLD + 1:
            logger.warning(
                "rate_limit.sentry_alert_threshold",
                identifier=identifier,
                endpoint=endpoint,
                count=count,
            )
            _sentry_capture(
                f"Rate limit alert: {identifier} hit {count} req/hr on /{endpoint}",
                extra={"identifier": identifier, "endpoint": endpoint, "count": count, "limit": limit},
            )

        if not allowed:
            logger.warning(
                "rate_limit.endpoint_exceeded",
                identifier=identifier,
                endpoint=endpoint,
                count=count,
                limit=limit,
            )

        return RateLimitResult(
            allowed=allowed,
            limit=limit,
            remaining=remaining,
            reset_in_seconds=ttl,
        )
    except Exception as exc:
        logger.error("rate_limit.endpoint_redis_error", identifier=identifier, error=str(exc))
        return RateLimitResult(allowed=True, limit=limit, remaining=limit, reset_in_seconds=_SECONDS_PER_HOUR)


async def check_upload_rate_limit(identifier: str, *, paid: bool) -> RateLimitResult:
    """
    Per-user hourly upload cap (security hardening item 9):
    free = 10/hr, paid = 50/hr. Fail-open on Redis errors.
    """
    limit = _UPLOAD_HOURLY_LIMITS["paid" if paid else "free"]
    key = f"{PREFIX_RATE}upload_user:{identifier}"
    try:
        count, ttl = await _redis_incr_window(key, _SECONDS_PER_HOUR)
        return RateLimitResult(
            allowed=count <= limit,
            limit=limit,
            remaining=max(0, limit - count),
            reset_in_seconds=ttl,
        )
    except Exception as exc:
        logger.error("rate_limit.upload_redis_error", identifier=identifier, error=str(exc))
        return RateLimitResult(allowed=True, limit=limit, remaining=limit, reset_in_seconds=_SECONDS_PER_HOUR)


async def record_auth_failure(identifier: str) -> int:
    """
    Increment the 5-minute auth-failure counter for an IP and return the
    running count (security hardening items 1/7). Fail-open (returns 0 so
    callers never alert on a Redis outage).
    """
    key = f"{PREFIX_RATE}authfail:{identifier}"
    try:
        count, _ttl = await _redis_incr_window(key, _AUTH_FAILURE_WINDOW_SECONDS)
        return count
    except Exception:
        return 0


def auth_failure_alert_threshold() -> int:
    return _AUTH_FAILURE_ALERT_THRESHOLD
