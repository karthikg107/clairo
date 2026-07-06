"""
CLR-024 — Account settings and GDPR data deletion/export.

GET /api/v1/account
  Authenticated. Returns email, subscription tier, member-since date,
  and saved language preferences.

PATCH /api/v1/account/language-preferences
  Authenticated. Updates the saved doc_language/output_language/country.

GET /api/v1/account/export
  Authenticated. GDPR data-portability export — every row this account
  owns, as JSON.

  HARD RULE: the exact scope of "all data held about a user" is a legal
  determination. This export includes the account row, subscription
  status, analyses, and this account's own audit log entries, but
  excludes raw Stripe identifiers (stripe_customer_id etc. — internal
  operational references, not data collected from the user). This
  scope requires legal review before launch, same as other
  compliance-sensitive content in this codebase (see the system prompt
  in app/services/analysis.py for the established convention).

POST /api/v1/account/delete
  Authenticated. Requires {"confirmation": "DELETE"} in the body —
  mirrors the frontend's typed-confirmation gate so the check isn't
  purely a client-side affordance. Calls the gdpr_delete_user()
  Postgres function (defined in the initial migration): a synchronous
  cascading DELETE of subscriptions/analyses and a SET NULL on this
  account's audit_log rows. "Full deletion within 30 seconds" is
  satisfied trivially — deletion is complete before this endpoint
  returns a response.
"""
from __future__ import annotations

from datetime import datetime

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.http import require_user
from app.db.session import get_db
from app.models.analysis import Analysis
from app.models.audit_log import AuditLog
from app.models.referral import Referral
from app.models.share_link import ShareLink
from app.models.subscription import Subscription
from app.models.user import User
from app.services.clerk import delete_clerk_user

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/account", tags=["account"])

_LANGUAGE_PATTERN = r"^[a-z]{2}(-[a-zA-Z]{2,4})?$"
_COUNTRY_PATTERN = r"^[A-Z]{2}$"


async def _current_tier(db: AsyncSession, user: User) -> str:
    result = await db.execute(select(Subscription).where(Subscription.user_id == user.id))
    subscription = result.scalar_one_or_none()
    return subscription.tier.value if subscription else "free"


class AccountResponse(BaseModel):
    email: str
    subscription_tier: str
    member_since: datetime
    doc_language: str | None
    output_language: str | None
    country: str | None


def _account_response(user: User, tier: str) -> AccountResponse:
    return AccountResponse(
        email=user.email,
        subscription_tier=tier,
        member_since=user.created_at,
        doc_language=user.doc_language,
        output_language=user.output_language,
        country=user.country,
    )


@router.get("", response_model=AccountResponse)
async def get_account(request: Request, db: AsyncSession = Depends(get_db)) -> AccountResponse:
    user = await require_user(request, db)
    tier = await _current_tier(db, user)
    return _account_response(user, tier)


class LanguagePreferencesRequest(BaseModel):
    doc_language: str = Field(..., pattern=_LANGUAGE_PATTERN)
    output_language: str = Field(..., pattern=_LANGUAGE_PATTERN)
    country: str = Field(..., pattern=_COUNTRY_PATTERN)


@router.patch("/language-preferences", response_model=AccountResponse)
async def update_language_preferences(
    body: LanguagePreferencesRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> AccountResponse:
    user = await require_user(request, db)
    user.doc_language = body.doc_language
    user.output_language = body.output_language
    user.country = body.country
    await db.commit()
    await db.refresh(user)

    tier = await _current_tier(db, user)
    return _account_response(user, tier)


class DataExportResponse(BaseModel):
    user: dict
    subscription: dict | None
    analyses: list[dict]
    # CLR-055 — features added after CLR-024, kept in the export so
    # "all stored data" stays true as the product grows
    share_links: list[dict]
    referrals: list[dict]
    audit_log: list[dict]


@router.get("/export", response_model=DataExportResponse)
async def export_account_data(
    request: Request, db: AsyncSession = Depends(get_db)
) -> DataExportResponse:
    user = await require_user(request, db)

    sub_result = await db.execute(select(Subscription).where(Subscription.user_id == user.id))
    subscription = sub_result.scalar_one_or_none()

    analyses_result = await db.execute(
        select(Analysis).where(Analysis.user_id == user.id).order_by(Analysis.created_at.desc())
    )
    analyses = analyses_result.scalars().all()

    audit_result = await db.execute(
        select(AuditLog).where(AuditLog.user_id == user.id).order_by(AuditLog.created_at.desc())
    )
    audit_rows = audit_result.scalars().all()

    # CLR-055 — share links for this user's analyses
    share_links_result = await db.execute(
        select(ShareLink)
        .join(Analysis, ShareLink.analysis_id == Analysis.id)
        .where(Analysis.user_id == user.id)
        .order_by(ShareLink.created_at.desc())
    )
    share_links = share_links_result.scalars().all()

    # CLR-055 — referrals where this user is either side. The OTHER user's
    # id is not exported (it's someone else's personal data) — only the
    # role, state, and dates.
    referrals_result = await db.execute(
        select(Referral).where(
            (Referral.referrer_user_id == user.id)
            | (Referral.referred_user_id == user.id)
        )
    )
    referral_rows = referrals_result.scalars().all()

    return DataExportResponse(
        user={
            "id": str(user.id),
            "clerk_id": user.clerk_id,
            "email": user.email,
            "tos_accepted_at": user.tos_accepted_at.isoformat() if user.tos_accepted_at else None,
            "tos_version": user.tos_version,
            "doc_language": user.doc_language,
            "output_language": user.output_language,
            "country": user.country,
            "free_analyses_used": user.free_analyses_used,
            "bonus_analyses": user.bonus_analyses,
            "created_at": user.created_at.isoformat(),
        },
        subscription=(
            {
                "tier": subscription.tier.value,
                "status": subscription.status.value,
                "billing_interval": (
                    subscription.billing_interval.value if subscription.billing_interval else None
                ),
                "current_period_end": (
                    subscription.current_period_end.isoformat()
                    if subscription.current_period_end
                    else None
                ),
                "created_at": subscription.created_at.isoformat(),
            }
            if subscription is not None
            else None
        ),
        analyses=[
            {
                "id": str(a.id),
                "document_type": a.document_type.value,
                "doc_language": a.doc_language,
                "output_language": a.output_language,
                "result_json": a.result_json,
                "created_at": a.created_at.isoformat(),
            }
            for a in analyses
        ],
        share_links=[
            {
                "id": str(link.id),
                "analysis_id": str(link.analysis_id),
                "expires_at": link.expires_at.isoformat(),
                "is_revoked": link.is_revoked,
                "created_at": link.created_at.isoformat(),
            }
            for link in share_links
        ],
        referrals=[
            {
                "role": "referrer" if r.referrer_user_id == user.id else "referred",
                "completed_at": r.completed_at.isoformat() if r.completed_at else None,
                "bonus_granted_to_referrer": r.bonus_granted,
                "created_at": r.created_at.isoformat(),
            }
            for r in referral_rows
        ],
        audit_log=[
            {
                "action": a.action,
                "metadata": a.metadata_json,
                "created_at": a.created_at.isoformat(),
            }
            for a in audit_rows
        ],
    )


class DeleteAccountRequest(BaseModel):
    confirmation: str


@router.post("/delete", status_code=status.HTTP_204_NO_CONTENT)
async def delete_account(
    body: DeleteAccountRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> None:
    if body.confirmation != "DELETE":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Type DELETE to confirm account deletion.",
        )

    user = await require_user(request, db)
    user_id = str(user.id)
    clerk_id = user.clerk_id  # capture before the row is deleted

    await db.execute(text("SELECT gdpr_delete_user(:uid)"), {"uid": user_id})
    await db.commit()

    # Security hardening item 6: revoke ALL of the user's sessions by
    # deleting the Clerk user (best-effort — never blocks the deletion).
    await delete_clerk_user(clerk_id)

    logger.info("account.deleted", user_id=user_id)
