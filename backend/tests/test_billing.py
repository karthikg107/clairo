"""
CLR-026 — Stripe subscription billing tests.

Service-layer tests mock the `stripe` SDK directly (matching how
`anthropic.AsyncAnthropic` is mocked in test_analysis.py) and use a
lightweight fake AsyncSession (matching the quota-service test pattern)
rather than a live Postgres connection — there is no live-DB test
fixture anywhere in this repo.
"""
from __future__ import annotations

import uuid
from decimal import Decimal
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
    TIER_PRICING,
    BillingError,
    _annual_total,
    _price_id_for,
    create_checkout_session,
    dispatch_webhook_event,
    handle_checkout_completed,
    handle_payment_failed,
    handle_payment_succeeded,
    handle_subscription_deleted,
    handle_subscription_updated,
    verify_webhook_signature,
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


def _make_user() -> User:
    return User(id=uuid.uuid4(), clerk_id="user_abc", email="test@example.com")


class _FakeResult:
    def __init__(self, value):
        self._value = value

    def scalar_one_or_none(self):
        return self._value


class FakeSession:
    """Minimal AsyncSession stand-in — queues canned results for execute()."""

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


# ── Pricing math ───────────────────────────────────────────────────────────────

class TestPricing:
    def test_annual_total_is_25_percent_off_yearly(self):
        # $7/mo * 12 = $84/yr; 25% off = $63/yr
        assert _annual_total(Decimal("7")) == Decimal("63.00")

    def test_free_tier_is_zero(self):
        pricing = TIER_PRICING[SubscriptionTier.free]
        assert pricing.monthly_usd == Decimal("0")
        assert pricing.annual_usd == Decimal("0")

    def test_starter_pricing(self):
        pricing = TIER_PRICING[SubscriptionTier.starter]
        assert pricing.monthly_usd == Decimal("7")
        assert pricing.annual_usd == Decimal("63.00")

    def test_pro_pricing(self):
        pricing = TIER_PRICING[SubscriptionTier.pro]
        assert pricing.monthly_usd == Decimal("19")
        assert pricing.annual_usd == Decimal("171.00")

    def test_team_pricing(self):
        pricing = TIER_PRICING[SubscriptionTier.team]
        assert pricing.monthly_usd == Decimal("49")
        assert pricing.annual_usd == Decimal("441.00")

    def test_all_four_tiers_priced(self):
        assert set(TIER_PRICING.keys()) == {
            SubscriptionTier.free, SubscriptionTier.starter,
            SubscriptionTier.pro, SubscriptionTier.team,
        }


# ── _price_id_for ──────────────────────────────────────────────────────────────

class TestPriceIdFor:
    def test_resolves_configured_price(self):
        with patch("app.services.billing._stripe_secrets", return_value=STRIPE_SECRETS):
            price_id = _price_id_for(SubscriptionTier.starter, BillingInterval.monthly)
        assert price_id == "price_starter_m"

    def test_free_tier_raises(self):
        with patch("app.services.billing._stripe_secrets", return_value=STRIPE_SECRETS):
            with pytest.raises(BillingError):
                _price_id_for(SubscriptionTier.free, BillingInterval.monthly)

    def test_missing_price_id_raises(self):
        with patch("app.services.billing._stripe_secrets", return_value={}):
            with pytest.raises(BillingError):
                _price_id_for(SubscriptionTier.pro, BillingInterval.annual)


# ── create_checkout_session ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_checkout_session_happy_path():
    user = _make_user()
    existing_subscription = Subscription(
        user_id=user.id, tier=SubscriptionTier.free, status=SubscriptionStatus.active,
        stripe_customer_id="cus_existing",
    )
    session = FakeSession(existing_subscription)

    mock_checkout_session = MagicMock(url="https://checkout.stripe.com/pay/cs_test_123")

    with patch("app.services.billing._stripe_secrets", return_value=STRIPE_SECRETS):
        with patch(
            "stripe.checkout.Session.create", return_value=mock_checkout_session
        ) as mock_create:
            url = await create_checkout_session(
                session,
                user=user,
                tier=SubscriptionTier.pro,
                interval=BillingInterval.monthly,
                success_url="https://clairo.app/success",
                cancel_url="https://clairo.app/pricing",
            )

    assert url == "https://checkout.stripe.com/pay/cs_test_123"
    _, kwargs = mock_create.call_args
    assert kwargs["customer"] == "cus_existing"
    assert kwargs["line_items"] == [{"price": "price_pro_m", "quantity": 1}]
    assert kwargs["metadata"] == {"user_id": str(user.id), "tier": "pro", "interval": "monthly"}
    assert kwargs["api_key"] == "sk_test_x"


@pytest.mark.asyncio
async def test_create_checkout_session_creates_customer_when_none_exists():
    user = _make_user()
    session = FakeSession(None)  # no existing Subscription row

    mock_customer = MagicMock(id="cus_new")
    mock_checkout_session = MagicMock(url="https://checkout.stripe.com/pay/cs_test_456")

    with patch("app.services.billing._stripe_secrets", return_value=STRIPE_SECRETS):
        with patch("stripe.Customer.create", return_value=mock_customer) as mock_customer_create:
            with patch("stripe.checkout.Session.create", return_value=mock_checkout_session):
                await create_checkout_session(
                    session,
                    user=user,
                    tier=SubscriptionTier.starter,
                    interval=BillingInterval.annual,
                    success_url="https://clairo.app/success",
                    cancel_url="https://clairo.app/pricing",
                )

    mock_customer_create.assert_called_once()
    assert session.committed is True
    assert len(session.added) == 1
    assert session.added[0].stripe_customer_id == "cus_new"


@pytest.mark.asyncio
async def test_create_checkout_session_rejects_free_tier():
    user = _make_user()
    session = FakeSession(None)
    with pytest.raises(BillingError):
        await create_checkout_session(
            session,
            user=user,
            tier=SubscriptionTier.free,
            interval=BillingInterval.monthly,
            success_url="x",
            cancel_url="y",
        )


@pytest.mark.asyncio
async def test_create_checkout_session_wraps_stripe_error():
    user = _make_user()
    subscription = Subscription(
        user_id=user.id, tier=SubscriptionTier.free, status=SubscriptionStatus.active,
        stripe_customer_id="cus_existing",
    )
    session = FakeSession(subscription)

    with patch("app.services.billing._stripe_secrets", return_value=STRIPE_SECRETS):
        with patch(
            "stripe.checkout.Session.create",
            side_effect=stripe.StripeError("card issue"),
        ):
            with pytest.raises(BillingError):
                await create_checkout_session(
                    session,
                    user=user,
                    tier=SubscriptionTier.team,
                    interval=BillingInterval.monthly,
                    success_url="x",
                    cancel_url="y",
                )


# ── Webhook signature verification ────────────────────────────────────────────

class TestVerifyWebhookSignature:
    def test_valid_signature_returns_event(self):
        fake_event = {"type": "checkout.session.completed", "data": {"object": {}}}
        with patch("app.services.billing._stripe_secrets", return_value=STRIPE_SECRETS):
            with patch("stripe.Webhook.construct_event", return_value=fake_event) as mock_construct:
                event = verify_webhook_signature(b"payload", "sig_header_value")
        assert event == fake_event
        mock_construct.assert_called_once_with(b"payload", "sig_header_value", "whsec_test")

    def test_invalid_signature_propagates(self):
        with patch("app.services.billing._stripe_secrets", return_value=STRIPE_SECRETS):
            with patch(
                "stripe.Webhook.construct_event",
                side_effect=stripe.SignatureVerificationError("bad sig", "sig_header"),
            ):
                with pytest.raises(stripe.SignatureVerificationError):
                    verify_webhook_signature(b"payload", "bad_sig")

    def test_missing_webhook_secret_raises_billing_error(self):
        with patch("app.services.billing._stripe_secrets", return_value={}):
            with pytest.raises(BillingError):
                verify_webhook_signature(b"payload", "sig")


# ── Webhook handlers ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_handle_checkout_completed_provisions_subscription():
    subscription = Subscription(
        user_id=uuid.uuid4(), tier=SubscriptionTier.free, status=SubscriptionStatus.active,
        stripe_customer_id="cus_1",
    )
    session = FakeSession(subscription)

    event_data = {
        "object": {
            "customer": "cus_1",
            "subscription": "sub_1",
            "metadata": {"tier": "pro", "interval": "annual"},
        }
    }
    await handle_checkout_completed(session, event_data)

    assert subscription.tier == SubscriptionTier.pro
    assert subscription.billing_interval == BillingInterval.annual
    assert subscription.status == SubscriptionStatus.active
    assert subscription.stripe_subscription_id == "sub_1"
    assert session.committed is True


@pytest.mark.asyncio
async def test_handle_checkout_completed_missing_metadata_is_noop():
    session = FakeSession(None)
    event_data = {"object": {"customer": "cus_1", "subscription": "sub_1", "metadata": {}}}
    await handle_checkout_completed(session, event_data)
    assert session.committed is False


@pytest.mark.asyncio
async def test_handle_payment_succeeded_sets_active_and_period_end():
    subscription = Subscription(
        user_id=uuid.uuid4(), tier=SubscriptionTier.pro, status=SubscriptionStatus.past_due,
        stripe_subscription_id="sub_1",
    )
    session = FakeSession(subscription)

    event_data = {
        "object": {
            "subscription": "sub_1",
            "lines": {"data": [{"period": {"end": 1735689600}}]},
        }
    }
    await handle_payment_succeeded(session, event_data)

    assert subscription.status == SubscriptionStatus.active
    assert subscription.current_period_end is not None
    assert session.committed is True


@pytest.mark.asyncio
async def test_handle_payment_failed_sets_past_due():
    subscription = Subscription(
        user_id=uuid.uuid4(), tier=SubscriptionTier.pro, status=SubscriptionStatus.active,
        stripe_subscription_id="sub_1",
    )
    session = FakeSession(subscription)

    event_data = {"object": {"subscription": "sub_1"}}
    await handle_payment_failed(session, event_data)

    assert subscription.status == SubscriptionStatus.past_due
    assert session.committed is True


@pytest.mark.asyncio
async def test_handle_subscription_updated_syncs_status_and_tier():
    subscription = Subscription(
        user_id=uuid.uuid4(), tier=SubscriptionTier.starter, status=SubscriptionStatus.active,
        stripe_subscription_id="sub_1",
    )
    session = FakeSession(subscription)

    event_data = {
        "object": {
            "id": "sub_1",
            "status": "past_due",
            "metadata": {"tier": "team", "interval": "monthly"},
            "current_period_end": 1735689600,
        }
    }
    await handle_subscription_updated(session, event_data)

    assert subscription.status == SubscriptionStatus.past_due
    assert subscription.tier == SubscriptionTier.team
    assert subscription.billing_interval == BillingInterval.monthly
    assert subscription.current_period_end is not None


@pytest.mark.asyncio
async def test_handle_subscription_deleted_reverts_to_free():
    subscription = Subscription(
        user_id=uuid.uuid4(), tier=SubscriptionTier.pro, status=SubscriptionStatus.active,
        billing_interval=BillingInterval.monthly, stripe_subscription_id="sub_1",
    )
    session = FakeSession(subscription)

    event_data = {"object": {"id": "sub_1"}}
    await handle_subscription_deleted(session, event_data)

    assert subscription.status == SubscriptionStatus.canceled
    assert subscription.tier == SubscriptionTier.free
    assert subscription.billing_interval is None
    assert session.committed is True


@pytest.mark.asyncio
async def test_handlers_are_noop_when_subscription_row_not_found():
    """Every handler must tolerate an unknown subscription id without raising."""
    session = FakeSession(None)
    await handle_payment_succeeded(session, {"object": {"subscription": "sub_ghost"}})
    await handle_payment_failed(session, {"object": {"subscription": "sub_ghost"}})
    await handle_subscription_updated(session, {"object": {"id": "sub_ghost"}})
    await handle_subscription_deleted(session, {"object": {"id": "sub_ghost"}})
    assert session.committed is False


# ── dispatch_webhook_event ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_dispatch_routes_known_event_type():
    subscription = Subscription(
        user_id=uuid.uuid4(), tier=SubscriptionTier.pro, status=SubscriptionStatus.active,
        stripe_subscription_id="sub_1",
    )
    session = FakeSession(subscription)

    event = {"type": "invoice.payment_failed", "data": {"object": {"subscription": "sub_1"}}}
    await dispatch_webhook_event(session, event)

    assert subscription.status == SubscriptionStatus.past_due


@pytest.mark.asyncio
async def test_dispatch_ignores_unknown_event_type():
    session = FakeSession()
    event = {"type": "some.unhandled.event", "data": {"object": {}}}
    await dispatch_webhook_event(session, event)  # must not raise
    assert session.committed is False
