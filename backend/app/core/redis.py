"""
Async Redis client.

SECURITY:
- Redis NEVER stores document content — only structured JSON (analysis results)
  and rate-limit counters.
- Cache keys are prefixed and namespaced to prevent collisions.
- TTLs are enforced on every SET — no unbounded data accumulation.
"""
from __future__ import annotations

import json
from typing import Any

import redis.asyncio as aioredis

from app.core.logging import get_logger
from app.core.secrets import get_secret

logger = get_logger(__name__)

_redis_client: aioredis.Redis | None = None

# Key prefixes
PREFIX_ANALYSIS = "analysis:"      # analysis result cache
PREFIX_RATE     = "rl:"            # rate limit counters
PREFIX_SESSION  = "session:"       # user session metadata (tier, limits)

# TTLs (seconds)
TTL_ANALYSIS = 60 * 60 * 24 * 30  # 30 days (CLR-019) — analysis results
TTL_RATE_WINDOW = 60               # 1 min sliding window for rate limits
TTL_SESSION = 60 * 60 * 2         # 2 h — session metadata


def _get_redis_url() -> str:
    secret = get_secret("clairo/redis")
    url = secret.get("url", "")
    if not url:
        raise RuntimeError("Redis URL not found in secrets")
    return url


async def get_redis() -> aioredis.Redis:
    """Return (or create) the shared async Redis client."""
    global _redis_client
    if _redis_client is None:
        _redis_client = aioredis.from_url(
            _get_redis_url(),
            encoding="utf-8",
            decode_responses=True,
            socket_connect_timeout=3,
            socket_timeout=3,
            retry_on_timeout=True,
        )
    return _redis_client


async def close_redis() -> None:
    global _redis_client
    if _redis_client is not None:
        await _redis_client.aclose()
        _redis_client = None


async def redis_ping() -> bool:
    """Health check — returns True if Redis is reachable."""
    try:
        client = await get_redis()
        return await client.ping()
    except Exception as exc:
        logger.warning("redis.ping_failed", error=str(exc))
        return False


# ── Cache helpers ─────────────────────────────────────────────────────────────

async def cache_set(key: str, value: Any, ttl: int) -> None:
    """
    Store a JSON-serialisable value with a mandatory TTL.

    SECURITY: callers must never pass document content as value.
    Only structured JSON (analysis results, session metadata) is permitted.
    """
    client = await get_redis()
    await client.set(key, json.dumps(value), ex=ttl)


async def cache_get(key: str) -> Any | None:
    """Return decoded value or None if missing/expired."""
    client = await get_redis()
    raw = await client.get(key)
    return json.loads(raw) if raw is not None else None


async def cache_delete(key: str) -> None:
    client = await get_redis()
    await client.delete(key)


# ── Analysis cache ────────────────────────────────────────────────────────────

async def cache_analysis(analysis_id: str, result: dict[str, Any]) -> None:
    """Cache an analysis result_json. NEVER pass document content here."""
    await cache_set(f"{PREFIX_ANALYSIS}{analysis_id}", result, TTL_ANALYSIS)


async def get_cached_analysis(analysis_id: str) -> dict[str, Any] | None:
    return await cache_get(f"{PREFIX_ANALYSIS}{analysis_id}")


async def invalidate_analysis(analysis_id: str) -> None:
    await cache_delete(f"{PREFIX_ANALYSIS}{analysis_id}")


# ── Content-hash analysis cache (CLR-019) ─────────────────────────────────────
# Caches analysis results for common contract templates, keyed by a SHA-256
# hash of the user-verified document text (never the text itself).

def analysis_cache_key(text_hash: str, output_language: str, country: str) -> str:
    return f"{PREFIX_ANALYSIS}{text_hash}:{output_language}:{country}"


async def cache_analysis_result(
    text_hash: str, output_language: str, country: str, result: dict[str, Any]
) -> None:
    """Cache a validated analysis JSON result. NEVER pass document content here."""
    await cache_set(
        analysis_cache_key(text_hash, output_language, country), result, TTL_ANALYSIS
    )


async def get_cached_analysis_result(
    text_hash: str, output_language: str, country: str
) -> dict[str, Any] | None:
    return await cache_get(analysis_cache_key(text_hash, output_language, country))


async def flush_analysis_cache(text_hash: str, output_language: str, country: str) -> None:
    """Manual flush — used when legal review requires an updated analysis."""
    await cache_delete(analysis_cache_key(text_hash, output_language, country))


# ── Session metadata cache ────────────────────────────────────────────────────

async def cache_user_session(user_id: str, data: dict[str, Any]) -> None:
    """Cache user metadata (tier, rate limit info). No PII beyond user_id key."""
    await cache_set(f"{PREFIX_SESSION}{user_id}", data, TTL_SESSION)


async def get_user_session(user_id: str) -> dict[str, Any] | None:
    return await cache_get(f"{PREFIX_SESSION}{user_id}")


async def invalidate_user_session(user_id: str) -> None:
    await cache_delete(f"{PREFIX_SESSION}{user_id}")
