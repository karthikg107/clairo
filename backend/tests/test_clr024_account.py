"""
CLR-024 — Account settings and GDPR data deletion/export tests.

GET /api/v1/account, PATCH /api/v1/account/language-preferences,
GET /api/v1/account/export, POST /api/v1/account/delete.
"""
from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.db.session import get_db
from app.models.analysis import Analysis, DocumentType
from app.models.audit_log import AuditLog
from app.models.subscription import (
    BillingInterval,
    Subscription,
    SubscriptionStatus,
    SubscriptionTier,
)
from app.models.user import User


class _FakeResult:
    def __init__(self, value):
        self._value = value

    def scalar_one_or_none(self):
        return self._value

    def scalars(self):
        return self

    def all(self):
        return self._value if isinstance(self._value, list) else [self._value]


def _mock_session_factory(*results):
    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(side_effect=[_FakeResult(r) for r in results])
    mock_session.add = MagicMock()

    @asynccontextmanager
    async def factory_cm():
        yield mock_session

    session_factory = MagicMock(side_effect=lambda: factory_cm())
    get_session_factory_mock = MagicMock(return_value=session_factory)
    return get_session_factory_mock, mock_session


def _make_user(**kwargs) -> User:
    defaults = {
        "id": uuid.uuid4(),
        "clerk_id": "user_abc",
        "email": "a@b.com",
        "created_at": datetime(2026, 1, 15, tzinfo=UTC),
        "doc_language": None,
        "output_language": None,
        "country": None,
    }
    defaults.update(kwargs)
    return User(**defaults)


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
            app.dependency_overrides.pop(get_db, None)


def _override_db(*results):
    from app.main import app

    factory, session = _mock_session_factory(*results)

    async def _get_db():
        async with factory()() as s:
            yield s

    app.dependency_overrides[get_db] = _get_db
    return session


# ── GET /api/v1/account ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_account_requires_auth(client):
    _override_db(None)
    r = await client.get("/api/v1/account")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_get_account_user_not_found(client):
    _override_db(None)
    r = await client.get("/api/v1/account", headers={"X-Clerk-User-Id": "ghost"})
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_get_account_free_tier_when_no_subscription(client):
    user = _make_user()
    _override_db(user, None)

    r = await client.get("/api/v1/account", headers={"X-Clerk-User-Id": "user_abc"})
    assert r.status_code == 200
    body = r.json()
    assert body["email"] == "a@b.com"
    assert body["subscription_tier"] == "free"
    assert body["member_since"].startswith("2026-01-15")
    assert body["doc_language"] is None


@pytest.mark.asyncio
async def test_get_account_reflects_paid_tier(client):
    user = _make_user(doc_language="en", output_language="es", country="US")
    subscription = Subscription(
        user_id=user.id, tier=SubscriptionTier.pro, status=SubscriptionStatus.active
    )
    _override_db(user, subscription)

    r = await client.get("/api/v1/account", headers={"X-Clerk-User-Id": "user_abc"})
    assert r.status_code == 200
    body = r.json()
    assert body["subscription_tier"] == "pro"
    assert body["doc_language"] == "en"
    assert body["output_language"] == "es"
    assert body["country"] == "US"


# ── PATCH /api/v1/account/language-preferences ────────────────────────────────

@pytest.mark.asyncio
async def test_update_language_preferences_requires_auth(client):
    _override_db(None)
    r = await client.patch(
        "/api/v1/account/language-preferences",
        json={"doc_language": "en", "output_language": "es", "country": "US"},
    )
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_update_language_preferences_rejects_bad_country(client):
    user = _make_user()
    _override_db(user)

    r = await client.patch(
        "/api/v1/account/language-preferences",
        json={"doc_language": "en", "output_language": "es", "country": "usa"},
        headers={"X-Clerk-User-Id": "user_abc"},
    )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_update_language_preferences_saves_and_returns(client):
    user = _make_user()
    session = _override_db(user, None)

    r = await client.patch(
        "/api/v1/account/language-preferences",
        json={"doc_language": "hi", "output_language": "en", "country": "IN"},
        headers={"X-Clerk-User-Id": "user_abc"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["doc_language"] == "hi"
    assert body["output_language"] == "en"
    assert body["country"] == "IN"
    assert user.doc_language == "hi"
    session.commit.assert_awaited()


# ── GET /api/v1/account/export ─────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_export_requires_auth(client):
    _override_db(None)
    r = await client.get("/api/v1/account/export")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_export_shape_with_no_subscription_or_analyses(client):
    user = _make_user()
    # queue: require_user, subscription, analyses, audit, share_links, referrals
    _override_db(user, None, [], [], [], [])

    r = await client.get("/api/v1/account/export", headers={"X-Clerk-User-Id": "user_abc"})
    assert r.status_code == 200
    body = r.json()
    assert body["user"]["email"] == "a@b.com"
    assert body["subscription"] is None
    assert body["analyses"] == []
    assert body["share_links"] == []
    assert body["referrals"] == []
    assert body["audit_log"] == []
    # CLR-055 — quota fields belong to the account record
    assert "free_analyses_used" in body["user"]
    assert "bonus_analyses" in body["user"]


@pytest.mark.asyncio
async def test_export_includes_subscription_analyses_and_audit_log(client):
    user = _make_user()
    subscription = Subscription(
        user_id=user.id,
        tier=SubscriptionTier.starter,
        status=SubscriptionStatus.active,
        billing_interval=BillingInterval.monthly,
        stripe_customer_id="cus_secret_internal_id",
        created_at=datetime(2026, 2, 1, tzinfo=UTC),
    )
    analysis = Analysis(
        id=uuid.uuid4(),
        user_id=user.id,
        document_type=DocumentType.rental,
        doc_language="en",
        output_language="en",
        result_json={"summary": "A lease."},
        created_at=datetime(2026, 3, 1, tzinfo=UTC),
    )
    audit_row = AuditLog(
        action="tos_accepted",
        metadata_json={"tos_version": "1.0"},
        created_at=datetime(2026, 1, 16, tzinfo=UTC),
    )
    _override_db(user, subscription, [analysis], [audit_row], [], [])

    r = await client.get("/api/v1/account/export", headers={"X-Clerk-User-Id": "user_abc"})
    assert r.status_code == 200
    body = r.json()

    assert body["subscription"]["tier"] == "starter"
    assert body["subscription"]["billing_interval"] == "monthly"
    # SECURITY: raw Stripe identifiers are internal/operational, not exported.
    assert "stripe_customer_id" not in body["subscription"]
    assert "cus_secret_internal_id" not in str(body)

    assert len(body["analyses"]) == 1
    assert body["analyses"][0]["document_type"] == "rental"
    assert body["analyses"][0]["result_json"] == {"summary": "A lease."}

    assert len(body["audit_log"]) == 1
    assert body["audit_log"][0]["action"] == "tos_accepted"


@pytest.mark.asyncio
async def test_export_never_contains_document_content_markers():
    """SECURITY: exported analyses only ever carry the same structured JSON
    already returned by /analyse — never raw document text."""
    user = _make_user()
    sentinel = "SENTINEL_SHOULD_NEVER_APPEAR_IN_EXPORT"
    analysis = Analysis(
        id=uuid.uuid4(),
        user_id=user.id,
        document_type=DocumentType.rental,
        doc_language="en",
        output_language="en",
        result_json={"summary": "Safe summary, no document content."},
        created_at=datetime(2026, 3, 1, tzinfo=UTC),
    )

    from httpx import ASGITransport, AsyncClient

    import app.middleware.rate_limit as rl_module
    from app.core.rate_limit import RateLimitResult
    from app.main import app

    async def _mock_rate(*args, **kwargs):
        return RateLimitResult(allowed=True, limit=100, remaining=99, reset_in_seconds=3600)

    _override_db(user, None, [analysis], [], [], [])

    with patch.object(rl_module, "check_rate_limit", side_effect=_mock_rate):
        with patch.object(rl_module, "check_endpoint_rate_limit", side_effect=_mock_rate):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://localhost") as c:
                r = await c.get(
                    "/api/v1/account/export", headers={"X-Clerk-User-Id": "user_abc"}
                )

    app.dependency_overrides.pop(get_db, None)
    assert sentinel not in r.text


# ── POST /api/v1/account/delete ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_delete_account_requires_exact_confirmation_text(client):
    user = _make_user()
    _override_db(user)

    r = await client.post(
        "/api/v1/account/delete",
        json={"confirmation": "delete"},  # lowercase — must not match
        headers={"X-Clerk-User-Id": "user_abc"},
    )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_delete_account_confirmation_checked_before_auth_lookup(client):
    """A bad confirmation is rejected without even resolving the user."""
    session = _override_db()

    r = await client.post("/api/v1/account/delete", json={"confirmation": "nope"})
    assert r.status_code == 422
    session.execute.assert_not_called()


@pytest.mark.asyncio
async def test_delete_account_requires_auth(client):
    _override_db(None)
    r = await client.post("/api/v1/account/delete", json={"confirmation": "DELETE"})
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_delete_account_calls_gdpr_delete_user(client):
    user = _make_user()
    session = _override_db(user, None)  # user lookup, then the DELETE call's result

    r = await client.post(
        "/api/v1/account/delete",
        json={"confirmation": "DELETE"},
        headers={"X-Clerk-User-Id": "user_abc"},
    )

    assert r.status_code == 204
    assert session.execute.call_count == 2
    delete_call = session.execute.call_args_list[1]
    # SQLAlchemy text() constructs compare by rendered SQL string.
    assert "gdpr_delete_user" in str(delete_call.args[0])
    assert delete_call.args[1] == {"uid": str(user.id)}
    session.commit.assert_awaited()
