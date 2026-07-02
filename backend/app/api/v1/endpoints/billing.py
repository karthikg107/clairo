"""
CLR-026 — Stripe subscription billing endpoints.

POST /api/v1/billing/checkout-session
  Authenticated only. Starts a Stripe Checkout session for one of the
  three paid tiers (starter/pro/team) at monthly or annual billing.

GET /api/v1/billing/subscription
  Authenticated only. Returns the caller's current tier/status.

POST /api/v1/billing/webhook
  Called by Stripe, not the frontend — no Clerk JWT is present, so this
  path is exempted from JWTAuthMiddleware (see app/middleware/jwt_auth.py)
  and from rate limiting (see app/middleware/rate_limit.py). Authenticity
  is instead verified via the Stripe webhook signature.
"""
from __future__ import annotations

import stripe
import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.http import require_user
from app.db.session import get_db
from app.models.subscription import BillingInterval, Subscription, SubscriptionTier
from app.services.billing import (
    TIER_PRICING,
    BillingError,
    create_checkout_session,
    dispatch_webhook_event,
    verify_webhook_signature,
)

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/billing", tags=["billing"])

_PAID_TIER_STRINGS = {t.value for t in TIER_PRICING if t != SubscriptionTier.free}


class CheckoutSessionRequest(BaseModel):
    tier: str
    interval: str  # "monthly" | "annual"


class CheckoutSessionResponse(BaseModel):
    checkout_url: str


@router.post("/checkout-session", response_model=CheckoutSessionResponse)
async def checkout_session_endpoint(
    body: CheckoutSessionRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> CheckoutSessionResponse:
    if body.tier not in _PAID_TIER_STRINGS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"tier must be one of {sorted(_PAID_TIER_STRINGS)}",
        )
    try:
        interval = BillingInterval(body.interval)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="interval must be 'monthly' or 'annual'",
        )

    user = await require_user(request, db)
    settings = get_settings()

    try:
        checkout_url = await create_checkout_session(
            db,
            user=user,
            tier=SubscriptionTier(body.tier),
            interval=interval,
            success_url=f"{settings.frontend_base_url}/billing/success?session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{settings.frontend_base_url}/pricing",
        )
    except BillingError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"error": "checkout_failed", "message": str(exc)},
        )

    return CheckoutSessionResponse(checkout_url=checkout_url)


class SubscriptionResponse(BaseModel):
    tier: str
    status: str
    billing_interval: str | None


@router.get("/subscription", response_model=SubscriptionResponse)
async def subscription_endpoint(
    request: Request, db: AsyncSession = Depends(get_db)
) -> SubscriptionResponse:
    user = await require_user(request, db)
    result = await db.execute(select(Subscription).where(Subscription.user_id == user.id))
    subscription = result.scalar_one_or_none()

    if subscription is None:
        return SubscriptionResponse(tier="free", status="active", billing_interval=None)

    interval = subscription.billing_interval
    return SubscriptionResponse(
        tier=subscription.tier.value,
        status=subscription.status.value,
        billing_interval=interval.value if interval else None,
    )


@router.post("/webhook", status_code=status.HTTP_204_NO_CONTENT)
async def webhook_endpoint(request: Request, db: AsyncSession = Depends(get_db)) -> None:
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")

    try:
        event = verify_webhook_signature(payload, sig_header)
    except stripe.SignatureVerificationError:
        logger.warning("billing.webhook_invalid_signature")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid signature")
    except BillingError as exc:
        logger.error("billing.webhook_config_error", error=str(exc))
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))

    await dispatch_webhook_event(db, event)
