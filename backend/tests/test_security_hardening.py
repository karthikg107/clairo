"""
Security hardening tests.

Covers the measures added in the security-hardening pass. Auth/login items
(login rate limiting, lockout, refresh rotation, concurrent sessions) are
Clerk-owned and cannot be exercised here — see docs/clerk-security-config.md.
Expired/tampered JWT rejection is already covered by tests/test_jwt_auth.py
(test_expired_token_returns_401, test_invalid_signature_returns_401,
test_garbled_token_returns_401).
"""
from __future__ import annotations

from unittest.mock import patch
from urllib.parse import quote

import pytest

from app.middleware.hardening import (
    MAX_REQUEST_BYTES,
    SecurityGuardMiddleware,
    _first_suspicious,
)


# ── Suspicious-pattern firewall: unit level ───────────────────────────────────

@pytest.mark.parametrize(
    "payload,expected",
    [
        ("/api/v1/health?q=' OR 1=1", "sqli_or_1"),
        ("/api/v1/health?q=UNION SELECT password FROM users", "sqli_union"),
        ("/api/v1/x?q=1; DROP TABLE users", "sqli_drop"),
        ("/api/v1/x?q=<script>alert(1)</script>", "xss_script"),
        ("/api/v1/x?next=javascript:alert(1)", "xss_js_uri"),
        ("/api/v1/x?img=<iframe src=evil>", "xss_iframe"),
        ("/api/v1/x?f=../../etc/passwd", "path_traversal"),
    ],
)
def test_suspicious_patterns_detected(payload, expected):
    assert _first_suspicious(payload) == expected


@pytest.mark.parametrize(
    "safe",
    [
        "/api/v1/analyses?limit=50",
        "/de/pricing",
        "/api/v1/shared/1b671a64-40d5-491e-99b0-da01ff1f3341",
        "/dashboard?upgraded=true",
        "/api/v1/share-links/abc-123/revoke",
        "/en?redirect=/dashboard",
        "/api/v1/account/language-preferences",
    ],
)
def test_legitimate_paths_not_flagged(safe):
    # No false positives on normal UUIDs, locales, numeric limits, redirects.
    assert _first_suspicious(safe) is None


# ── Body-size cap (guard, unit level) ─────────────────────────────────────────

@pytest.mark.asyncio
async def test_oversized_request_rejected_by_guard():
    from starlette.requests import Request

    mw = SecurityGuardMiddleware(app=None)
    scope = {
        "type": "http",
        "method": "POST",
        "path": "/api/v1/upload/validate",
        "query_string": b"",
        "headers": [(b"content-length", str(MAX_REQUEST_BYTES + 1).encode())],
    }
    req = Request(scope)

    async def call_next(_req):  # pragma: no cover - must not be reached
        raise AssertionError("handler must not run for oversized body")

    resp = await mw.dispatch(req, call_next)
    assert resp.status_code == 413


# ── Full-app integration ──────────────────────────────────────────────────────

@pytest.fixture
async def client():
    from httpx import ASGITransport, AsyncClient

    import app.middleware.rate_limit as rl_module
    from app.core.rate_limit import RateLimitResult
    from app.db.session import get_db

    async def _mock_rate(*args, **kwargs):
        return RateLimitResult(allowed=True, limit=100, remaining=99, reset_in_seconds=3600)

    with patch.object(rl_module, "check_rate_limit", side_effect=_mock_rate):
        with patch.object(rl_module, "check_endpoint_rate_limit", side_effect=_mock_rate):
            from app.main import app

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://localhost") as c:
                yield c
            app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_sqli_in_query_string_blocked(client):
    r = await client.get("/api/v1/health?q=" + quote("' OR 1=1"))
    assert r.status_code == 400
    assert r.json() == {"error": "bad_request"}


@pytest.mark.asyncio
async def test_xss_in_query_string_blocked(client):
    r = await client.get("/api/v1/health?x=" + quote("<script>alert(1)</script>"))
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_path_traversal_blocked(client):
    r = await client.get("/api/v1/health?f=" + quote("../../etc/passwd"))
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_clean_request_passes_guard(client):
    r = await client.get("/api/v1/health")
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_disallowed_origin_on_post_rejected(client):
    # Origin check runs before auth, so this is 403 regardless of the token.
    r = await client.post(
        "/api/v1/share-links",
        json={"analysis_id": "1b671a64-40d5-491e-99b0-da01ff1f3341"},
        headers={"Origin": "https://evil.example.com"},
    )
    assert r.status_code == 403
    assert r.json() == {"error": "origin_not_allowed"}


@pytest.mark.asyncio
async def test_allowed_origin_on_post_passes_guard(client):
    # localhost:3000 is allowed — the guard lets it through (routing then
    # 404s the unknown path, but crucially NOT a 403 origin rejection).
    r = await client.post(
        "/api/v1/__nonexistent__",
        json={},
        headers={"Origin": "http://localhost:3000"},
    )
    assert r.status_code != 403


@pytest.mark.asyncio
async def test_no_origin_header_passes_guard(client):
    # Server-to-server / same-origin requests send no Origin — allowed.
    r = await client.post("/api/v1/__nonexistent__", json={})
    assert r.status_code != 403


@pytest.mark.asyncio
async def test_security_txt_served(client):
    r = await client.get("/.well-known/security.txt")
    assert r.status_code == 200
    assert "Contact:" in r.text
    assert "Expires:" in r.text


# ── SQL-injection in a JSON body is neutralised by validation/ORM ─────────────

@pytest.mark.asyncio
async def test_sqli_in_json_body_rejected_by_validation(client):
    # A SQLi string where a UUID is expected → pydantic 422, never reaches
    # the DB as raw SQL (all queries are parameterised ORM anyway).
    from app.db.session import get_db
    from app.main import app

    async def _fake_db():
        yield object()  # never used — validation fails before the handler runs

    app.dependency_overrides[get_db] = _fake_db
    try:
        r = await client.post(
            "/api/v1/share-links",
            json={"analysis_id": "'; DROP TABLE users;--"},
            headers={"X-Clerk-User-Id": "user_x"},
        )
    finally:
        app.dependency_overrides.pop(get_db, None)
    assert r.status_code == 422


# ── Upload rate limit enforced at the endpoint ────────────────────────────────

@pytest.mark.asyncio
async def test_upload_rate_limit_returns_429(client):
    from app.core.rate_limit import RateLimitResult

    blocked = RateLimitResult(allowed=False, limit=10, remaining=0, reset_in_seconds=1800)
    with patch(
        "app.api.v1.endpoints.upload.check_upload_rate_limit", return_value=blocked
    ):
        r = await client.post(
            "/api/v1/upload/validate",
            files={"file": ("x.pdf", b"%PDF-1.4 fake", "application/pdf")},
        )
    assert r.status_code == 429
    assert r.json()["detail"]["error_code"] == "UPLOAD_RATE_LIMIT"
    assert r.headers["Retry-After"] == "1800"


def test_upload_limits_are_10_free_50_paid():
    from app.core.rate_limit import _UPLOAD_HOURLY_LIMITS

    assert _UPLOAD_HOURLY_LIMITS == {"free": 10, "paid": 50}


# ── Auth-failure monitoring config ────────────────────────────────────────────

def test_auth_failure_threshold_is_10():
    from app.core.rate_limit import auth_failure_alert_threshold

    assert auth_failure_alert_threshold() == 10


# ── Security-event logging never raises and records safe metadata ─────────────

@pytest.mark.asyncio
async def test_log_security_event_never_raises_without_db():
    from app.core.security_events import EVENT_SUSPICIOUS_PATTERN, log_security_event

    # No DB configured in this unit test → the audit write fails internally,
    # but the helper must swallow it and never raise into the request path.
    await log_security_event(
        action=EVENT_SUSPICIOUS_PATTERN,
        metadata={"pattern": "sqli_union", "path": "/api/v1/x"},
        ip="203.0.113.5",
    )
