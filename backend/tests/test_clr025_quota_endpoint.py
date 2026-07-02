"""
CLR-025 — Endpoint-level tests: GET /api/v1/quota and quota enforcement
inside POST /api/v1/analyse.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import fakeredis.aioredis
import pytest

from app.services.analysis import AnalysisResult
from app.services.quota import FREE_LIFETIME_LIMIT

VALID_RESPONSE = {
    "document_type": "rental",
    "summary": "A standard lease agreement.",
    "clauses": [],
    "protective_clause_count": 0,
    "review_clause_count": 0,
}

VALID_REQUEST = {
    "verified_text": "This lease agreement is between landlord and tenant. Rent is due monthly.",
    "doc_language": "en",
    "country": "US",
    "output_language": "en",
    "document_type": "rental",
}


@pytest.fixture
def fake_redis():
    return fakeredis.aioredis.FakeRedis(decode_responses=True)


@pytest.fixture(autouse=True)
def patch_redis(fake_redis):
    with patch("app.services.quota.get_redis", new=AsyncMock(return_value=fake_redis)):
        yield fake_redis


@pytest.fixture
async def client():
    from httpx import ASGITransport, AsyncClient

    import app.middleware.rate_limit as rl_module
    from app.core.rate_limit import RateLimitResult

    async def _mock_rate(*args, **kwargs):
        return RateLimitResult(allowed=True, limit=100, remaining=99, reset_in_seconds=3600)

    with patch.object(rl_module, "check_rate_limit", side_effect=_mock_rate):
        with patch.object(rl_module, "check_endpoint_rate_limit", side_effect=_mock_rate):
            from app.main import app
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://localhost") as c:
                yield c


# ── GET /api/v1/quota ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_quota_endpoint_anonymous_fresh(client):
    r = await client.get("/api/v1/quota")
    assert r.status_code == 200
    body = r.json()
    assert body["allowed"] is True
    assert body["is_free_tier"] is True
    assert body["used"] == 0
    assert body["remaining"] == FREE_LIFETIME_LIMIT


@pytest.mark.asyncio
async def test_quota_endpoint_anonymous_exhausted_by_device_id(client, fake_redis):
    await fake_redis.set("quota:lifetime:device:dev-abc", FREE_LIFETIME_LIMIT)
    r = await client.get("/api/v1/quota", headers={"X-Anonymous-Id": "dev-abc"})
    assert r.status_code == 200
    body = r.json()
    assert body["allowed"] is False
    assert body["remaining"] == 0


@pytest.mark.asyncio
async def test_quota_endpoint_anonymous_isolated_by_ip(client, fake_redis):
    await fake_redis.set("quota:lifetime:ip:127.0.0.1", FREE_LIFETIME_LIMIT)
    r = await client.get("/api/v1/quota", headers={"X-Anonymous-Id": "brand-new-device"})
    # httpx's ASGITransport reports request.client.host as 127.0.0.1.
    body = r.json()
    assert r.status_code == 200
    assert body["allowed"] is False  # IP signal alone is enough to block


# ── POST /api/v1/analyse — quota enforcement ──────────────────────────────────

@pytest.mark.asyncio
async def test_analyse_blocked_when_quota_exceeded_does_not_call_claude(client, fake_redis):
    await fake_redis.set("quota:lifetime:ip:127.0.0.1", FREE_LIFETIME_LIMIT)

    with patch(
        "app.api.v1.endpoints.analyse.analyse_document", new_callable=AsyncMock
    ) as mock_analyse:
        r = await client.post(
            "/api/v1/analyse", json=VALID_REQUEST, headers={"X-Anonymous-Id": "exhausted-dev"}
        )

    assert r.status_code == 402
    assert r.json()["detail"]["error"] == "quota_exceeded"
    mock_analyse.assert_not_called()


@pytest.mark.asyncio
async def test_analyse_allowed_consumes_quota_and_returns_quota_field(client, fake_redis):
    mock_result = AnalysisResult(
        raw=VALID_RESPONSE,
        document_type="rental",
        summary="Standard lease.",
        clauses=[],
        protective_clause_count=0,
        review_clause_count=0,
        cache_hit=False,
    )

    with patch(
        "app.api.v1.endpoints.analyse.analyse_document",
        new_callable=AsyncMock,
        return_value=mock_result,
    ):
        r = await client.post(
            "/api/v1/analyse", json=VALID_REQUEST, headers={"X-Anonymous-Id": "fresh-dev-1"}
        )

    assert r.status_code == 200
    body = r.json()
    assert body["quota"]["used"] == 1
    assert body["quota"]["remaining"] == FREE_LIFETIME_LIMIT - 1

    # Quota was actually persisted, not just reflected in the response.
    assert await fake_redis.get("quota:lifetime:device:fresh-dev-1") == "1"


@pytest.mark.asyncio
async def test_analyse_second_call_after_limit_is_blocked(client, fake_redis):
    mock_result = AnalysisResult(
        raw=VALID_RESPONSE,
        document_type="rental",
        summary="Standard lease.",
        clauses=[],
        protective_clause_count=0,
        review_clause_count=0,
        cache_hit=False,
    )

    with patch(
        "app.api.v1.endpoints.analyse.analyse_document",
        new_callable=AsyncMock,
        return_value=mock_result,
    ) as mock_analyse:
        headers = {"X-Anonymous-Id": "two-strikes-dev"}
        for _ in range(FREE_LIFETIME_LIMIT):
            r = await client.post("/api/v1/analyse", json=VALID_REQUEST, headers=headers)
            assert r.status_code == 200

        r = await client.post("/api/v1/analyse", json=VALID_REQUEST, headers=headers)
        assert r.status_code == 402
        assert mock_analyse.call_count == FREE_LIFETIME_LIMIT  # third call never reached Claude


@pytest.mark.asyncio
async def test_analyse_quota_not_consumed_on_service_error(client, fake_redis):
    from app.services.analysis import AnalysisServiceError

    with patch(
        "app.api.v1.endpoints.analyse.analyse_document",
        new_callable=AsyncMock,
        side_effect=AnalysisServiceError("unavailable"),
    ):
        r = await client.post(
            "/api/v1/analyse", json=VALID_REQUEST, headers={"X-Anonymous-Id": "unlucky-dev"}
        )

    assert r.status_code == 503
    assert await fake_redis.get("quota:lifetime:device:unlucky-dev") is None


@pytest.mark.asyncio
async def test_analyse_cache_hit_still_consumes_quota(client, fake_redis):
    mock_result = AnalysisResult(
        raw=VALID_RESPONSE,
        document_type="rental",
        summary="Standard lease.",
        clauses=[],
        protective_clause_count=0,
        review_clause_count=0,
        cache_hit=True,
    )

    with patch(
        "app.api.v1.endpoints.analyse.analyse_document",
        new_callable=AsyncMock,
        return_value=mock_result,
    ):
        with patch(
            "app.api.v1.endpoints.analyse._write_audit_log", new_callable=AsyncMock
        ):
            r = await client.post(
                "/api/v1/analyse", json=VALID_REQUEST, headers={"X-Anonymous-Id": "cache-hit-dev"}
            )

    assert r.status_code == 200
    assert await fake_redis.get("quota:lifetime:device:cache-hit-dev") == "1"
