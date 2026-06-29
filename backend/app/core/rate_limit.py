"""
Sliding-window rate limiter backed by Redis.

Limits per user_id (authenticated) or IP (anonymous).
Tiers:
  free       — 10 analyses / day
  pro        — 100 analyses / day
  enterprise — 1000 analyses / day
  anonymous  — 3 analyses / day (by IP)
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from enum import Enum

import redis.asyncio as aioredis

from app.core.logging import get_logger
from app.core.redis import PREFIX_RATE, TTL_RATE_WINDOW, get_redis

logger = get_logger(__name__)


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


@dataclass
class RateLimitResult:
    allowed: bool
    limit: int
    remaining: int
    reset_in_seconds: int


async def check_rate_limit(
    identifier: str,           # user_id or IP address
    tier: RateLimitTier = RateLimitTier.anonymous,
) -> RateLimitResult:
    """
    Sliding-window rate limit check using Redis INCR + EXPIRE.
    Returns RateLimitResult — callers should return 429 if allowed=False.
    """
    limit = DAILY_LIMITS[tier]
    window = _SECONDS_PER_DAY
    key = f"{PREFIX_RATE}{tier.value}:{identifier}"

    client: aioredis.Redis = await get_redis()

    try:
        pipe = client.pipeline(transaction=True)
        await pipe.incr(key)
        await pipe.ttl(key)
        count_raw, ttl = await pipe.execute()
        count = int(count_raw)

        # Set expiry only on first increment (ttl == -1 means no expiry yet)
        if ttl == -1:
            await client.expire(key, window)
            ttl = window

        remaining = max(0, limit - count)
        return RateLimitResult(
            allowed=count <= limit,
            limit=limit,
            remaining=remaining,
            reset_in_seconds=ttl if ttl > 0 else window,
        )
    except Exception as exc:
        # Fail open — log and allow request rather than blocking on Redis error
        logger.error("rate_limit.redis_error", identifier=identifier, error=str(exc))
        return RateLimitResult(allowed=True, limit=limit, remaining=limit, reset_in_seconds=window)
