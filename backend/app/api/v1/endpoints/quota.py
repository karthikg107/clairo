"""
CLR-025 — Free tier lifetime quota status.

GET /api/v1/quota — read-only check, does NOT consume quota.
Consumption happens automatically inside POST /api/v1/analyse after a
successful analysis (see app/api/v1/endpoints/analyse.py).

Lets the frontend show remaining-quota / upgrade messaging (e.g. before
the user even starts an upload) without needing to run an analysis first.
"""
from __future__ import annotations

from fastapi import APIRouter, Request
from pydantic import BaseModel

from app.core.http import get_clerk_id, get_client_ip
from app.services.quota import check_quota

router = APIRouter()


class QuotaResponse(BaseModel):
    allowed: bool
    is_free_tier: bool
    used: int
    limit: int
    remaining: int


@router.get(
    "/quota",
    response_model=QuotaResponse,
    tags=["quota"],
    summary="Check free-tier lifetime quota status",
)
async def quota_endpoint(request: Request) -> QuotaResponse:
    status = await check_quota(
        clerk_id=get_clerk_id(request),
        anonymous_id=request.headers.get("X-Anonymous-Id"),
        ip=get_client_ip(request),
    )
    return QuotaResponse(
        allowed=status.allowed,
        is_free_tier=status.is_free_tier,
        used=status.used,
        limit=status.limit,
        remaining=status.remaining,
    )
