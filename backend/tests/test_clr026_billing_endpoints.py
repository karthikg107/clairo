"""
CLR-026 — Endpoint-level tests: checkout session, subscription status, and
webhook handling under /api/v1/billing/*.

Uses FastAPI's dependency_overrides for get_db (the endpoints declare a
hard `Depends(get_db)`, unlike the best-effort session helpers elsewhere
in this codebase, so a real override is required rather than patching a
module-level function).
"""
from __future__ import annotations

import uuid
from unittest.mock import MagicMock, patch

import pytest
import stripe

from app.db.session import get_db
from app.models.subscription import Subscription, SubscriptionStatus, SubscriptionTier
from app.models.user import User

STRIPE_SECRETS = {
    "secret_key": "sk_test_x",
    "webhook_secret": "whsec_test",
    "price_starter_monthly": "price_starter_m",
    "price_starter_annual": "price_starter_a",
    "price_pro_monthly": "price_pro_m",
    "price_pro_annual": "price_pro_a",
    "price_team_monthly": "price_team_m",
    "price_team_annual": "price_team_a",
}


class _FakeResult:
    def __init__(self, value):
        self._value = value

    def scalar_one_or_none(self):
        return self._value


class FakeSession:
    def __init__(self, *results):
        self._results = list(results)
        self.added = []
        self.committed = False

    async def execute(self, *_args, **_kwargs):
        return _FakeResult(self._results.pop(0) if self._results else None)

    def add(self, obj):
        self.added.append(obj)

    async def commit(self):
        self.committed = True


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


def _override_db(session: FakeSession):
    from app.main import app

    async def _get_db():
        yield session

    app.dependency_overrides[get_db] = _get_db


# ── POST /api/v1/billing/checkout-session ─────────────────────────────────────

@pytest.mark.asyncio
async def test_checkout_session_requires_auth(client):
    # FastAPI resolves Depends(get_db) before the handler body runs (which
    # is where the 401 actually gets raised), so the dependency still
    # needs a working override even though this test never uses the DB.
    _override_db(FakeSession())

    r = await client.post(
        "/api/v1/billing/checkout-session", json={"tier": "pro", "interval": "monthly"}
    )
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_checkout_session_rejects_unknown_tier(client):
    user = User(id=uuid.uuid4(), clerk_id="user_abc", email="a@b.com")
    _override_db(FakeSession(user))

    r = await client.post(
        "/api/v1/billing/checkout-session",
        json={"tier": "banana", "interval": "monthly"},
        headers={"X-Clerk-User-Id": "user_abc"},
    )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_checkout_session_rejects_bad_interval(client):
    user = User(id=uuid.uuid4(), clerk_id="user_abc", email="a@b.com")
    _override_db(FakeSession(user))

    r = await client.post(
        "/api/v1/billing/checkout-session",
        json={"tier": "pro", "interval": "weekly"},
        headers={"X-Clerk-User-Id": "user_abc"},
    )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_checkout_session_user_not_found_returns_404(client):
    _override_db(FakeSession(None))

    r = await client.post(
        "/api/v1/billing/checkout-session",
        json={"tier": "pro", "interval": "monthly"},
        headers={"X-Clerk-User-Id": "ghost_user"},
    )
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_checkout_session_happy_path(client):
    user = User(id=uuid.uuid4(), clerk_id="user_abc", email="a@b.com")
    subscription = Subscription(
        user_id=user.id, tier=SubscriptionTier.free, status=SubscriptionStatus.active,
        stripe_customer_id="cus_1",
    )
    _override_db(FakeSession(user, subscription))

    mock_checkout_session = MagicMock(url="https://checkout.stripe.com/pay/cs_test_1")

    with patch("app.services.billing._stripe_secrets", return_value=STRIPE_SECRETS):
        with patch("stripe.checkout.Session.create", return_value=mock_checkout_session):
            r = await client.post(
                "/api/v1/billing/checkout-session",
                json={"tier": "pro", "interval": "monthly"},
                headers={"X-Clerk-User-Id": "user_abc"},
            )

    assert r.status_code == 200
    assert r.json()["checkout_url"] == "https://checkout.stripe.com/pay/cs_test_1"


@pytest.mark.asyncio
async def test_checkout_session_stripe_error_returns_502(client):
    user = User(id=uuid.uuid4(), clerk_id="user_abc", email="a@b.com")
    subscription = Subscription(
        user_id=user.id, tier=SubscriptionTier.free, status=SubscriptionStatus.active,
        stripe_customer_id="cus_1",
    )
    _override_db(FakeSession(user, subscription))

    with patch("app.services.billing._stripe_secrets", return_value=STRIPE_SECRETS):
        with patch("stripe.checkout.Session.create", side_effect=stripe.StripeError("boom")):
            r = await client.post(
                "/api/v1/billing/checkout-session",
                json={"tier": "pro", "interval": "monthly"},
                headers={"X-Clerk-User-Id": "user_abc"},
            )

    assert r.status_code == 502


# ── GET /api/v1/billing/subscription ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_subscription_status_defaults_to_free_with_no_row(client):
    user = User(id=uuid.uuid4(), clerk_id="user_abc", email="a@b.com")
    _override_db(FakeSession(user, None))

    r = await client.get(
        "/api/v1/billing/subscription", headers={"X-Clerk-User-Id": "user_abc"}
    )
    assert r.status_code == 200
    body = r.json()
    assert body["tier"] == "free"
    assert body["billing_interval"] is None


@pytest.mark.asyncio
async def test_subscription_status_reflects_paid_tier(client):
    user = User(id=uuid.uuid4(), clerk_id="user_abc", email="a@b.com")
    subscription = Subscription(
        user_id=user.id, tier=SubscriptionTier.team, status=SubscriptionStatus.active,
    )
    from app.models.subscription import BillingInterval
    subscription.billing_interval = BillingInterval.annual
    _override_db(FakeSession(user, subscription))

    r = await client.get(
        "/api/v1/billing/subscription", headers={"X-Clerk-User-Id": "user_abc"}
    )
    assert r.status_code == 200
    body = r.json()
    assert body["tier"] == "team"
    assert body["billing_interval"] == "annual"


# ── POST /api/v1/billing/webhook ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_webhook_invalid_signature_returns_400(client):
    _override_db(FakeSession())

    with patch("app.services.billing._stripe_secrets", return_value=STRIPE_SECRETS):
        with patch(
            "stripe.Webhook.construct_event",
            side_effect=stripe.SignatureVerificationError("bad", "sig"),
        ):
            r = await client.post(
                "/api/v1/billing/webhook",
                content=b'{"type": "invoice.payment_failed"}',
                headers={"stripe-signature": "bad_sig"},
            )

    assert r.status_code == 400


@pytest.mark.asyncio
async def test_webhook_valid_event_dispatches_and_returns_204(client):
    subscription = Subscription(
        user_id=uuid.uuid4(), tier=SubscriptionTier.pro, status=SubscriptionStatus.active,
        stripe_subscription_id="sub_1",
    )
    _override_db(FakeSession(subscription))

    fake_event = {
        "type": "invoice.payment_failed",
        "data": {"object": {"subscription": "sub_1"}},
    }

    with patch("app.services.billing._stripe_secrets", return_value=STRIPE_SECRETS):
        with patch("stripe.Webhook.construct_event", return_value=fake_event):
            r = await client.post(
                "/api/v1/billing/webhook",
                content=b'{"type": "invoice.payment_failed"}',
                headers={"stripe-signature": "good_sig"},
            )

    assert r.status_code == 204
    assert subscription.status == SubscriptionStatus.past_due


@pytest.mark.asyncio
async def test_webhook_does_not_require_clerk_auth(client):
    """The whole point of the exemption — no X-Clerk-User-Id / Authorization header at all."""
    _override_db(FakeSession())
    fake_event = {"type": "some.unhandled.event", "data": {"object": {}}}

    with patch("app.services.billing._stripe_secrets", return_value=STRIPE_SECRETS):
        with patch("stripe.Webhook.construct_event", return_value=fake_event):
            r = await client.post(
                "/api/v1/billing/webhook",
                content=b"{}",
                headers={"stripe-signature": "good_sig"},
            )

    assert r.status_code == 204
