"""
CLR-030 — Rate limiting tests.

Tests:
- Anonymous upload: 3/hr limit enforced
- Authenticated upload: 20/hr limit enforced
- Auth endpoint: 10/hr per IP
- Sentry alert fires at 50 req/hr threshold
- Daily analysis quota (existing check_rate_limit)
- Fail-open on Redis error
"""
import pytest
import fakeredis.aioredis
from unittest.mock import AsyncMock, patch

from app.core.rate_limit import (
    RateLimitTier,
    check_endpoint_rate_limit,
    check_rate_limit,
    _SENTRY_ALERT_THRESHOLD,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def fake_redis():
    return fakeredis.aioredis.FakeRedis()


@pytest.fixture(autouse=True)
def patch_get_redis(fake_redis):
    """Replace get_redis() with fakeredis for all tests in this module."""
    with patch("app.core.rate_limit.get_redis", new=AsyncMock(return_value=fake_redis)):
        yield fake_redis


# ── Hourly endpoint limits ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_upload_anonymous_allows_20_per_hour():
    for i in range(20):
        result = await check_endpoint_rate_limit("1.2.3.4", "upload", authenticated=False)
        assert result.allowed, f"Request {i+1} should be allowed"
        assert result.limit == 20


@pytest.mark.asyncio
async def test_upload_anonymous_blocks_21st():
    for _ in range(20):
        await check_endpoint_rate_limit("1.2.3.5", "upload", authenticated=False)

    result = await check_endpoint_rate_limit("1.2.3.5", "upload", authenticated=False)
    assert not result.allowed
    assert result.remaining == 0


@pytest.mark.asyncio
async def test_upload_authenticated_allows_60_per_hour():
    for i in range(60):
        result = await check_endpoint_rate_limit("user_abc", "upload", authenticated=True)
        assert result.allowed, f"Request {i+1} should be allowed (limit=60)"
        assert result.limit == 60


@pytest.mark.asyncio
async def test_upload_authenticated_blocks_61st():
    for _ in range(60):
        await check_endpoint_rate_limit("user_xyz", "upload", authenticated=True)

    result = await check_endpoint_rate_limit("user_xyz", "upload", authenticated=True)
    assert not result.allowed
    assert result.remaining == 0


@pytest.mark.asyncio
async def test_auth_endpoint_limit_10_per_ip():
    for i in range(10):
        result = await check_endpoint_rate_limit("5.6.7.8", "auth", authenticated=False)
        assert result.allowed, f"Auth request {i+1} should be allowed"
        assert result.limit == 10


@pytest.mark.asyncio
async def test_auth_endpoint_blocks_11th():
    for _ in range(10):
        await check_endpoint_rate_limit("5.6.7.9", "auth", authenticated=False)

    result = await check_endpoint_rate_limit("5.6.7.9", "auth", authenticated=False)
    assert not result.allowed


@pytest.mark.asyncio
async def test_different_identifiers_have_separate_buckets():
    for _ in range(20):
        await check_endpoint_rate_limit("ip_a", "upload", authenticated=False)

    # ip_a is at limit but ip_b should still be allowed
    result_a = await check_endpoint_rate_limit("ip_a", "upload", authenticated=False)
    result_b = await check_endpoint_rate_limit("ip_b", "upload", authenticated=False)
    assert not result_a.allowed
    assert result_b.allowed


@pytest.mark.asyncio
async def test_remaining_decrements_correctly():
    r1 = await check_endpoint_rate_limit("ip_c", "upload", authenticated=False)
    assert r1.remaining == 19  # limit=20, count=1

    r2 = await check_endpoint_rate_limit("ip_c", "upload", authenticated=False)
    assert r2.remaining == 18  # count=2

    r3 = await check_endpoint_rate_limit("ip_c", "upload", authenticated=False)
    assert r3.remaining == 17  # count=3


# ── Sentry alert at 50/hr ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_sentry_alert_fires_at_threshold():
    sentry_calls = []

    def mock_sentry(msg, extra):
        sentry_calls.append(msg)

    with patch("app.core.rate_limit._sentry_capture", side_effect=mock_sentry):
        for _ in range(_SENTRY_ALERT_THRESHOLD):
            await check_endpoint_rate_limit("spammer", "upload", authenticated=True)

        # Next request is the (threshold + 1)th — should trigger alert
        await check_endpoint_rate_limit("spammer", "upload", authenticated=True)

    assert len(sentry_calls) == 1
    assert "spammer" in sentry_calls[0]


@pytest.mark.asyncio
async def test_sentry_alert_fires_only_once_per_window():
    """Alert fires on the (threshold+1)th request only, not on every subsequent one."""
    sentry_calls = []

    def mock_sentry(msg, extra):
        sentry_calls.append(msg)

    with patch("app.core.rate_limit._sentry_capture", side_effect=mock_sentry):
        for _ in range(_SENTRY_ALERT_THRESHOLD + 5):
            await check_endpoint_rate_limit("spammer2", "upload", authenticated=True)

    assert len(sentry_calls) == 1


# ── Analysis-flow bucket (ocr + classify + analyse) ──────────────────────────
# Regression guard: a single anonymous analysis run makes one call each to
# ocr, classify and analyse. The dedicated "analysis" bucket must comfortably
# allow the product's 2 free analyses (+ retries) — NOT block after one run
# the way the old shared 3/hr "default" bucket did.

@pytest.mark.asyncio
async def test_analysis_bucket_allows_many_anonymous_runs():
    # 45 anonymous calls = 15 full runs of (ocr+classify+analyse) — all allowed.
    for i in range(45):
        result = await check_endpoint_rate_limit("anon_flow_ip", "analysis", authenticated=False)
        assert result.allowed, f"analysis call {i+1} should be allowed"
        assert result.limit == 45


def test_flow_endpoints_map_to_analysis_bucket_not_default():
    from app.middleware.rate_limit import _endpoint_key

    assert _endpoint_key("/api/v1/ocr") == "analysis"
    assert _endpoint_key("/api/v1/classify") == "analysis"
    assert _endpoint_key("/api/v1/analyse") == "analysis"
    # history list must NOT fall into the analysis-flow bucket
    assert _endpoint_key("/api/v1/analyses") == "default"
    assert _endpoint_key("/api/v1/upload/validate") == "upload"


# ── Daily analysis quota ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_daily_quota_anonymous():
    for i in range(3):
        result = await check_rate_limit("anon_ip_1", RateLimitTier.anonymous)
        assert result.allowed

    result = await check_rate_limit("anon_ip_1", RateLimitTier.anonymous)
    assert not result.allowed
    assert result.limit == 3


@pytest.mark.asyncio
async def test_daily_quota_pro():
    for i in range(100):
        result = await check_rate_limit("pro_user_1", RateLimitTier.pro)
        assert result.allowed

    result = await check_rate_limit("pro_user_1", RateLimitTier.pro)
    assert not result.allowed
    assert result.limit == 100


# ── Fail-open on Redis error ───────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_endpoint_rate_limit_fail_open_on_redis_error():
    """If Redis is unavailable, requests should be ALLOWED (fail-open)."""
    # Raise directly from _redis_incr_window to avoid coroutine-leak warnings
    with patch("app.core.rate_limit._redis_incr_window", side_effect=Exception("Redis connection refused")):
        result = await check_endpoint_rate_limit("some_ip", "upload", authenticated=False)

    assert result.allowed  # fail-open — never block on Redis error


@pytest.mark.asyncio
async def test_daily_quota_fail_open_on_redis_error():
    with patch("app.core.rate_limit._redis_incr_window", side_effect=Exception("Redis timeout")):
        result = await check_rate_limit("some_user", RateLimitTier.free)

    assert result.allowed
