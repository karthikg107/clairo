"""
CLR-020 — Circuit breaker and error-rate alerting for the Claude analysis call.

- 5 analysis failures within a 1-minute window opens the breaker; while open,
  analyse_document() is paused for 60 seconds without calling Claude at all.
- Every analysis outcome (success/failure) feeds a rolling error-rate counter;
  a Sentry alert fires once the error rate exceeds 1% (with a minimum sample
  size, to avoid alerting on a handful of early requests).
- Backed by Redis so the breaker is shared across all API instances. Fails
  open on Redis errors — infra hiccups here must never block analysis.
"""
from __future__ import annotations

from app.core import redis as redis_core
from app.core.logging import get_logger

logger = get_logger(__name__)

PREFIX_BREAKER = "breaker:analysis:"
FAILURE_THRESHOLD = 5
FAILURE_WINDOW_SECONDS = 60
OPEN_DURATION_SECONDS = 60

PREFIX_ERROR_RATE = "errrate:analysis:"
ERROR_RATE_WINDOW_SECONDS = 60 * 5
ERROR_RATE_THRESHOLD = 0.01
ERROR_RATE_MIN_SAMPLES = 20


def _sentry_capture(msg: str, level: str, extra: dict) -> None:
    try:
        import sentry_sdk
        with sentry_sdk.new_scope() as scope:
            scope.set_extra("analysis_error_data", extra)
            sentry_sdk.capture_message(msg, level=level)
    except Exception:
        pass


async def is_open() -> bool:
    """True if the breaker is currently open (analyses should be paused)."""
    try:
        client = await redis_core.get_redis()
        return bool(await client.get(f"{PREFIX_BREAKER}open"))
    except Exception as exc:
        logger.warning("circuit_breaker.check_failed", error=str(exc))
        return False  # fail open — never block analysis due to Redis issues


async def record_failure() -> None:
    """Record an analysis failure; opens the breaker if the threshold is hit."""
    try:
        client = await redis_core.get_redis()
        key = f"{PREFIX_BREAKER}failures"
        count = await client.incr(key)
        if count == 1:
            await client.expire(key, FAILURE_WINDOW_SECONDS)

        if count >= FAILURE_THRESHOLD:
            await client.set(f"{PREFIX_BREAKER}open", "1", ex=OPEN_DURATION_SECONDS)
            await client.delete(key)
            logger.error("circuit_breaker.opened", failure_count=count)
            _sentry_capture(
                f"Claude API circuit breaker opened after {count} failures/min",
                level="error",
                extra={"failure_count": count},
            )
    except Exception as exc:
        logger.warning("circuit_breaker.record_failure_failed", error=str(exc))


async def record_outcome_for_error_rate(*, is_error: bool) -> None:
    """
    Track rolling error rate and fire a Sentry alert once it exceeds 1%
    (only once enough samples have accumulated, to avoid noisy early alerts).
    """
    try:
        client = await redis_core.get_redis()
        total_key = f"{PREFIX_ERROR_RATE}total"
        error_key = f"{PREFIX_ERROR_RATE}errors"

        total = await client.incr(total_key)
        if total == 1:
            await client.expire(total_key, ERROR_RATE_WINDOW_SECONDS)

        if is_error:
            errors = await client.incr(error_key)
            if errors == 1:
                await client.expire(error_key, ERROR_RATE_WINDOW_SECONDS)
        else:
            errors_raw = await client.get(error_key)
            errors = int(errors_raw) if errors_raw else 0

        if total >= ERROR_RATE_MIN_SAMPLES:
            rate = errors / total
            if rate > ERROR_RATE_THRESHOLD:
                logger.error("analysis.error_rate_alert", rate=rate, total=total, errors=errors)
                _sentry_capture(
                    f"Claude API error rate {rate:.2%} exceeds 1% threshold",
                    level="error",
                    extra={"total": total, "errors": errors, "rate": rate},
                )
    except Exception as exc:
        logger.warning("error_rate.record_failed", error=str(exc))
