"""
CLR-026 — Stripe subscription billing.

Four tiers: free, starter ($7/mo), pro ($19/mo), team ($49/mo). Each paid
tier has a monthly and an annual variant — annual is 25% off the
monthly-equivalent yearly total (12 * monthly * 0.75).

Stripe Price IDs are looked up from AWS Secrets Manager (clairo/stripe)
rather than hardcoded — they're created once per Stripe account (via
Dashboard or `stripe prices create`) and referenced here by id.

SECURITY:
- The Stripe secret key is fetched from Secrets Manager per call and
  passed explicitly as api_key= to every Stripe call — never assigned
  to the global `stripe.api_key`, so it's never accidentally shared
  across requests/tests.
- Webhook payloads are verified via stripe.Webhook.construct_event()
  using the webhook secret from Secrets Manager before any DB write —
  an invalid/missing signature is rejected outright.
- Never logs card data, customer PII beyond what Stripe already has,
  or document content (billing has no access to document content).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import stripe
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.core.secrets import get_secret
from app.models.subscription import (
    BillingInterval,
    Subscription,
    SubscriptionStatus,
    SubscriptionTier,
)
from app.models.user import User

logger = get_logger(__name__)

PAID_TIERS: tuple[SubscriptionTier, ...] = (
    SubscriptionTier.starter,
    SubscriptionTier.pro,
    SubscriptionTier.team,
)

# 25% off the yearly-equivalent total when billed annually.
ANNUAL_DISCOUNT_PCT = Decimal("0.25")


def _annual_total(monthly_usd: Decimal) -> Decimal:
    return (monthly_usd * 12 * (1 - ANNUAL_DISCOUNT_PCT)).quantize(Decimal("0.01"))


@dataclass(frozen=True)
class TierPricing:
    tier: SubscriptionTier
    monthly_usd: Decimal
    annual_usd: Decimal          # total for the year, not a monthly-equivalent
    monthly_price_lookup: str | None   # key into the clairo/stripe secret
    annual_price_lookup: str | None


TIER_PRICING: dict[SubscriptionTier, TierPricing] = {
    SubscriptionTier.free: TierPricing(
        tier=SubscriptionTier.free,
        monthly_usd=Decimal("0"),
        annual_usd=Decimal("0"),
        monthly_price_lookup=None,
        annual_price_lookup=None,
    ),
    SubscriptionTier.starter: TierPricing(
        tier=SubscriptionTier.starter,
        monthly_usd=Decimal("7"),
        annual_usd=_annual_total(Decimal("7")),
        monthly_price_lookup="price_starter_monthly",
        annual_price_lookup="price_starter_annual",
    ),
    SubscriptionTier.pro: TierPricing(
        tier=SubscriptionTier.pro,
        monthly_usd=Decimal("19"),
        annual_usd=_annual_total(Decimal("19")),
        monthly_price_lookup="price_pro_monthly",
        annual_price_lookup="price_pro_annual",
    ),
    SubscriptionTier.team: TierPricing(
        tier=SubscriptionTier.team,
        monthly_usd=Decimal("49"),
        annual_usd=_annual_total(Decimal("49")),
        monthly_price_lookup="price_team_monthly",
        annual_price_lookup="price_team_annual",
    ),
}


class BillingError(Exception):
    """Raised for any Stripe-side or configuration failure creating a checkout session."""


def _stripe_secrets() -> dict[str, str]:
    return get_secret("clairo/stripe")


def _price_id_for(tier: SubscriptionTier, interval: BillingInterval) -> str:
    pricing = TIER_PRICING[tier]
    key = (
        pricing.monthly_price_lookup
        if interval == BillingInterval.monthly
        else pricing.annual_price_lookup
    )
    if key is None:
        raise BillingError(f"Tier {tier.value!r} has no price (free tier is not purchasable)")

    price_id = _stripe_secrets().get(key, "")
    if not price_id:
        raise BillingError(f"Stripe price id not configured for {tier.value}/{interval.value}")
    return price_id


async def _get_or_create_stripe_customer(
    db: AsyncSession,
    user: User,
    *,
    api_key: str,
    existing_subscription: Subscription | None = None,
) -> str:
    """
    Returns the Stripe customer id, creating one on first use.

    Accepts an already-fetched `existing_subscription` so callers that have
    already looked up the row (e.g. the checkout-session endpoint, deciding
    between a new Checkout session and an in-place tier change) don't pay
    for a second identical query.
    """
    if existing_subscription is not None:
        subscription = existing_subscription
    else:
        result = await db.execute(select(Subscription).where(Subscription.user_id == user.id))
        subscription = result.scalar_one_or_none()

    if subscription is not None and subscription.stripe_customer_id:
        return subscription.stripe_customer_id

    customer = stripe.Customer.create(
        email=user.email,
        metadata={"clerk_id": user.clerk_id, "user_id": str(user.id)},
        api_key=api_key,
    )

    if subscription is None:
        subscription = Subscription(
            user_id=user.id,
            tier=SubscriptionTier.free,
            status=SubscriptionStatus.active,
            stripe_customer_id=customer.id,
        )
        db.add(subscription)
    else:
        subscription.stripe_customer_id = customer.id

    await db.commit()
    return customer.id


async def create_checkout_session(
    db: AsyncSession,
    *,
    user: User,
    tier: SubscriptionTier,
    interval: BillingInterval,
    success_url: str,
    cancel_url: str,
    existing_subscription: Subscription | None = None,
) -> str:
    """Creates a Stripe Checkout Session for the given tier/interval and returns its URL."""
    if tier not in PAID_TIERS:
        raise BillingError(f"Cannot check out for tier {tier.value!r}")

    secrets = _stripe_secrets()
    api_key = secrets.get("secret_key", "")
    if not api_key:
        raise BillingError("Stripe secret key not configured")

    price_id = _price_id_for(tier, interval)
    customer_id = await _get_or_create_stripe_customer(
        db, user, api_key=api_key, existing_subscription=existing_subscription
    )

    try:
        session = stripe.checkout.Session.create(
            customer=customer_id,
            mode="subscription",
            line_items=[{"price": price_id, "quantity": 1}],
            success_url=success_url,
            cancel_url=cancel_url,
            metadata={
                "user_id": str(user.id),
                "tier": tier.value,
                "interval": interval.value,
            },
            api_key=api_key,
        )
    except stripe.StripeError as exc:
        logger.error("billing.checkout_session_failed", error=str(exc))
        raise BillingError("Could not start checkout") from exc

    if not session.url:
        raise BillingError("Stripe did not return a checkout URL")
    return session.url


async def change_subscription_tier(
    db: AsyncSession,
    *,
    user: User,
    tier: SubscriptionTier,
    interval: BillingInterval,
    existing_subscription: Subscription | None = None,
) -> None:
    """
    CLR-028 — For a user who ALREADY has an active Stripe subscription,
    changes their tier/interval in place rather than starting a second
    Checkout session (which would create a second, parallel subscription).

    Uses proration_behavior="create_prorations" so Stripe automatically
    credits/charges the difference for the remainder of the current
    billing period — this is what "prorated upgrades handled by Stripe"
    means in practice: we don't compute proration ourselves, Stripe does.

    The local `subscriptions` row is updated optimistically so the UI
    reflects the change immediately; the customer.subscription.updated
    webhook will also sync it shortly after (belt and suspenders — the
    two must never meaningfully disagree since both derive from the same
    Stripe subscription object).

    Accepts an already-fetched `existing_subscription` for the same reason
    as create_checkout_session — avoids a second identical query when the
    caller (the checkout-session endpoint) has already looked the row up.
    """
    if tier not in PAID_TIERS:
        raise BillingError(f"Cannot change to tier {tier.value!r}")

    if existing_subscription is not None:
        subscription = existing_subscription
    else:
        result = await db.execute(select(Subscription).where(Subscription.user_id == user.id))
        subscription = result.scalar_one_or_none()

    if subscription is None or not subscription.stripe_subscription_id:
        raise BillingError("No active subscription to change")

    secrets = _stripe_secrets()
    api_key = secrets.get("secret_key", "")
    if not api_key:
        raise BillingError("Stripe secret key not configured")

    price_id = _price_id_for(tier, interval)

    try:
        stripe_sub = stripe.Subscription.retrieve(
            subscription.stripe_subscription_id, api_key=api_key
        )
        item_id = stripe_sub["items"]["data"][0]["id"]

        stripe.Subscription.modify(
            subscription.stripe_subscription_id,
            items=[{"id": item_id, "price": price_id}],
            proration_behavior="create_prorations",
            metadata={"tier": tier.value, "interval": interval.value},
            api_key=api_key,
        )
    except stripe.StripeError as exc:
        logger.error("billing.change_tier_failed", error=str(exc))
        raise BillingError("Could not change subscription tier") from exc

    subscription.tier = tier
    subscription.billing_interval = interval
    await db.commit()
    logger.info("billing.tier_changed", tier=tier.value, interval=interval.value)


# ── Webhook event handling ─────────────────────────────────────────────────────

def verify_webhook_signature(payload: bytes, sig_header: str) -> dict[str, Any]:
    """
    Verifies the Stripe webhook signature and returns the parsed event.
    Raises stripe.SignatureVerificationError on an invalid/missing signature.
    """
    secrets = _stripe_secrets()
    webhook_secret = secrets.get("webhook_secret", "")
    if not webhook_secret:
        raise BillingError("Stripe webhook secret not configured")

    event = stripe.Webhook.construct_event(payload, sig_header, webhook_secret)
    return event


async def _get_subscription_by_stripe_id(
    db: AsyncSession, stripe_subscription_id: str
) -> Subscription | None:
    result = await db.execute(
        select(Subscription).where(Subscription.stripe_subscription_id == stripe_subscription_id)
    )
    return result.scalar_one_or_none()


async def _get_subscription_by_customer_id(
    db: AsyncSession, stripe_customer_id: str
) -> Subscription | None:
    result = await db.execute(
        select(Subscription).where(Subscription.stripe_customer_id == stripe_customer_id)
    )
    return result.scalar_one_or_none()


def _period_end_from_timestamp(ts: int | None) -> datetime | None:
    if ts is None:
        return None
    return datetime.fromtimestamp(ts, tz=UTC)


def _invoice_period_end(invoice: dict[str, Any]) -> int | None:
    """Stripe nests the billing period under lines.data[0].period.end."""
    lines = (invoice.get("lines") or {}).get("data") or []
    if not lines:
        return None
    return (lines[0].get("period") or {}).get("end")


def _tier_from_metadata(metadata: dict[str, str]) -> SubscriptionTier | None:
    raw = metadata.get("tier")
    if raw is None:
        return None
    try:
        return SubscriptionTier(raw)
    except ValueError:
        return None


def _interval_from_metadata(metadata: dict[str, str]) -> BillingInterval | None:
    raw = metadata.get("interval")
    if raw is None:
        return None
    try:
        return BillingInterval(raw)
    except ValueError:
        return None


async def handle_checkout_completed(db: AsyncSession, event_data: dict[str, Any]) -> None:
    """checkout.session.completed — provisions the subscription for the first time."""
    session = event_data["object"]
    customer_id = session.get("customer")
    stripe_subscription_id = session.get("subscription")
    metadata = session.get("metadata") or {}

    tier = _tier_from_metadata(metadata)
    interval = _interval_from_metadata(metadata)
    if tier is None or interval is None or not customer_id:
        logger.warning("billing.checkout_completed_missing_metadata", metadata=metadata)
        return

    subscription = await _get_subscription_by_customer_id(db, customer_id)
    if subscription is None:
        logger.warning("billing.checkout_completed_no_subscription_row", customer_id=customer_id)
        return

    subscription.tier = tier
    subscription.billing_interval = interval
    subscription.status = SubscriptionStatus.active
    subscription.stripe_subscription_id = stripe_subscription_id
    await db.commit()
    logger.info("billing.checkout_completed", tier=tier.value, interval=interval.value)


async def handle_payment_succeeded(db: AsyncSession, event_data: dict[str, Any]) -> None:
    """invoice.payment_succeeded — keeps the subscription active, refreshes period end."""
    invoice = event_data["object"]
    stripe_subscription_id = invoice.get("subscription")
    if not stripe_subscription_id:
        return

    subscription = await _get_subscription_by_stripe_id(db, stripe_subscription_id)
    if subscription is None:
        logger.warning("billing.payment_succeeded_no_subscription_row")
        return

    subscription.status = SubscriptionStatus.active
    period_end = _period_end_from_timestamp(_invoice_period_end(invoice))
    if period_end is not None:
        subscription.current_period_end = period_end
    await db.commit()
    logger.info("billing.payment_succeeded", subscription_id=stripe_subscription_id)


async def handle_payment_failed(db: AsyncSession, event_data: dict[str, Any]) -> None:
    """invoice.payment_failed — flags the subscription as past_due."""
    invoice = event_data["object"]
    stripe_subscription_id = invoice.get("subscription")
    if not stripe_subscription_id:
        return

    subscription = await _get_subscription_by_stripe_id(db, stripe_subscription_id)
    if subscription is None:
        logger.warning("billing.payment_failed_no_subscription_row")
        return

    subscription.status = SubscriptionStatus.past_due
    await db.commit()
    logger.warning("billing.payment_failed", subscription_id=stripe_subscription_id)


async def handle_subscription_updated(db: AsyncSession, event_data: dict[str, Any]) -> None:
    """customer.subscription.updated — syncs status/period end, and tier/interval if changed."""
    stripe_sub = event_data["object"]
    stripe_subscription_id = stripe_sub.get("id")
    if not stripe_subscription_id:
        return

    subscription = await _get_subscription_by_stripe_id(db, stripe_subscription_id)
    if subscription is None:
        logger.warning("billing.subscription_updated_no_subscription_row")
        return

    status_map = {
        "active": SubscriptionStatus.active,
        "canceled": SubscriptionStatus.canceled,
        "past_due": SubscriptionStatus.past_due,
        "trialing": SubscriptionStatus.trialing,
        "unpaid": SubscriptionStatus.unpaid,
    }
    stripe_status = stripe_sub.get("status", "")
    if stripe_status in status_map:
        subscription.status = status_map[stripe_status]

    metadata = stripe_sub.get("metadata") or {}
    tier = _tier_from_metadata(metadata)
    interval = _interval_from_metadata(metadata)
    if tier is not None:
        subscription.tier = tier
    if interval is not None:
        subscription.billing_interval = interval

    period_end = _period_end_from_timestamp(stripe_sub.get("current_period_end"))
    if period_end is not None:
        subscription.current_period_end = period_end

    await db.commit()
    logger.info("billing.subscription_updated", subscription_id=stripe_subscription_id)


async def handle_subscription_deleted(db: AsyncSession, event_data: dict[str, Any]) -> None:
    """customer.subscription.deleted — cancellation; reverts the user to the free tier."""
    stripe_sub = event_data["object"]
    stripe_subscription_id = stripe_sub.get("id")
    if not stripe_subscription_id:
        return

    subscription = await _get_subscription_by_stripe_id(db, stripe_subscription_id)
    if subscription is None:
        logger.warning("billing.subscription_deleted_no_subscription_row")
        return

    subscription.status = SubscriptionStatus.canceled
    subscription.tier = SubscriptionTier.free
    subscription.billing_interval = None
    await db.commit()
    logger.info("billing.subscription_deleted", subscription_id=stripe_subscription_id)


_EVENT_HANDLERS = {
    "checkout.session.completed": handle_checkout_completed,
    "invoice.payment_succeeded": handle_payment_succeeded,
    "invoice.payment_failed": handle_payment_failed,
    "customer.subscription.updated": handle_subscription_updated,
    "customer.subscription.deleted": handle_subscription_deleted,
}


async def dispatch_webhook_event(db: AsyncSession, event: dict[str, Any]) -> None:
    """Routes a verified Stripe event to its handler. Unhandled event types are ignored."""
    event_type = event.get("type", "")
    handler = _EVENT_HANDLERS.get(event_type)
    if handler is None:
        logger.info("billing.webhook_ignored", event_type=event_type)
        return

    await handler(db, event["data"])
