"""
Tests for CLR-019 — analysis caching for common contract templates.

All Anthropic API calls are mocked. Redis is backed by fakeredis.
"""
from __future__ import annotations

import hashlib
import json
from unittest.mock import AsyncMock, MagicMock, patch

import fakeredis.aioredis
import pytest

import app.core.redis as redis_module
from app.services.analysis import (
    AnalysisResult,
    analyse_document,
    hash_verified_text,
)

VALID_RESPONSE = {
    "document_type": "rental",
    "summary": "A standard lease agreement.",
    "clauses": [
        {
            "id": "c1",
            "title": "Monthly rent",
            "original_text": "Rent is $1,500 per month.",
            "explanation": "You pay $1,500 each month.",
            "frequency_pct": 95,
            "is_protective": False,
            "flag_level": "none",
            "numbers": [{"value": "$1,500", "context": "monthly rent amount"}],
        }
    ],
    "protective_clause_count": 0,
    "review_clause_count": 0,
}


def _mock_claude_response(payload: dict) -> MagicMock:
    content = MagicMock()
    content.text = json.dumps(payload)
    msg = MagicMock()
    msg.content = [content]
    return msg


@pytest.fixture
def fake_redis_store():
    return fakeredis.aioredis.FakeRedis(decode_responses=True)


@pytest.fixture(autouse=True)
def patch_redis(fake_redis_store):
    with patch("app.core.redis.get_redis", new=AsyncMock(return_value=fake_redis_store)):
        yield fake_redis_store


@pytest.fixture
def mock_anthropic():
    with patch("app.services.analysis.anthropic.AsyncAnthropic") as mock_cls:
        with patch("app.services.analysis.get_secret", return_value={"api_key": "sk-test"}):
            mock_client = AsyncMock()
            mock_cls.return_value = mock_client
            mock_client.messages.create = AsyncMock(
                return_value=_mock_claude_response(VALID_RESPONSE)
            )
            yield mock_client


# ── hash_verified_text ─────────────────────────────────────────────────────────

class TestHashVerifiedText:
    def test_returns_sha256_hex_digest(self):
        result = hash_verified_text("Rent is $1,500 per month.")
        assert result == hashlib.sha256(b"Rent is $1,500 per month.").hexdigest()
        assert len(result) == 64

    def test_different_text_different_hash(self):
        assert hash_verified_text("a") != hash_verified_text("b")

    def test_same_text_same_hash(self):
        assert hash_verified_text("identical") == hash_verified_text("identical")


# ── Cache key format ──────────────────────────────────────────────────────────

class TestCacheKeyFormat:
    def test_key_format_matches_spec(self):
        key = redis_module.analysis_cache_key("abc123", "en", "US")
        assert key == "analysis:abc123:en:US"


# ── analyse_document cache behaviour ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_cache_miss_calls_claude_and_stores_result(mock_anthropic, fake_redis_store):
    result = await analyse_document(
        verified_text="Rent is $1,500 per month.",
        doc_language="en",
        country="US",
        output_language="en",
        document_type="rental",
    )

    assert mock_anthropic.messages.create.call_count == 1
    assert result.cache_hit is False

    text_hash = hash_verified_text("Rent is $1,500 per month.")
    cached = await redis_module.get_cached_analysis_result(text_hash, "en", "US")
    assert cached == VALID_RESPONSE


@pytest.mark.asyncio
async def test_cache_hit_skips_claude_call(mock_anthropic, fake_redis_store):
    text_hash = hash_verified_text("Rent is $1,500 per month.")
    await redis_module.cache_analysis_result(text_hash, "en", "US", VALID_RESPONSE)

    result = await analyse_document(
        verified_text="Rent is $1,500 per month.",
        doc_language="en",
        country="US",
        output_language="en",
        document_type="rental",
    )

    assert mock_anthropic.messages.create.call_count == 0
    assert result.cache_hit is True
    assert result.document_type == "rental"
    assert result.clauses == VALID_RESPONSE["clauses"]


@pytest.mark.asyncio
async def test_cache_key_scoped_by_output_language(mock_anthropic, fake_redis_store):
    """Same text, different output_language must NOT share a cache entry."""
    text = "Rent is $1,500 per month."
    text_hash = hash_verified_text(text)
    await redis_module.cache_analysis_result(text_hash, "en", "US", VALID_RESPONSE)

    result = await analyse_document(
        verified_text=text,
        doc_language="en",
        country="US",
        output_language="es",  # different output language -> miss
        document_type="rental",
    )

    assert mock_anthropic.messages.create.call_count == 1
    assert result.cache_hit is False


@pytest.mark.asyncio
async def test_cache_key_scoped_by_country(mock_anthropic, fake_redis_store):
    """Same text, different country must NOT share a cache entry."""
    text = "Rent is $1,500 per month."
    text_hash = hash_verified_text(text)
    await redis_module.cache_analysis_result(text_hash, "en", "US", VALID_RESPONSE)

    result = await analyse_document(
        verified_text=text,
        doc_language="en",
        country="GB",  # different country -> miss
        output_language="en",
        document_type="rental",
    )

    assert mock_anthropic.messages.create.call_count == 1
    assert result.cache_hit is False


@pytest.mark.asyncio
async def test_cache_never_stores_document_content(mock_anthropic, fake_redis_store):
    """SECURITY: only the analysis JSON is cached — never verified_text."""
    sentinel = "SENTINEL_DOCUMENT_TEXT_DO_NOT_CACHE"

    await analyse_document(
        verified_text=sentinel,
        doc_language="en",
        country="US",
        output_language="en",
        document_type="rental",
    )

    async for key in fake_redis_store.scan_iter("*"):
        value = await fake_redis_store.get(key)
        assert sentinel not in (value or "")


@pytest.mark.asyncio
async def test_cache_write_failure_does_not_break_analysis(mock_anthropic, fake_redis_store):
    """Fail open: if Redis errors on write, analysis still returns a result."""
    with patch(
        "app.services.analysis.cache_analysis_result",
        side_effect=RuntimeError("redis down"),
    ):
        result = await analyse_document(
            verified_text="Rent is $1,500 per month.",
            doc_language="en",
            country="US",
            output_language="en",
            document_type="rental",
        )

    assert result.cache_hit is False
    assert result.document_type == "rental"


@pytest.mark.asyncio
async def test_cache_read_failure_falls_back_to_claude(mock_anthropic, fake_redis_store):
    """Fail open: if Redis errors on read, we still call Claude rather than erroring."""
    with patch(
        "app.services.analysis.get_cached_analysis_result",
        side_effect=RuntimeError("redis down"),
    ):
        result = await analyse_document(
            verified_text="Rent is $1,500 per month.",
            doc_language="en",
            country="US",
            output_language="en",
            document_type="rental",
        )

    assert mock_anthropic.messages.create.call_count == 1
    assert result.cache_hit is False


@pytest.mark.asyncio
async def test_corrupt_cache_entry_falls_back_to_claude(mock_anthropic, fake_redis_store):
    """A cached entry that fails schema validation is treated as a miss."""
    text = "Rent is $1,500 per month."
    text_hash = hash_verified_text(text)
    await redis_module.cache_analysis_result(text_hash, "en", "US", {"junk": True})

    result = await analyse_document(
        verified_text=text,
        doc_language="en",
        country="US",
        output_language="en",
        document_type="rental",
    )

    assert mock_anthropic.messages.create.call_count == 1
    assert result.cache_hit is False


# ── Manual flush (CLR-019) ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_flush_analysis_cache_removes_entry(fake_redis_store):
    text_hash = hash_verified_text("Rent is $1,500 per month.")
    await redis_module.cache_analysis_result(text_hash, "en", "US", VALID_RESPONSE)
    assert await redis_module.get_cached_analysis_result(text_hash, "en", "US") is not None

    await redis_module.flush_analysis_cache(text_hash, "en", "US")

    assert await redis_module.get_cached_analysis_result(text_hash, "en", "US") is None


@pytest.mark.asyncio
async def test_flush_only_affects_matching_key(fake_redis_store):
    text_hash = hash_verified_text("Rent is $1,500 per month.")
    await redis_module.cache_analysis_result(text_hash, "en", "US", VALID_RESPONSE)
    await redis_module.cache_analysis_result(text_hash, "es", "US", VALID_RESPONSE)

    await redis_module.flush_analysis_cache(text_hash, "en", "US")

    assert await redis_module.get_cached_analysis_result(text_hash, "en", "US") is None
    assert await redis_module.get_cached_analysis_result(text_hash, "es", "US") is not None


# ── TTL ────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_analysis_cache_ttl_is_30_days():
    assert redis_module.TTL_ANALYSIS == 60 * 60 * 24 * 30


@pytest.mark.asyncio
async def test_cached_entry_has_ttl_set(mock_anthropic, fake_redis_store):
    await analyse_document(
        verified_text="Rent is $1,500 per month.",
        doc_language="en",
        country="US",
        output_language="en",
        document_type="rental",
    )
    text_hash = hash_verified_text("Rent is $1,500 per month.")
    key = redis_module.analysis_cache_key(text_hash, "en", "US")
    ttl = await fake_redis_store.ttl(key)
    assert 0 < ttl <= 60 * 60 * 24 * 30


# ── Endpoint: audit log on cache hit ──────────────────────────────────────────

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


VALID_REQUEST = {
    "verified_text": "This lease agreement is between landlord and tenant. Rent is due monthly.",
    "doc_language": "en",
    "country": "US",
    "output_language": "en",
    "document_type": "rental",
}


@pytest.mark.asyncio
async def test_endpoint_writes_audit_log_on_cache_hit(client):
    cache_hit_result = AnalysisResult(
        raw=VALID_RESPONSE,
        document_type="rental",
        summary="Standard lease.",
        clauses=VALID_RESPONSE["clauses"],
        protective_clause_count=0,
        review_clause_count=0,
        cache_hit=True,
    )

    with patch(
        "app.api.v1.endpoints.analyse.analyse_document",
        new_callable=AsyncMock,
        return_value=cache_hit_result,
    ):
        with patch(
            "app.api.v1.endpoints.analyse._write_audit_log", new_callable=AsyncMock
        ) as mock_audit:
            r = await client.post("/api/v1/analyse", json=VALID_REQUEST)

    assert r.status_code == 200
    mock_audit.assert_awaited_once()
    _, kwargs = mock_audit.call_args
    assert kwargs["action"] == "analysis_cache_hit"
    assert "verified_text" not in json.dumps(kwargs["metadata"])


@pytest.mark.asyncio
async def test_endpoint_skips_audit_log_on_cache_miss(client):
    miss_result = AnalysisResult(
        raw=VALID_RESPONSE,
        document_type="rental",
        summary="Standard lease.",
        clauses=VALID_RESPONSE["clauses"],
        protective_clause_count=0,
        review_clause_count=0,
        cache_hit=False,
    )

    with patch(
        "app.api.v1.endpoints.analyse.analyse_document",
        new_callable=AsyncMock,
        return_value=miss_result,
    ):
        with patch(
            "app.api.v1.endpoints.analyse._write_audit_log", new_callable=AsyncMock
        ) as mock_audit:
            r = await client.post("/api/v1/analyse", json=VALID_REQUEST)

    assert r.status_code == 200
    mock_audit.assert_not_awaited()


@pytest.mark.asyncio
async def test_flush_endpoint_calls_flush_and_audits(client):
    with patch(
        "app.api.v1.endpoints.analyse.flush_analysis_cache", new_callable=AsyncMock
    ) as mock_flush:
        with patch(
            "app.api.v1.endpoints.analyse._write_audit_log", new_callable=AsyncMock
        ) as mock_audit:
            r = await client.request(
                "DELETE",
                "/api/v1/analyse/cache",
                json={
                    "text_hash": "a" * 64,
                    "output_language": "en",
                    "country": "US",
                },
            )

    assert r.status_code == 204
    mock_flush.assert_awaited_once_with("a" * 64, "en", "US")
    mock_audit.assert_awaited_once()
    assert mock_audit.call_args.kwargs["action"] == "analysis_cache_flushed"


@pytest.mark.asyncio
async def test_flush_endpoint_rejects_bad_hash(client):
    r = await client.request(
        "DELETE",
        "/api/v1/analyse/cache",
        json={"text_hash": "not-a-hash", "output_language": "en", "country": "US"},
    )
    assert r.status_code == 422
