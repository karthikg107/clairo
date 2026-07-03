"""
CLR-044 — Referral programme.

Flow:
  1. clairo.app/ref/[userId] stores the referrer id client-side and sends
     the visitor to sign-up.
  2. After sign-up, the frontend claims the referral (POST /referrals/claim)
     → a PENDING Referral row. Nothing is granted yet.
  3. When the referred user completes their FIRST analysis, the pending row
     completes: both sides earn 1 bonus analysis. The referrer is capped at
     MAX_REFERRAL_BONUSES earned bonuses; the referred user's single bonus
     is unconditional on completion.

Bonus analyses extend the free-tier lifetime limit (see quota.py:
limit = FREE_LIFETIME_LIMIT + user.bonus_analyses).

Completion is best-effort from the analyse endpoint (own session, never
blocks or fails the analysis response) — same convention as
_persist_analysis (CLR-023).
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.db.session import get_session_factory
from app.models.referral import MAX_REFERRAL_BONUSES, Referral
from app.models.user import User

logger = get_logger(__name__)


class ReferralError(Exception):
    """Validation failure claiming a referral."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


async def claim_referral(
    db: AsyncSession, *, referred_user: User, referrer_user_id: uuid.UUID
) -> Referral:
    """
    Records a PENDING referral for a freshly signed-up user.

    Raises ReferralError with a code:
      self_referral   — you can't refer yourself
      invalid_referrer — no such user
      already_claimed  — this user was already referred
    """
    if referrer_user_id == referred_user.id:
        raise ReferralError("self_referral")

    referrer_result = await db.execute(select(User).where(User.id == referrer_user_id))
    if referrer_result.scalar_one_or_none() is None:
        raise ReferralError("invalid_referrer")

    existing_result = await db.execute(
        select(Referral).where(Referral.referred_user_id == referred_user.id)
    )
    if existing_result.scalar_one_or_none() is not None:
        raise ReferralError("already_claimed")

    referral = Referral(
        id=uuid.uuid4(),
        referrer_user_id=referrer_user_id,
        referred_user_id=referred_user.id,
    )
    db.add(referral)
    await db.commit()
    logger.info(
        "referrals.claimed",
        referrer_user_id=str(referrer_user_id),
        referred_user_id=str(referred_user.id),
    )
    return referral


async def _granted_bonus_count(db: AsyncSession, referrer_user_id: uuid.UUID) -> int:
    result = await db.execute(
        select(func.count())
        .select_from(Referral)
        .where(
            Referral.referrer_user_id == referrer_user_id,
            Referral.bonus_granted.is_(True),
        )
    )
    return int(result.scalar_one() or 0)


async def complete_pending_referral(db: AsyncSession, *, referred_user_id: uuid.UUID) -> bool:
    """
    Completes the referred user's pending referral, if any. Returns True
    if a referral was completed.

    Grants: referred user +1 bonus analysis (unconditional); referrer +1
    only while under MAX_REFERRAL_BONUSES earned bonuses.
    """
    referral_result = await db.execute(
        select(Referral).where(
            Referral.referred_user_id == referred_user_id,
            Referral.completed_at.is_(None),
        )
    )
    referral = referral_result.scalar_one_or_none()
    if referral is None:
        return False

    referred_result = await db.execute(
        select(User).where(User.id == referred_user_id)
    )
    referred = referred_result.scalar_one_or_none()

    referrer_result = await db.execute(
        select(User).where(User.id == referral.referrer_user_id)
    )
    referrer = referrer_result.scalar_one_or_none()

    referral.completed_at = datetime.now(UTC)

    if referred is not None:
        referred.bonus_analyses += 1

    if referrer is not None:
        earned = await _granted_bonus_count(db, referral.referrer_user_id)
        if earned < MAX_REFERRAL_BONUSES:
            referrer.bonus_analyses += 1
            referral.bonus_granted = True

    await db.commit()
    logger.info(
        "referrals.completed",
        referred_user_id=str(referred_user_id),
        referrer_bonus_granted=referral.bonus_granted,
    )
    return True


async def complete_referral_for_clerk_id(clerk_id: str | None) -> None:
    """
    Best-effort completion hook for the analyse endpoint — own session,
    never raises, never blocks the analysis response.
    """
    if not clerk_id:
        return
    try:
        factory = get_session_factory()
        async with factory() as session:
            user_result = await session.execute(
                select(User).where(User.clerk_id == clerk_id)
            )
            user = user_result.scalar_one_or_none()
            if user is None:
                return
            await complete_pending_referral(session, referred_user_id=user.id)
    except Exception as exc:
        logger.warning("referrals.completion_failed", error=str(exc))


async def get_referral_stats(db: AsyncSession, *, user: User) -> dict:
    """Stats for the account-settings referral section."""
    pending_result = await db.execute(
        select(func.count())
        .select_from(Referral)
        .where(
            Referral.referrer_user_id == user.id,
            Referral.completed_at.is_(None),
        )
    )
    completed_result = await db.execute(
        select(func.count())
        .select_from(Referral)
        .where(
            Referral.referrer_user_id == user.id,
            Referral.completed_at.is_not(None),
        )
    )
    granted = await _granted_bonus_count(db, user.id)

    return {
        "referral_path": f"/ref/{user.id}",
        "pending_count": int(pending_result.scalar_one() or 0),
        "completed_count": int(completed_result.scalar_one() or 0),
        "bonuses_earned": granted,
        "max_bonuses": MAX_REFERRAL_BONUSES,
        "bonus_analyses": user.bonus_analyses,
    }
