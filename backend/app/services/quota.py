"""
CLR-025 — Free tier lifetime quota.

2 free analyses per user, for life — this is NOT a rolling/daily window
(that's the separate, orthogonal mechanism in app/core/rate_limit.py).

Authenticated users are tracked on users.free_analyses_used and are exempt
once their subscription tier is anything other than "free".

Anonymous users are tracked in Redis, keyed by BOTH the client-supplied
anonymous device id (X-Anonymous-Id header, sourced from localStorage on
the frontend — see lib/anonymousId.ts) and IP address. Quota is considered
exhausted if EITHER signal has reached the limit: clearing localStorage
alone does not reset quota (the IP signal still blocks), while distinct
users behind a shared IP (e.g. office/campus NAT) are still each given
their own allowance via the device id.

SECURITY / RESILIENCE:
- Fails open on Redis/DB errors, matching the existing rate-limiter
  convention (app/core/rate_limit.py) — an infra outage must never block
  the product. The tradeoff is a determined abuser could get extra free
  analyses during an outage window; this is a deliberate, documented
  choice, not an oversight.
- Never logs or stores document content — only counts and identifiers
  that are already used for rate limiting elsewhere.
"""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.logging import get_logger
from app.core.redis import get_redis
from app.db.session import get_session_factory
from app.models.subscription import SubscriptionTier
from app.models.user import User

logger = get_logger(__name__)

FREE_LIFETIME_LIMIT = 2

PREFIX_LIFETIME_QUOTA = "quota:lifetime:"
# Long but finite TTL, purely for Redis storage hygiene on anonymous keys —
# NOT a product decision to ever "reset" someone's lifetime quota.
TTL_LIFETIME_QUOTA = 60 * 60 * 24 * 365 * 2


@dataclass
class QuotaStatus:
    allowed: bool
    is_free_tier: bool
    used: int
    limit: int
    remaining: int


def _is_paid_tier(user: User) -> bool:
    sub = user.subscription
    return sub is not None and sub.tier != SubscriptionTier.free


def _status_for_user(user: User) -> QuotaStatus:
    if _is_paid_tier(user):
        return QuotaStatus(
            allowed=True, is_free_tier=False,
            used=0, limit=FREE_LIFETIME_LIMIT, remaining=FREE_LIFETIME_LIMIT,
        )
    used = user.free_analyses_used
    return QuotaStatus(
        allowed=used < FREE_LIFETIME_LIMIT,
        is_free_tier=True,
        used=used,
        limit=FREE_LIFETIME_LIMIT,
        remaining=max(0, FREE_LIFETIME_LIMIT - used),
    )


async def _load_user(clerk_id: str) -> User | None:
    try:
        factory = get_session_factory()
        async with factory() as session:
            result = await session.execute(
                select(User)
                .options(selectinload(User.subscription))
                .where(User.clerk_id == clerk_id)
            )
            return result.scalar_one_or_none()
    except Exception as exc:
        logger.warning("quota.user_lookup_failed", error=str(exc))
        return None


async def _redis_get_count(key: str) -> int:
    try:
        client = await get_redis()
        raw = await client.get(key)
        return int(raw) if raw else 0
    except Exception as exc:
        logger.warning("quota.redis_read_failed", error=str(exc))
        return 0


async def _redis_increment(key: str) -> None:
    try:
        client = await get_redis()
        count = await client.incr(key)
        if count == 1:
            await client.expire(key, TTL_LIFETIME_QUOTA)
    except Exception as exc:
        logger.warning("quota.redis_increment_failed", error=str(exc))


async def _status_for_anonymous(anonymous_id: str | None, ip: str) -> QuotaStatus:
    ip_used = await _redis_get_count(f"{PREFIX_LIFETIME_QUOTA}ip:{ip}")
    device_used = (
        await _redis_get_count(f"{PREFIX_LIFETIME_QUOTA}device:{anonymous_id}")
        if anonymous_id else 0
    )
    used = max(ip_used, device_used)
    return QuotaStatus(
        allowed=used < FREE_LIFETIME_LIMIT,
        is_free_tier=True,
        used=used,
        limit=FREE_LIFETIME_LIMIT,
        remaining=max(0, FREE_LIFETIME_LIMIT - used),
    )


async def check_quota(*, clerk_id: str | None, anonymous_id: str | None, ip: str) -> QuotaStatus:
    """Read-only — call before running analysis to decide whether to allow it."""
    if clerk_id:
        user = await _load_user(clerk_id)
        if user is not None:
            return _status_for_user(user)
        # clerk_id given but no matching/reachable user row — fall through
        # to anonymous tracking rather than allowing unlimited analyses.
    return await _status_for_anonymous(anonymous_id, ip)


async def _increment_authenticated(clerk_id: str) -> bool:
    """Returns True if a user row was found (and updated, unless paid tier)."""
    try:
        factory = get_session_factory()
        async with factory() as session:
            result = await session.execute(
                select(User)
                .options(selectinload(User.subscription))
                .where(User.clerk_id == clerk_id)
            )
            user = result.scalar_one_or_none()
            if user is None:
                return False
            if not _is_paid_tier(user):
                user.free_analyses_used += 1
                await session.commit()
            return True
    except Exception as exc:
        logger.warning("quota.increment_failed", error=str(exc))
        return False


async def consume_quota(*, clerk_id: str | None, anonymous_id: str | None, ip: str) -> None:
    """
    Call only after a successful, permitted analysis (cache hit or miss —
    both count, since quota is about analyses delivered to the user, not
    Claude API spend). Never raises.
    """
    if clerk_id and await _increment_authenticated(clerk_id):
        return
    # No clerk_id, or a DB error / missing user row — fall through to
    # anonymous tracking, mirroring check_quota's fallback above.

    await _redis_increment(f"{PREFIX_LIFETIME_QUOTA}ip:{ip}")
    if anonymous_id:
        await _redis_increment(f"{PREFIX_LIFETIME_QUOTA}device:{anonymous_id}")
