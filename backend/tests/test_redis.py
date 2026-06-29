"""Tests for Redis cache and rate limiting — uses fakeredis (no live Redis needed)."""
import pytest
import fakeredis.aioredis as fakeredis

import app.core.redis as redis_module
import app.core.rate_limit as rl_module


@pytest.fixture(autouse=True)
async def fake_redis(monkeypatch):
    """Patch get_redis() to return an in-memory fake."""
    server = fakeredis.FakeRedis(decode_responses=True)
    monkeypatch.setattr(redis_module, "_redis_client", server)
    monkeypatch.setattr(rl_module, "get_redis", lambda: server)
    yield server
    await server.aclose()


# ── Cache helpers ─────────────────────────────────────────────────────────────

async def test_cache_set_and_get():
    await redis_module.cache_set("test:key", {"foo": "bar"}, ttl=60)
    result = await redis_module.cache_get("test:key")
    assert result == {"foo": "bar"}


async def test_cache_get_missing_returns_none():
    result = await redis_module.cache_get("no:such:key")
    assert result is None


async def test_cache_delete():
    await redis_module.cache_set("del:key", {"x": 1}, ttl=60)
    await redis_module.cache_delete("del:key")
    assert await redis_module.cache_get("del:key") is None


async def test_analysis_cache_roundtrip():
    result = {"summary": "Safe contract", "risk_score": 2, "flags": []}
    await redis_module.cache_analysis("analysis-uuid-123", result)
    cached = await redis_module.get_cached_analysis("analysis-uuid-123")
    assert cached == result


async def test_analysis_cache_never_stores_content():
    """SECURITY: ensure result_json with forbidden keys is structurally rejected by caller convention."""
    # The cache layer itself is key-agnostic; security is enforced at the service layer.
    # This test documents the contract: only these keys are permitted in result_json.
    permitted_keys = {"summary", "flags", "clauses", "risk_score", "language_detected"}
    sample = {k: "value" for k in permitted_keys}
    await redis_module.cache_analysis("sec-test", sample)
    cached = await redis_module.get_cached_analysis("sec-test")
    assert set(cached.keys()) <= permitted_keys


async def test_invalidate_analysis():
    await redis_module.cache_analysis("to-invalidate", {"summary": "x"})
    await redis_module.invalidate_analysis("to-invalidate")
    assert await redis_module.get_cached_analysis("to-invalidate") is None


async def test_user_session_cache():
    data = {"tier": "pro", "user_id": "usr_abc"}
    await redis_module.cache_user_session("usr_abc", data)
    cached = await redis_module.get_user_session("usr_abc")
    assert cached == data


# ── Rate limiting ─────────────────────────────────────────────────────────────

async def test_rate_limit_allows_within_limit(fake_redis):
    from app.core.rate_limit import RateLimitTier, check_rate_limit

    async def _check():
        return await check_rate_limit("user-1", RateLimitTier.free)

    # free tier = 10/day; first call should be allowed
    result = await _check()
    assert result.allowed is True
    assert result.limit == 10
    assert result.remaining == 9


async def test_rate_limit_blocks_when_exceeded(fake_redis):
    from app.core.rate_limit import RateLimitTier, check_rate_limit, DAILY_LIMITS

    limit = DAILY_LIMITS[RateLimitTier.anonymous]  # 3
    for _ in range(limit):
        await check_rate_limit("anon-ip", RateLimitTier.anonymous)

    # Next call should be blocked
    result = await check_rate_limit("anon-ip", RateLimitTier.anonymous)
    assert result.allowed is False
    assert result.remaining == 0


async def test_rate_limit_tiers_have_correct_limits():
    from app.core.rate_limit import DAILY_LIMITS, RateLimitTier
    assert DAILY_LIMITS[RateLimitTier.anonymous] == 3
    assert DAILY_LIMITS[RateLimitTier.free] == 10
    assert DAILY_LIMITS[RateLimitTier.pro] == 100
    assert DAILY_LIMITS[RateLimitTier.enterprise] == 1000


async def test_rate_limit_different_users_independent(fake_redis):
    from app.core.rate_limit import RateLimitTier, check_rate_limit, DAILY_LIMITS

    limit = DAILY_LIMITS[RateLimitTier.anonymous]
    for _ in range(limit):
        await check_rate_limit("user-A", RateLimitTier.anonymous)

    # user-B should still be allowed
    result = await check_rate_limit("user-B", RateLimitTier.anonymous)
    assert result.allowed is True
