"""
CLR-025 — Free tier lifetime quota tests.

Authenticated-user paths mock the DB session factory (no live Postgres
needed, matching how every other DB-touching write in this codebase is
tested — e.g. there's no existing live-DB test fixture in this repo).
Anonymous paths use fakeredis, matching app/core/rate_limit.py's tests.
"""
from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import fakeredis.aioredis
import pytest

from app.models.subscription import Subscription, SubscriptionStatus, SubscriptionTier
from app.models.user import User
from app.services.quota import (
    FREE_LIFETIME_LIMIT,
    TTL_LIFETIME_QUOTA,
    _is_paid_tier,
    _status_for_user,
    check_quota,
    consume_quota,
)


def _make_user(*, free_analyses_used: int = 0, tier: SubscriptionTier | None = None) -> User:
    user = User(
        id=uuid.uuid4(),
        clerk_id="user_abc",
        email="test@example.com",
        free_analyses_used=free_analyses_used,
    )
    if tier is not None:
        user.subscription = Subscription(
            user_id=user.id, tier=tier, status=SubscriptionStatus.active
        )
    else:
        user.subscription = None
    return user


def _mock_session_factory(user: User | None):
    """
    Build a fake replacement for `get_session_factory`, matching the real
    two-level call shape: `factory = get_session_factory(); async with
    factory() as session:`. `session_factory()` must return a FRESH context
    manager each call — an already-entered one can't be reused.
    """
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = user

    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=mock_result)

    @asynccontextmanager
    async def factory_cm():
        yield mock_session

    session_factory = MagicMock(side_effect=lambda: factory_cm())
    get_session_factory_mock = MagicMock(return_value=session_factory)
    return get_session_factory_mock, mock_session


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def fake_redis():
    return fakeredis.aioredis.FakeRedis(decode_responses=True)


@pytest.fixture(autouse=True)
def patch_get_redis(fake_redis):
    with patch("app.services.quota.get_redis", new=AsyncMock(return_value=fake_redis)):
        yield fake_redis


# ── _is_paid_tier / _status_for_user (pure, no I/O) ───────────────────────────

class TestIsPaidTier:
    def test_no_subscription_is_not_paid(self):
        user = _make_user()
        assert _is_paid_tier(user) is False

    def test_free_subscription_is_not_paid(self):
        user = _make_user(tier=SubscriptionTier.free)
        assert _is_paid_tier(user) is False

    def test_pro_subscription_is_paid(self):
        user = _make_user(tier=SubscriptionTier.pro)
        assert _is_paid_tier(user) is True

    def test_enterprise_subscription_is_paid(self):
        user = _make_user(tier=SubscriptionTier.enterprise)
        assert _is_paid_tier(user) is True


class TestStatusForUser:
    def test_paid_user_always_allowed(self):
        user = _make_user(free_analyses_used=999, tier=SubscriptionTier.pro)
        status = _status_for_user(user)
        assert status.allowed is True
        assert status.is_free_tier is False

    def test_free_user_under_limit_allowed(self):
        user = _make_user(free_analyses_used=1)
        status = _status_for_user(user)
        assert status.allowed is True
        assert status.is_free_tier is True
        assert status.used == 1
        assert status.remaining == 1

    def test_free_user_at_limit_blocked(self):
        user = _make_user(free_analyses_used=FREE_LIFETIME_LIMIT)
        status = _status_for_user(user)
        assert status.allowed is False
        assert status.remaining == 0

    def test_free_user_over_limit_blocked_remaining_not_negative(self):
        user = _make_user(free_analyses_used=FREE_LIFETIME_LIMIT + 5)
        status = _status_for_user(user)
        assert status.allowed is False
        assert status.remaining == 0


# ── check_quota — authenticated ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_check_quota_authenticated_under_limit():
    user = _make_user(free_analyses_used=0)
    factory, _ = _mock_session_factory(user)
    with patch("app.services.quota.get_session_factory", factory):
        status = await check_quota(clerk_id="user_abc", anonymous_id=None, ip="1.2.3.4")
    assert status.allowed is True
    assert status.is_free_tier is True


@pytest.mark.asyncio
async def test_check_quota_authenticated_at_limit():
    user = _make_user(free_analyses_used=FREE_LIFETIME_LIMIT)
    factory, _ = _mock_session_factory(user)
    with patch("app.services.quota.get_session_factory", factory):
        status = await check_quota(clerk_id="user_abc", anonymous_id=None, ip="1.2.3.4")
    assert status.allowed is False


@pytest.mark.asyncio
async def test_check_quota_authenticated_paid_tier_unlimited():
    user = _make_user(free_analyses_used=FREE_LIFETIME_LIMIT, tier=SubscriptionTier.pro)
    factory, _ = _mock_session_factory(user)
    with patch("app.services.quota.get_session_factory", factory):
        status = await check_quota(clerk_id="user_abc", anonymous_id=None, ip="1.2.3.4")
    assert status.allowed is True
    assert status.is_free_tier is False


@pytest.mark.asyncio
async def test_check_quota_authenticated_user_not_found_falls_back_to_anonymous(fake_redis):
    """clerk_id given but no matching row — falls back to IP/device tracking."""
    factory, _ = _mock_session_factory(None)
    with patch("app.services.quota.get_session_factory", factory):
        status = await check_quota(clerk_id="ghost_user", anonymous_id=None, ip="9.9.9.9")
    assert status.allowed is True  # fresh IP, no usage yet


@pytest.mark.asyncio
async def test_check_quota_authenticated_db_error_fails_open_to_anonymous():
    def _raise(*a, **kw):
        raise RuntimeError("db down")

    with patch("app.services.quota.get_session_factory", _raise):
        status = await check_quota(clerk_id="user_abc", anonymous_id=None, ip="5.5.5.5")
    assert status.allowed is True


# ── check_quota — anonymous ───────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_check_quota_anonymous_fresh_allowed():
    status = await check_quota(clerk_id=None, anonymous_id="dev-1", ip="1.1.1.1")
    assert status.allowed is True
    assert status.used == 0
    assert status.remaining == FREE_LIFETIME_LIMIT


@pytest.mark.asyncio
async def test_check_quota_anonymous_ip_at_limit_blocks(fake_redis):
    await fake_redis.set("quota:lifetime:ip:2.2.2.2", FREE_LIFETIME_LIMIT)
    status = await check_quota(clerk_id=None, anonymous_id="dev-2", ip="2.2.2.2")
    assert status.allowed is False


@pytest.mark.asyncio
async def test_check_quota_anonymous_device_at_limit_blocks_even_new_ip(fake_redis):
    """Clearing/spoofing IP alone doesn't help if the device id is exhausted."""
    await fake_redis.set("quota:lifetime:device:dev-3", FREE_LIFETIME_LIMIT)
    status = await check_quota(clerk_id=None, anonymous_id="dev-3", ip="3.3.3.3")
    assert status.allowed is False


@pytest.mark.asyncio
async def test_check_quota_anonymous_no_device_id_uses_ip_only(fake_redis):
    await fake_redis.set("quota:lifetime:ip:4.4.4.4", FREE_LIFETIME_LIMIT)
    status = await check_quota(clerk_id=None, anonymous_id=None, ip="4.4.4.4")
    assert status.allowed is False


@pytest.mark.asyncio
async def test_check_quota_anonymous_redis_error_fails_open():
    with patch("app.services.quota.get_redis", side_effect=RuntimeError("redis down")):
        status = await check_quota(clerk_id=None, anonymous_id="dev-x", ip="6.6.6.6")
    assert status.allowed is True


# ── consume_quota — authenticated ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_consume_quota_authenticated_increments():
    user = _make_user(free_analyses_used=0)
    factory, session = _mock_session_factory(user)
    with patch("app.services.quota.get_session_factory", factory):
        await consume_quota(clerk_id="user_abc", anonymous_id=None, ip="1.2.3.4")
    assert user.free_analyses_used == 1
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_consume_quota_authenticated_paid_tier_not_incremented():
    user = _make_user(free_analyses_used=0, tier=SubscriptionTier.pro)
    factory, session = _mock_session_factory(user)
    with patch("app.services.quota.get_session_factory", factory):
        await consume_quota(clerk_id="user_abc", anonymous_id=None, ip="1.2.3.4")
    assert user.free_analyses_used == 0
    session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_consume_quota_authenticated_user_not_found_falls_back_to_anonymous(fake_redis):
    factory, _ = _mock_session_factory(None)
    with patch("app.services.quota.get_session_factory", factory):
        await consume_quota(clerk_id="ghost_user", anonymous_id="dev-9", ip="7.7.7.7")
    ip_count = await fake_redis.get("quota:lifetime:ip:7.7.7.7")
    device_count = await fake_redis.get("quota:lifetime:device:dev-9")
    assert ip_count == "1"
    assert device_count == "1"


@pytest.mark.asyncio
async def test_consume_quota_authenticated_db_error_falls_back_to_anonymous(fake_redis):
    def _raise(*a, **kw):
        raise RuntimeError("db down")

    with patch("app.services.quota.get_session_factory", _raise):
        await consume_quota(clerk_id="user_abc", anonymous_id="dev-10", ip="8.8.8.8")
    ip_count = await fake_redis.get("quota:lifetime:ip:8.8.8.8")
    assert ip_count == "1"


# ── consume_quota — anonymous ──────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_consume_quota_anonymous_increments_both_signals(fake_redis):
    await consume_quota(clerk_id=None, anonymous_id="dev-11", ip="9.1.1.1")
    assert await fake_redis.get("quota:lifetime:ip:9.1.1.1") == "1"
    assert await fake_redis.get("quota:lifetime:device:dev-11") == "1"


@pytest.mark.asyncio
async def test_consume_quota_anonymous_no_device_id_only_increments_ip(fake_redis):
    await consume_quota(clerk_id=None, anonymous_id=None, ip="9.2.2.2")
    assert await fake_redis.get("quota:lifetime:ip:9.2.2.2") == "1"


@pytest.mark.asyncio
async def test_consume_quota_anonymous_sets_ttl(fake_redis):
    await consume_quota(clerk_id=None, anonymous_id="dev-12", ip="9.3.3.3")
    ttl = await fake_redis.ttl("quota:lifetime:ip:9.3.3.3")
    assert 0 < ttl <= TTL_LIFETIME_QUOTA


@pytest.mark.asyncio
async def test_consume_quota_anonymous_cumulative_reaches_limit(fake_redis):
    for _ in range(FREE_LIFETIME_LIMIT):
        await consume_quota(clerk_id=None, anonymous_id="dev-13", ip="9.4.4.4")
    status = await check_quota(clerk_id=None, anonymous_id="dev-13", ip="9.4.4.4")
    assert status.allowed is False
    assert status.used == FREE_LIFETIME_LIMIT


@pytest.mark.asyncio
async def test_consume_quota_redis_error_never_raises():
    with patch("app.services.quota.get_redis", side_effect=RuntimeError("redis down")):
        await consume_quota(clerk_id=None, anonymous_id="dev-x", ip="9.5.5.5")  # must not raise


# ── Different users/IPs are isolated ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_anonymous_quota_isolated_per_ip(fake_redis):
    for _ in range(FREE_LIFETIME_LIMIT):
        await consume_quota(clerk_id=None, anonymous_id=None, ip="10.0.0.1")
    status_a = await check_quota(clerk_id=None, anonymous_id=None, ip="10.0.0.1")
    status_b = await check_quota(clerk_id=None, anonymous_id=None, ip="10.0.0.2")
    assert status_a.allowed is False
    assert status_b.allowed is True
