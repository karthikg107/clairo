"""
CLR-056 — monitoring & alerting: Claude consecutive-error alert.

3 consecutive Claude errors fire a Sentry alert exactly once per streak;
any success resets the streak. (The windowed >1% error-rate alert and
the 50 req/hr abuse alert are covered by CLR-020/CLR-030 tests.)
"""
from __future__ import annotations

from unittest.mock import patch

import fakeredis.aioredis
import pytest

import app.core.circuit_breaker as cb
import app.core.redis as redis_core


@pytest.fixture
async def fake_redis():
    client = fakeredis.aioredis.FakeRedis(decode_responses=True)
    with patch.object(redis_core, "get_redis", return_value=client):
        yield client
    await client.flushall()


@pytest.mark.asyncio
async def test_three_consecutive_errors_fire_alert_once(fake_redis):
    with patch.object(cb, "_sentry_capture") as mock_sentry:
        await cb.record_outcome_for_error_rate(is_error=True)
        await cb.record_outcome_for_error_rate(is_error=True)
        assert mock_sentry.call_count == 0  # not yet

        await cb.record_outcome_for_error_rate(is_error=True)

    consecutive_alerts = [
        c for c in mock_sentry.call_args_list if "consecutive" in c.args[0]
    ]
    assert len(consecutive_alerts) == 1
    assert "3 consecutive errors" in consecutive_alerts[0].args[0]


@pytest.mark.asyncio
async def test_streak_does_not_realert_on_fourth_error(fake_redis):
    with patch.object(cb, "_sentry_capture") as mock_sentry:
        for _ in range(4):
            await cb.record_outcome_for_error_rate(is_error=True)

    consecutive_alerts = [
        c for c in mock_sentry.call_args_list if "consecutive" in c.args[0]
    ]
    assert len(consecutive_alerts) == 1  # once per streak, not per error


@pytest.mark.asyncio
async def test_success_resets_the_streak(fake_redis):
    with patch.object(cb, "_sentry_capture") as mock_sentry:
        await cb.record_outcome_for_error_rate(is_error=True)
        await cb.record_outcome_for_error_rate(is_error=True)
        await cb.record_outcome_for_error_rate(is_error=False)  # streak broken
        await cb.record_outcome_for_error_rate(is_error=True)
        await cb.record_outcome_for_error_rate(is_error=True)

    consecutive_alerts = [
        c for c in mock_sentry.call_args_list if "consecutive" in c.args[0]
    ]
    assert len(consecutive_alerts) == 0  # never reached 3 in a row


@pytest.mark.asyncio
async def test_new_streak_after_reset_alerts_again(fake_redis):
    with patch.object(cb, "_sentry_capture") as mock_sentry:
        for _ in range(3):
            await cb.record_outcome_for_error_rate(is_error=True)
        await cb.record_outcome_for_error_rate(is_error=False)
        for _ in range(3):
            await cb.record_outcome_for_error_rate(is_error=True)

    consecutive_alerts = [
        c for c in mock_sentry.call_args_list if "consecutive" in c.args[0]
    ]
    assert len(consecutive_alerts) == 2  # one per streak
