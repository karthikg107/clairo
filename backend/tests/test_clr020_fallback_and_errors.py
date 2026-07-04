"""
Tests for CLR-020 — Claude API fallback and error handling.

All Anthropic API calls are mocked. Redis (cache + circuit breaker + error
rate) is backed by fakeredis.
"""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import anthropic
import fakeredis.aioredis
import pytest

import app.core.circuit_breaker as cb_module
from app.services.analysis import (
    AnalysisServiceError,
    analyse_document,
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


def _bad_json_response(text: str = "not json") -> MagicMock:
    content = MagicMock()
    content.text = text
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
            yield mock_client


COMMON_ARGS = {
    "verified_text": "Rent is $1,500 per month.",
    "doc_language": "en",
    "country": "US",
    "output_language": "en",
    "document_type": "rental",
}


# ── Timeout / retry-once (CLR-020) ────────────────────────────────────────────

@pytest.mark.asyncio
async def test_timeout_then_success_retries_once(mock_anthropic):
    mock_anthropic.messages.create = AsyncMock(
        side_effect=[
            anthropic.APITimeoutError(request=MagicMock()),
            _mock_claude_response(VALID_RESPONSE),
        ]
    )

    result = await analyse_document(**COMMON_ARGS)

    assert mock_anthropic.messages.create.call_count == 2
    assert result.document_type == "rental"


@pytest.mark.asyncio
async def test_timeout_twice_raises_clear_error(mock_anthropic):
    mock_anthropic.messages.create = AsyncMock(
        side_effect=anthropic.APITimeoutError(request=MagicMock())
    )

    with pytest.raises(AnalysisServiceError):
        await analyse_document(**COMMON_ARGS)

    # Exactly one retry — two calls total, not more.
    assert mock_anthropic.messages.create.call_count == 2


@pytest.mark.asyncio
async def test_timeout_calls_include_30s_timeout(mock_anthropic):
    mock_anthropic.messages.create = AsyncMock(return_value=_mock_claude_response(VALID_RESPONSE))

    await analyse_document(**COMMON_ARGS)

    _, kwargs = mock_anthropic.messages.create.call_args
    assert kwargs["timeout"] == 30.0


# ── API unavailable (CLR-020) ─────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_connection_error_raises_clear_error_after_retry(mock_anthropic):
    mock_anthropic.messages.create = AsyncMock(
        side_effect=anthropic.APIConnectionError(request=MagicMock())
    )

    with pytest.raises(AnalysisServiceError, match="unavailable"):
        await analyse_document(**COMMON_ARGS)

    assert mock_anthropic.messages.create.call_count == 2


@pytest.mark.asyncio
async def test_internal_server_error_is_retried(mock_anthropic):
    error = anthropic.InternalServerError(
        message="boom", response=MagicMock(status_code=500), body=None
    )
    mock_anthropic.messages.create = AsyncMock(
        side_effect=[error, _mock_claude_response(VALID_RESPONSE)]
    )

    result = await analyse_document(**COMMON_ARGS)

    assert mock_anthropic.messages.create.call_count == 2
    assert result.document_type == "rental"


@pytest.mark.asyncio
async def test_unavailable_confirms_verified_text_not_stored(mock_anthropic, fake_redis_store):
    """SECURITY: on failure, the sentinel document text must never reach Redis."""
    sentinel = "SENTINEL_SHOULD_NEVER_BE_CACHED"
    mock_anthropic.messages.create = AsyncMock(
        side_effect=anthropic.APITimeoutError(request=MagicMock())
    )

    with pytest.raises(AnalysisServiceError):
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


# ── Malformed JSON: one correction retry (CLR-020) ────────────────────────────

@pytest.mark.asyncio
async def test_malformed_json_then_valid_retries_once(mock_anthropic):
    mock_anthropic.messages.create = AsyncMock(
        side_effect=[_bad_json_response(), _mock_claude_response(VALID_RESPONSE)]
    )

    result = await analyse_document(**COMMON_ARGS)

    assert mock_anthropic.messages.create.call_count == 2
    assert result.document_type == "rental"


@pytest.mark.asyncio
async def test_correction_retry_prompt_includes_original_and_correction_note(mock_anthropic):
    captured = []

    async def _create(**kwargs):
        captured.append(kwargs)
        if len(captured) == 1:
            return _bad_json_response()
        return _mock_claude_response(VALID_RESPONSE)

    mock_anthropic.messages.create = _create

    await analyse_document(**COMMON_ARGS)

    assert len(captured) == 2
    second_message = captured[1]["messages"][0]["content"]
    assert "DOCUMENT TEXT" in second_message  # original content retained
    assert "not valid JSON" in second_message  # correction note appended


@pytest.mark.asyncio
async def test_malformed_json_twice_raises_value_error(mock_anthropic):
    mock_anthropic.messages.create = AsyncMock(return_value=_bad_json_response())

    with pytest.raises(ValueError, match="non-JSON"):
        await analyse_document(**COMMON_ARGS)

    # One correction retry — two calls total, not more.
    assert mock_anthropic.messages.create.call_count == 2


# ── Circuit breaker (CLR-020) ─────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_breaker_opens_after_five_failures_in_window(mock_anthropic, fake_redis_store):
    mock_anthropic.messages.create = AsyncMock(
        side_effect=anthropic.APITimeoutError(request=MagicMock())
    )

    for _ in range(5):
        with pytest.raises(AnalysisServiceError):
            await analyse_document(**COMMON_ARGS)

    assert await cb_module.is_open() is True


@pytest.mark.asyncio
async def test_breaker_open_blocks_call_without_hitting_claude(mock_anthropic, fake_redis_store):
    await fake_redis_store.set(f"{cb_module.PREFIX_BREAKER}open", "1", ex=60)
    mock_anthropic.messages.create = AsyncMock(return_value=_mock_claude_response(VALID_RESPONSE))

    with pytest.raises(AnalysisServiceError, match="paused"):
        await analyse_document(**COMMON_ARGS)

    mock_anthropic.messages.create.assert_not_called()


@pytest.mark.asyncio
async def test_breaker_does_not_open_before_threshold(mock_anthropic, fake_redis_store):
    mock_anthropic.messages.create = AsyncMock(
        side_effect=anthropic.APITimeoutError(request=MagicMock())
    )

    for _ in range(4):
        with pytest.raises(AnalysisServiceError):
            await analyse_document(**COMMON_ARGS)

    assert await cb_module.is_open() is False


@pytest.mark.asyncio
async def test_breaker_check_fails_open_on_redis_error():
    with patch("app.core.redis.get_redis", side_effect=RuntimeError("redis down")):
        assert await cb_module.is_open() is False


@pytest.mark.asyncio
async def test_record_failure_fails_open_on_redis_error():
    with patch("app.core.redis.get_redis", side_effect=RuntimeError("redis down")):
        # Must not raise.
        await cb_module.record_failure()


# ── Sentry error-rate alert (CLR-020) ─────────────────────────────────────────

@pytest.mark.asyncio
async def test_sentry_alert_fires_above_one_percent_error_rate(fake_redis_store):
    with patch("app.core.circuit_breaker._sentry_capture") as mock_capture:
        # 19 successes, then 1 failure -> 1/20 = 5% > 1%, min samples reached at 20.
        for _ in range(19):
            await cb_module.record_outcome_for_error_rate(is_error=False)
        await cb_module.record_outcome_for_error_rate(is_error=True)

    mock_capture.assert_called_once()
    msg = mock_capture.call_args.args[0]
    assert "error rate" in msg.lower()


@pytest.mark.asyncio
async def test_no_alert_below_min_sample_size(fake_redis_store):
    with patch("app.core.circuit_breaker._sentry_capture") as mock_capture:
        # Only 5 samples, all errors -> 100% error rate, but below min sample size.
        for _ in range(5):
            await cb_module.record_outcome_for_error_rate(is_error=True)

    # No ERROR-RATE alert below the minimum sample size. (The separate
    # CLR-056 consecutive-errors alert legitimately fires here — 5 errors
    # in a row — so filter to rate alerts only.)
    rate_alerts = [c for c in mock_capture.call_args_list if "error rate" in c.args[0]]
    assert rate_alerts == []


@pytest.mark.asyncio
async def test_no_alert_when_error_rate_at_or_below_threshold(fake_redis_store):
    with patch("app.core.circuit_breaker._sentry_capture") as mock_capture:
        # 100 successes -> 0% error rate, well past min sample size.
        for _ in range(100):
            await cb_module.record_outcome_for_error_rate(is_error=False)

    mock_capture.assert_not_called()


@pytest.mark.asyncio
async def test_error_rate_tracking_fails_open_on_redis_error():
    with patch("app.core.redis.get_redis", side_effect=RuntimeError("redis down")):
        # Must not raise.
        await cb_module.record_outcome_for_error_rate(is_error=True)


@pytest.mark.asyncio
async def test_successful_analysis_records_non_error_outcome(mock_anthropic, fake_redis_store):
    mock_anthropic.messages.create = AsyncMock(return_value=_mock_claude_response(VALID_RESPONSE))

    with patch(
        "app.services.analysis.circuit_breaker.record_outcome_for_error_rate",
        new_callable=AsyncMock,
    ) as mock_record:
        await analyse_document(**COMMON_ARGS)

    mock_record.assert_awaited_once_with(is_error=False)


@pytest.mark.asyncio
async def test_failed_analysis_records_error_outcome_and_breaker_failure(mock_anthropic):
    mock_anthropic.messages.create = AsyncMock(
        side_effect=anthropic.APITimeoutError(request=MagicMock())
    )

    with patch(
        "app.services.analysis.circuit_breaker.record_outcome_for_error_rate",
        new_callable=AsyncMock,
    ) as mock_rate:
        with patch(
            "app.services.analysis.circuit_breaker.record_failure", new_callable=AsyncMock
        ) as mock_fail:
            with pytest.raises(AnalysisServiceError):
                await analyse_document(**COMMON_ARGS)

    mock_rate.assert_awaited_once_with(is_error=True)
    mock_fail.assert_awaited_once()


# ── Cache hit bypasses breaker/Claude entirely ────────────────────────────────

@pytest.mark.asyncio
async def test_cache_hit_does_not_touch_claude_or_breaker(mock_anthropic, fake_redis_store):
    import app.core.redis as redis_module
    from app.services.analysis import hash_verified_text

    text_hash = hash_verified_text(COMMON_ARGS["verified_text"])
    await redis_module.cache_analysis_result(text_hash, "en", "US", VALID_RESPONSE)
    await fake_redis_store.set(f"{cb_module.PREFIX_BREAKER}open", "1", ex=60)

    result = await analyse_document(**COMMON_ARGS)

    assert result.cache_hit is True
    mock_anthropic.messages.create.assert_not_called()


# ── Endpoint: error mapping (CLR-020) ─────────────────────────────────────────

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
async def test_endpoint_maps_service_error_to_503(client):
    with patch(
        "app.api.v1.endpoints.analyse.analyse_document",
        new_callable=AsyncMock,
        side_effect=AnalysisServiceError("Analysis service is temporarily unavailable."),
    ):
        r = await client.post("/api/v1/analyse", json=VALID_REQUEST)

    assert r.status_code == 503
    assert r.json()["detail"]["error"] == "analysis_unavailable"


@pytest.mark.asyncio
async def test_endpoint_maps_value_error_to_422(client):
    with patch(
        "app.api.v1.endpoints.analyse.analyse_document",
        new_callable=AsyncMock,
        side_effect=ValueError("Claude returned non-JSON response after correction retry"),
    ):
        r = await client.post("/api/v1/analyse", json=VALID_REQUEST)

    assert r.status_code == 422
    assert r.json()["detail"]["error"] == "analysis_failed"


@pytest.mark.asyncio
async def test_del_verified_text_present_on_service_error_path():
    """CLR-032/CLR-020: verified_text must still be purged when analysis is unavailable."""
    import inspect

    from app.api.v1.endpoints.analyse import analyse_endpoint

    source = inspect.getsource(analyse_endpoint)
    finally_idx = source.index("finally:")
    del_idx = source.index("del verified_text")
    assert del_idx > finally_idx
