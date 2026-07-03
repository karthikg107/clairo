"""
CLR-029 — Subscription management and cancellation.

- GET /billing/subscription now returns current_period_end and
  cancel_at_period_end so the UI can show the renewal date and a
  "cancels on <date>" state.
- POST /billing/cancel schedules cancellation at period end via Stripe's
  cancel_at_period_end=True — access continues until the period ends.
- POST /billing/reactivate undoes a pending cancellation.
- GET /billing/invoices lists billing history with links to
  Stripe-hosted downloadable invoices.
- The customer.subscription.updated webhook syncs cancel_at_period_end;
  customer.subscription.deleted resets it.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import patch

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
    cancel_subscription,
    handle_subscription_deleted,
    handle_subscription_updated,
    list_invoices,
    reactivate_subscription,
)

STRIPE_SECRETS = {
    "secret_key": "sk_test_x",
    "webhook_secret": "whsec_test",
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


def _active_subscription(user: User, **overrides) -> Subscription:
    defaults: dict = {
        "user_id": user.id,
        "tier": SubscriptionTier.pro,
        "status": SubscriptionStatus.active,
        "billing_interval": BillingInterval.monthly,
        "stripe_customer_id": "cus_1",
        "stripe_subscription_id": "sub_existing",
        "current_period_end": datetime(2026, 8, 1, tzinfo=UTC),
    }
    defaults.update(overrides)
    return Subscription(**defaults)


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


# ── cancel_subscription (service) ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_cancel_sets_cancel_at_period_end_not_immediate_delete():
    user = _make_user()
    subscription = _active_subscription(user)
    session = FakeSession()

    with patch("app.services.billing._stripe_secrets", return_value=STRIPE_SECRETS):
        with patch("stripe.Subscription.modify") as mock_modify:
            with patch("stripe.Subscription.delete") as mock_delete:
                result = await cancel_subscription(
                    session, user=user, existing_subscription=subscription
                )

    # Access continues until period end: modify with cancel_at_period_end,
    # never an immediate delete/cancel.
    mock_delete.assert_not_called()
    assert mock_modify.call_args.args[0] == "sub_existing"
    assert mock_modify.call_args.kwargs["cancel_at_period_end"] is True

    assert result.cancel_at_period_end is True
    # Status stays active — the user keeps access until period end.
    assert result.status == SubscriptionStatus.active
    assert session.committed is True


@pytest.mark.asyncio
async def test_cancel_requires_existing_stripe_subscription():
    user = _make_user()
    subscription = _active_subscription(user, stripe_subscription_id=None)
    session = FakeSession()

    with pytest.raises(BillingError, match="No active subscription"):
        await cancel_subscription(session, user=user, existing_subscription=subscription)


@pytest.mark.asyncio
async def test_cancel_wraps_stripe_error():
    user = _make_user()
    subscription = _active_subscription(user)
    session = FakeSession()

    with patch("app.services.billing._stripe_secrets", return_value=STRIPE_SECRETS):
        with patch("stripe.Subscription.modify", side_effect=stripe.StripeError("boom")):
            with pytest.raises(BillingError):
                await cancel_subscription(
                    session, user=user, existing_subscription=subscription
                )

    # Local row must NOT be flipped if Stripe rejected the change.
    assert not subscription.cancel_at_period_end
    assert session.committed is False


# ── reactivate_subscription (service) ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_reactivate_clears_cancel_at_period_end():
    user = _make_user()
    subscription = _active_subscription(user, cancel_at_period_end=True)
    session = FakeSession()

    with patch("app.services.billing._stripe_secrets", return_value=STRIPE_SECRETS):
        with patch("stripe.Subscription.modify") as mock_modify:
            result = await reactivate_subscription(
                session, user=user, existing_subscription=subscription
            )

    assert mock_modify.call_args.args[0] == "sub_existing"
    assert mock_modify.call_args.kwargs["cancel_at_period_end"] is False
    assert result.cancel_at_period_end is False
    assert session.committed is True


@pytest.mark.asyncio
async def test_reactivate_rejected_when_not_pending_cancellation():
    user = _make_user()
    subscription = _active_subscription(user, cancel_at_period_end=False)
    session = FakeSession()

    with pytest.raises(BillingError, match="not scheduled for cancellation"):
        await reactivate_subscription(
            session, user=user, existing_subscription=subscription
        )


# ── list_invoices (service) ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_invoices_maps_stripe_fields():
    user = _make_user()
    subscription = _active_subscription(user)
    session = FakeSession()

    stripe_invoices = {
        "data": [
            {
                "id": "in_1",
                "status": "paid",
                "amount_paid": 1900,
                "currency": "usd",
                "created": 1751328000,  # 2025-07-01 00:00:00 UTC
                "hosted_invoice_url": "https://invoice.stripe.com/i/in_1",
                "invoice_pdf": "https://pay.stripe.com/invoice/in_1/pdf",
            }
        ]
    }

    with patch("app.services.billing._stripe_secrets", return_value=STRIPE_SECRETS):
        with patch("stripe.Invoice.list", return_value=stripe_invoices) as mock_list:
            invoices = await list_invoices(
                session, user=user, existing_subscription=subscription
            )

    assert mock_list.call_args.kwargs["customer"] == "cus_1"
    assert len(invoices) == 1
    inv = invoices[0]
    assert inv.id == "in_1"
    assert inv.status == "paid"
    assert str(inv.amount_paid) == "19"
    assert inv.currency == "USD"
    assert inv.invoice_pdf == "https://pay.stripe.com/invoice/in_1/pdf"


@pytest.mark.asyncio
async def test_list_invoices_empty_without_stripe_customer():
    user = _make_user()
    subscription = _active_subscription(user, stripe_customer_id=None)
    session = FakeSession()

    invoices = await list_invoices(session, user=user, existing_subscription=subscription)
    assert invoices == []


# ── webhook sync of cancel_at_period_end ───────────────────────────────────────

@pytest.mark.asyncio
async def test_subscription_updated_webhook_syncs_cancel_flag():
    user = _make_user()
    subscription = _active_subscription(user)
    session = FakeSession(subscription)

    event_data = {
        "object": {
            "id": "sub_existing",
            "status": "active",
            "cancel_at_period_end": True,
            "current_period_end": 1754006400,
            "metadata": {},
        }
    }
    await handle_subscription_updated(session, event_data)

    assert subscription.cancel_at_period_end is True
    assert session.committed is True


@pytest.mark.asyncio
async def test_subscription_deleted_webhook_resets_cancel_flag():
    user = _make_user()
    subscription = _active_subscription(user, cancel_at_period_end=True)
    session = FakeSession(subscription)

    event_data = {"object": {"id": "sub_existing"}}
    await handle_subscription_deleted(session, event_data)

    assert subscription.cancel_at_period_end is False
    assert subscription.tier == SubscriptionTier.free
    assert subscription.status == SubscriptionStatus.canceled


# ── endpoints ──────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_subscription_endpoint_includes_renewal_and_cancel_fields(client):
    user = _make_user()
    subscription = _active_subscription(user, cancel_at_period_end=True)
    _override_db(FakeSession(user, subscription))

    r = await client.get(
        "/api/v1/billing/subscription", headers={"X-Clerk-User-Id": "user_abc"}
    )

    assert r.status_code == 200
    body = r.json()
    assert body["tier"] == "pro"
    assert body["current_period_end"] == "2026-08-01T00:00:00+00:00"
    assert body["cancel_at_period_end"] is True


@pytest.mark.asyncio
async def test_cancel_endpoint_returns_updated_subscription(client):
    user = _make_user()
    subscription = _active_subscription(user)
    _override_db(FakeSession(user, subscription))

    with patch("app.services.billing._stripe_secrets", return_value=STRIPE_SECRETS):
        with patch("stripe.Subscription.modify") as mock_modify:
            r = await client.post(
                "/api/v1/billing/cancel", headers={"X-Clerk-User-Id": "user_abc"}
            )

    assert r.status_code == 200
    body = r.json()
    assert body["cancel_at_period_end"] is True
    assert body["status"] == "active"  # access until period end
    assert mock_modify.call_args.kwargs["cancel_at_period_end"] is True


@pytest.mark.asyncio
async def test_cancel_endpoint_without_subscription_returns_400(client):
    user = _make_user()
    _override_db(FakeSession(user, None))

    r = await client.post(
        "/api/v1/billing/cancel", headers={"X-Clerk-User-Id": "user_abc"}
    )

    assert r.status_code == 400
    assert r.json()["detail"]["error"] == "cancel_failed"


@pytest.mark.asyncio
async def test_reactivate_endpoint_clears_pending_cancellation(client):
    user = _make_user()
    subscription = _active_subscription(user, cancel_at_period_end=True)
    _override_db(FakeSession(user, subscription))

    with patch("app.services.billing._stripe_secrets", return_value=STRIPE_SECRETS):
        with patch("stripe.Subscription.modify"):
            r = await client.post(
                "/api/v1/billing/reactivate", headers={"X-Clerk-User-Id": "user_abc"}
            )

    assert r.status_code == 200
    assert r.json()["cancel_at_period_end"] is False


@pytest.mark.asyncio
async def test_reactivate_endpoint_without_pending_cancellation_returns_400(client):
    user = _make_user()
    subscription = _active_subscription(user, cancel_at_period_end=False)
    _override_db(FakeSession(user, subscription))

    r = await client.post(
        "/api/v1/billing/reactivate", headers={"X-Clerk-User-Id": "user_abc"}
    )

    assert r.status_code == 400
    assert r.json()["detail"]["error"] == "reactivate_failed"


@pytest.mark.asyncio
async def test_invoices_endpoint_returns_billing_history(client):
    user = _make_user()
    subscription = _active_subscription(user)
    _override_db(FakeSession(user, subscription))

    stripe_invoices = {
        "data": [
            {
                "id": "in_1",
                "status": "paid",
                "amount_paid": 700,
                "currency": "usd",
                "created": 1751328000,
                "hosted_invoice_url": "https://invoice.stripe.com/i/in_1",
                "invoice_pdf": "https://pay.stripe.com/invoice/in_1/pdf",
            },
            {
                "id": "in_2",
                "status": "open",
                "amount_paid": 0,
                "currency": "usd",
                "created": 1748736000,
                "hosted_invoice_url": None,
                "invoice_pdf": None,
            },
        ]
    }

    with patch("app.services.billing._stripe_secrets", return_value=STRIPE_SECRETS):
        with patch("stripe.Invoice.list", return_value=stripe_invoices):
            r = await client.get(
                "/api/v1/billing/invoices", headers={"X-Clerk-User-Id": "user_abc"}
            )

    assert r.status_code == 200
    body = r.json()
    assert len(body) == 2
    assert body[0]["id"] == "in_1"
    assert body[0]["amount_paid"] == "7"
    assert body[0]["invoice_pdf"] == "https://pay.stripe.com/invoice/in_1/pdf"
    assert body[1]["invoice_pdf"] is None


@pytest.mark.asyncio
async def test_invoices_endpoint_free_user_gets_empty_list(client):
    user = _make_user()
    _override_db(FakeSession(user, None))

    r = await client.get(
        "/api/v1/billing/invoices", headers={"X-Clerk-User-Id": "user_abc"}
    )

    assert r.status_code == 200
    assert r.json() == []


@pytest.mark.asyncio
async def test_invoices_endpoint_stripe_error_returns_502(client):
    user = _make_user()
    subscription = _active_subscription(user)
    _override_db(FakeSession(user, subscription))

    with patch("app.services.billing._stripe_secrets", return_value=STRIPE_SECRETS):
        with patch("stripe.Invoice.list", side_effect=stripe.StripeError("boom")):
            r = await client.get(
                "/api/v1/billing/invoices", headers={"X-Clerk-User-Id": "user_abc"}
            )

    assert r.status_code == 502
    assert r.json()["detail"]["error"] == "invoices_failed"
