"""
CLR-028 — Subscription upgrade and checkout flow.

- A user with NO active subscription gets a fresh Stripe Checkout
  session (existing CLR-026 behavior).
- A user who ALREADY has an active/trialing subscription gets their
  existing Stripe subscription modified in place with proration,
  instead of a second Checkout session.
- The Checkout success_url points at /dashboard?upgraded=true.
"""
from __future__ import annotations

import uuid
from unittest.mock import MagicMock, patch

import pytest
import stripe

from app.models.subscription import (
    BillingInterval,
    Subscription,
    SubscriptionStatus,
    SubscriptionTier,
)
from app.models.user import User
from app.services.billing import (
    BillingError,
    change_subscription_tier,
    create_checkout_session,
)

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


def _make_user() -> User:
    return User(id=uuid.uuid4(), clerk_id="user_abc", email="test@example.com")


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


def _override_db(session: FakeSession):
    from app.db.session import get_db
    from app.main import app

    async def _get_db():
        yield session

    app.dependency_overrides[get_db] = _get_db


# ── change_subscription_tier (service) ────────────────────────────────────────

@pytest.mark.asyncio
async def test_change_tier_modifies_existing_stripe_subscription_with_proration():
    user = _make_user()
    subscription = Subscription(
        user_id=user.id,
        tier=SubscriptionTier.starter,
        status=SubscriptionStatus.active,
        billing_interval=BillingInterval.monthly,
        stripe_subscription_id="sub_existing",
    )
    session = FakeSession()  # existing_subscription passed directly, no lookup needed

    mock_stripe_sub = {"items": {"data": [{"id": "si_123"}]}}

    with patch("app.services.billing._stripe_secrets", return_value=STRIPE_SECRETS):
        with patch("stripe.Subscription.retrieve", return_value=mock_stripe_sub) as mock_retrieve:
            with patch("stripe.Subscription.modify") as mock_modify:
                await change_subscription_tier(
                    session,
                    user=user,
                    tier=SubscriptionTier.pro,
                    interval=BillingInterval.monthly,
                    existing_subscription=subscription,
                )

    mock_retrieve.assert_called_once_with("sub_existing", api_key="sk_test_x")
    _, kwargs = mock_modify.call_args
    assert mock_modify.call_args.args[0] == "sub_existing"
    assert kwargs["items"] == [{"id": "si_123", "price": "price_pro_m"}]
    assert kwargs["proration_behavior"] == "create_prorations"
    assert kwargs["metadata"] == {"tier": "pro", "interval": "monthly"}

    # Local row updated optimistically.
    assert subscription.tier == SubscriptionTier.pro
    assert subscription.billing_interval == BillingInterval.monthly
    assert session.committed is True


@pytest.mark.asyncio
async def test_change_tier_rejects_free_tier():
    user = _make_user()
    subscription = Subscription(
        user_id=user.id, tier=SubscriptionTier.starter, status=SubscriptionStatus.active,
        stripe_subscription_id="sub_existing",
    )
    session = FakeSession()

    with pytest.raises(BillingError):
        await change_subscription_tier(
            session,
            user=user,
            tier=SubscriptionTier.free,
            interval=BillingInterval.monthly,
            existing_subscription=subscription,
        )


@pytest.mark.asyncio
async def test_change_tier_requires_existing_stripe_subscription():
    user = _make_user()
    subscription = Subscription(
        user_id=user.id, tier=SubscriptionTier.free, status=SubscriptionStatus.active,
        stripe_subscription_id=None,
    )
    session = FakeSession()

    with pytest.raises(BillingError, match="No active subscription"):
        await change_subscription_tier(
            session,
            user=user,
            tier=SubscriptionTier.pro,
            interval=BillingInterval.monthly,
            existing_subscription=subscription,
        )


@pytest.mark.asyncio
async def test_change_tier_wraps_stripe_error():
    user = _make_user()
    subscription = Subscription(
        user_id=user.id, tier=SubscriptionTier.starter, status=SubscriptionStatus.active,
        stripe_subscription_id="sub_existing",
    )
    session = FakeSession()

    with patch("app.services.billing._stripe_secrets", return_value=STRIPE_SECRETS):
        with patch("stripe.Subscription.retrieve", side_effect=stripe.StripeError("boom")):
            with pytest.raises(BillingError):
                await change_subscription_tier(
                    session,
                    user=user,
                    tier=SubscriptionTier.pro,
                    interval=BillingInterval.monthly,
                    existing_subscription=subscription,
                )


@pytest.mark.asyncio
async def test_change_tier_looks_up_subscription_when_not_provided():
    user = _make_user()
    subscription = Subscription(
        user_id=user.id, tier=SubscriptionTier.starter, status=SubscriptionStatus.active,
        stripe_subscription_id="sub_existing",
    )
    session = FakeSession(subscription)  # no existing_subscription arg -> must query

    mock_stripe_sub = {"items": {"data": [{"id": "si_123"}]}}
    with patch("app.services.billing._stripe_secrets", return_value=STRIPE_SECRETS):
        with patch("stripe.Subscription.retrieve", return_value=mock_stripe_sub):
            with patch("stripe.Subscription.modify"):
                await change_subscription_tier(
                    session, user=user, tier=SubscriptionTier.pro, interval=BillingInterval.annual
                )

    assert subscription.tier == SubscriptionTier.pro


# ── create_checkout_session still accepts existing_subscription without re-querying ──

@pytest.mark.asyncio
async def test_create_checkout_session_uses_passed_subscription_without_extra_query():
    user = _make_user()
    subscription = Subscription(
        user_id=user.id, tier=SubscriptionTier.free, status=SubscriptionStatus.active,
        stripe_customer_id="cus_existing",
    )
    session = FakeSession()  # zero queued results — a query here would return None and break

    mock_checkout_session = MagicMock(url="https://checkout.stripe.com/pay/cs_test_1")
    with patch("app.services.billing._stripe_secrets", return_value=STRIPE_SECRETS):
        with patch("stripe.checkout.Session.create", return_value=mock_checkout_session):
            url = await create_checkout_session(
                session,
                user=user,
                tier=SubscriptionTier.pro,
                interval=BillingInterval.monthly,
                success_url="https://clairo.app/dashboard?upgraded=true",
                cancel_url="https://clairo.app/pricing",
                existing_subscription=subscription,
            )

    assert url == "https://checkout.stripe.com/pay/cs_test_1"


# ── POST /api/v1/billing/checkout-session — endpoint branching ────────────────

@pytest.mark.asyncio
async def test_endpoint_new_subscriber_gets_checkout_redirect(client):
    """No subscription row at all — brand new subscriber, needs Checkout."""
    user = User(id=uuid.uuid4(), clerk_id="user_abc", email="a@b.com")
    _override_db(FakeSession(user, None))

    mock_checkout_session = MagicMock(url="https://checkout.stripe.com/pay/cs_new")
    with patch("app.services.billing._stripe_secrets", return_value=STRIPE_SECRETS):
        with patch("stripe.Customer.create", return_value=MagicMock(id="cus_new")):
            with patch("stripe.checkout.Session.create", return_value=mock_checkout_session):
                r = await client.post(
                    "/api/v1/billing/checkout-session",
                    json={"tier": "starter", "interval": "monthly"},
                    headers={"X-Clerk-User-Id": "user_abc"},
                )

    assert r.status_code == 200
    body = r.json()
    assert body["checkout_url"] == "https://checkout.stripe.com/pay/cs_new"
    assert body["applied_immediately"] is False


@pytest.mark.asyncio
async def test_endpoint_success_url_points_at_dashboard(client):
    user = User(id=uuid.uuid4(), clerk_id="user_abc", email="a@b.com")
    _override_db(FakeSession(user, None))

    mock_checkout_session = MagicMock(url="https://checkout.stripe.com/pay/cs_new")
    with patch("app.services.billing._stripe_secrets", return_value=STRIPE_SECRETS):
        with patch("stripe.Customer.create", return_value=MagicMock(id="cus_new")):
            with patch(
                "stripe.checkout.Session.create", return_value=mock_checkout_session
            ) as mock_create:
                await client.post(
                    "/api/v1/billing/checkout-session",
                    json={"tier": "starter", "interval": "monthly"},
                    headers={"X-Clerk-User-Id": "user_abc"},
                )

    _, kwargs = mock_create.call_args
    assert kwargs["success_url"] == "http://localhost:3000/dashboard?upgraded=true"
    assert "/billing/success" not in kwargs["success_url"]


@pytest.mark.asyncio
async def test_endpoint_free_tier_subscription_row_still_gets_checkout(client):
    """A Subscription row exists (e.g. from a prior Stripe customer creation)
    but its tier is free / no stripe_subscription_id — still a new subscriber."""
    user = User(id=uuid.uuid4(), clerk_id="user_abc", email="a@b.com")
    subscription = Subscription(
        user_id=user.id, tier=SubscriptionTier.free, status=SubscriptionStatus.active,
        stripe_customer_id="cus_1", stripe_subscription_id=None,
    )
    _override_db(FakeSession(user, subscription))

    mock_checkout_session = MagicMock(url="https://checkout.stripe.com/pay/cs_new")
    with patch("app.services.billing._stripe_secrets", return_value=STRIPE_SECRETS):
        with patch("stripe.checkout.Session.create", return_value=mock_checkout_session):
            r = await client.post(
                "/api/v1/billing/checkout-session",
                json={"tier": "starter", "interval": "monthly"},
                headers={"X-Clerk-User-Id": "user_abc"},
            )

    assert r.status_code == 200
    assert r.json()["applied_immediately"] is False


@pytest.mark.asyncio
async def test_endpoint_active_subscriber_gets_prorated_tier_change_not_checkout(client):
    """An already-active subscriber changing tiers must NOT go through Checkout."""
    user = User(id=uuid.uuid4(), clerk_id="user_abc", email="a@b.com")
    subscription = Subscription(
        user_id=user.id, tier=SubscriptionTier.starter, status=SubscriptionStatus.active,
        stripe_subscription_id="sub_existing",
    )
    _override_db(FakeSession(user, subscription))

    mock_stripe_sub = {"items": {"data": [{"id": "si_123"}]}}
    with patch("app.services.billing._stripe_secrets", return_value=STRIPE_SECRETS):
        with patch("stripe.Subscription.retrieve", return_value=mock_stripe_sub):
            with patch("stripe.checkout.Session.create") as mock_checkout_create:
                with patch("stripe.Subscription.modify") as mock_modify:
                    r = await client.post(
                        "/api/v1/billing/checkout-session",
                        json={"tier": "pro", "interval": "monthly"},
                        headers={"X-Clerk-User-Id": "user_abc"},
                    )

    assert r.status_code == 200
    body = r.json()
    assert body["applied_immediately"] is True
    assert body["checkout_url"] is None
    mock_checkout_create.assert_not_called()
    mock_modify.assert_called_once()
    assert subscription.tier == SubscriptionTier.pro


@pytest.mark.asyncio
async def test_endpoint_trialing_subscriber_also_gets_prorated_change(client):
    user = User(id=uuid.uuid4(), clerk_id="user_abc", email="a@b.com")
    subscription = Subscription(
        user_id=user.id, tier=SubscriptionTier.starter, status=SubscriptionStatus.trialing,
        stripe_subscription_id="sub_existing",
    )
    _override_db(FakeSession(user, subscription))

    mock_stripe_sub = {"items": {"data": [{"id": "si_123"}]}}
    with patch("app.services.billing._stripe_secrets", return_value=STRIPE_SECRETS):
        with patch("stripe.Subscription.retrieve", return_value=mock_stripe_sub):
            with patch("stripe.checkout.Session.create") as mock_checkout_create:
                with patch("stripe.Subscription.modify"):
                    r = await client.post(
                        "/api/v1/billing/checkout-session",
                        json={"tier": "team", "interval": "annual"},
                        headers={"X-Clerk-User-Id": "user_abc"},
                    )

    assert r.status_code == 200
    assert r.json()["applied_immediately"] is True
    mock_checkout_create.assert_not_called()


@pytest.mark.asyncio
async def test_endpoint_canceled_subscriber_gets_fresh_checkout_not_modify(client):
    """A canceled subscription has no live Stripe subscription item to modify."""
    user = User(id=uuid.uuid4(), clerk_id="user_abc", email="a@b.com")
    subscription = Subscription(
        user_id=user.id, tier=SubscriptionTier.free, status=SubscriptionStatus.canceled,
        stripe_subscription_id="sub_canceled", stripe_customer_id="cus_1",
    )
    _override_db(FakeSession(user, subscription))

    mock_checkout_session = MagicMock(url="https://checkout.stripe.com/pay/cs_resub")
    with patch("app.services.billing._stripe_secrets", return_value=STRIPE_SECRETS):
        with patch("stripe.checkout.Session.create", return_value=mock_checkout_session):
            with patch("stripe.Subscription.modify") as mock_modify:
                r = await client.post(
                    "/api/v1/billing/checkout-session",
                    json={"tier": "pro", "interval": "monthly"},
                    headers={"X-Clerk-User-Id": "user_abc"},
                )

    assert r.status_code == 200
    body = r.json()
    assert body["applied_immediately"] is False
    assert body["checkout_url"] == "https://checkout.stripe.com/pay/cs_resub"
    mock_modify.assert_not_called()


@pytest.mark.asyncio
async def test_endpoint_tier_change_stripe_error_returns_502(client):
    user = User(id=uuid.uuid4(), clerk_id="user_abc", email="a@b.com")
    subscription = Subscription(
        user_id=user.id, tier=SubscriptionTier.starter, status=SubscriptionStatus.active,
        stripe_subscription_id="sub_existing",
    )
    _override_db(FakeSession(user, subscription))

    with patch("app.services.billing._stripe_secrets", return_value=STRIPE_SECRETS):
        with patch("stripe.Subscription.retrieve", side_effect=stripe.StripeError("boom")):
            r = await client.post(
                "/api/v1/billing/checkout-session",
                json={"tier": "pro", "interval": "monthly"},
                headers={"X-Clerk-User-Id": "user_abc"},
            )

    assert r.status_code == 502
    assert r.json()["detail"]["error"] == "tier_change_failed"
