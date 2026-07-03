"""
CLR-041 — Shareable analysis link endpoints.

POST /api/v1/share-links
  Authenticated. Creates (or returns the existing active) share link for
  one of the caller's own analyses. The frontend renders it as /s/[uuid].

POST /api/v1/share-links/{share_id}/revoke
  Authenticated. Instantly revokes the caller's own link.

GET /api/v1/shared/{share_id}
  PUBLIC (exempted from JWT auth in app/middleware/jwt_auth.py) — this is
  what the /s/[uuid] page fetches. Serves ONLY sanitized analysis output
  (see app/services/sharing.py) — never document text, OCR output, or
  user identity. Unknown, expired, and revoked links all return the same
  404 body, so callers can't distinguish them (anti-enumeration).

  Rate limits: 100 views/hour per link (checked here), plus a per-IP
  ceiling via the rate-limit middleware's share_view plane.
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.http import require_user
from app.core.rate_limit import check_endpoint_rate_limit
from app.db.session import get_db
from app.models.share_link import SHARE_LINK_TTL_DAYS
from app.services.sharing import (
    ShareLinkNotFoundError,
    SharingError,
    create_share_link,
    get_shared_analysis,
    revoke_share_link,
)

router = APIRouter(tags=["sharing"])

# One 404 body for unknown/expired/revoked — never reveals which (CLR-041/042).
_NOT_FOUND = HTTPException(
    status_code=status.HTTP_404_NOT_FOUND,
    detail={"error": "share_not_found", "message": "This link is no longer available."},
)


class CreateShareLinkRequest(BaseModel):
    analysis_id: uuid.UUID


class ShareLinkResponse(BaseModel):
    share_id: str
    share_path: str  # frontend prefixes its own origin → clairo.app/s/[uuid]
    expires_at: str
    ttl_days: int = SHARE_LINK_TTL_DAYS


@router.post("/share-links", response_model=ShareLinkResponse)
async def create_share_link_endpoint(
    body: CreateShareLinkRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> ShareLinkResponse:
    user = await require_user(request, db)
    try:
        link = await create_share_link(db, user=user, analysis_id=body.analysis_id)
    except SharingError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "analysis_not_found", "message": "Analysis not found."},
        )
    return ShareLinkResponse(
        share_id=str(link.id),
        share_path=f"/s/{link.id}",
        expires_at=link.expires_at.isoformat(),
    )


@router.post("/share-links/{share_id}/revoke", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_share_link_endpoint(
    share_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> None:
    user = await require_user(request, db)
    try:
        await revoke_share_link(db, user=user, share_id=share_id)
    except SharingError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "share_not_found", "message": "Share link not found."},
        )


@router.get("/shared/{share_id}")
async def shared_analysis_endpoint(
    share_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict:
    # CLR-041: 100 views/hour PER LINK — keyed by share id, not caller,
    # so one hot link can't be hammered regardless of how many IPs hit it.
    rate = await check_endpoint_rate_limit(
        identifier=str(share_id), endpoint="share_link", authenticated=False
    )
    if not rate.allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "error": "rate_limited",
                "message": "This link is being viewed too often. Try again shortly.",
            },
            headers={"Retry-After": str(rate.reset_in_seconds)},
        )

    try:
        payload = await get_shared_analysis(db, share_id=share_id)
    except ShareLinkNotFoundError:
        raise _NOT_FOUND

    return payload
