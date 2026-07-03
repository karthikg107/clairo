"""
CLR-044 — Referral programme endpoints.

POST /api/v1/referrals/claim
  Authenticated. Called once after sign-up when a stored referrer id
  exists client-side. Records a PENDING referral — bonuses are granted
  later, when the referred user completes their first analysis.

GET /api/v1/referrals/stats
  Authenticated. Referral link + stats for the account settings page.
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.http import require_user
from app.db.session import get_db
from app.services.referrals import ReferralError, claim_referral, get_referral_stats

router = APIRouter(prefix="/referrals", tags=["referrals"])


class ClaimReferralRequest(BaseModel):
    referrer_user_id: uuid.UUID


@router.post("/claim", status_code=status.HTTP_204_NO_CONTENT)
async def claim_referral_endpoint(
    body: ClaimReferralRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> None:
    user = await require_user(request, db)
    try:
        await claim_referral(db, referred_user=user, referrer_user_id=body.referrer_user_id)
    except ReferralError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": exc.code},
        )


class ReferralStatsResponse(BaseModel):
    referral_path: str
    pending_count: int
    completed_count: int
    bonuses_earned: int
    max_bonuses: int
    bonus_analyses: int


@router.get("/stats", response_model=ReferralStatsResponse)
async def referral_stats_endpoint(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> ReferralStatsResponse:
    user = await require_user(request, db)
    stats = await get_referral_stats(db, user=user)
    return ReferralStatsResponse(**stats)
