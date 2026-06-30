"""
CLR-022 — TOS / consent endpoint.

GET  /api/v1/consent   → returns whether current user has accepted current TOS
POST /api/v1/consent   → records acceptance; idempotent (re-POSTing is safe)

SECURITY:
- Requires valid Clerk JWT (enforced by JWTMiddleware, CLR-031)
- clerk_id extracted from verified token — never trusted from request body
- tos_accepted_at is set once; subsequent POSTs are no-ops (idempotent)
- Acceptance recorded in audit_log (write-only)
- No document content involved here
"""
from datetime import datetime, timezone

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.audit_log import AuditLog
from app.models.user import User, CURRENT_TOS_VERSION

logger = structlog.get_logger(__name__)

router = APIRouter(tags=["consent"])


class ConsentStatusResponse(BaseModel):
    has_accepted: bool
    tos_version: str | None
    current_version: str


class ConsentAcceptRequest(BaseModel):
    tos_version: str  # client sends version it showed; we validate it matches current


class ConsentAcceptResponse(BaseModel):
    accepted: bool
    tos_version: str
    accepted_at: datetime


def _get_clerk_id(request: Request) -> str:
    """
    Extract clerk_id from request state (set by JWTMiddleware, CLR-031).
    Until CLR-031 lands, falls back to X-Clerk-User-Id header (dev only).
    """
    clerk_id: str | None = getattr(request.state, "clerk_id", None)
    if not clerk_id:
        # Dev fallback — CLR-031 middleware will populate request.state.clerk_id
        clerk_id = request.headers.get("X-Clerk-User-Id")
    if not clerk_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )
    return clerk_id


@router.get("/consent", response_model=ConsentStatusResponse)
async def get_consent_status(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> ConsentStatusResponse:
    clerk_id = _get_clerk_id(request)

    result = await db.execute(select(User).where(User.clerk_id == clerk_id))
    user: User | None = result.scalar_one_or_none()

    if user is None:
        # User exists in Clerk but not yet in our DB — treat as not accepted
        return ConsentStatusResponse(
            has_accepted=False,
            tos_version=None,
            current_version=CURRENT_TOS_VERSION,
        )

    return ConsentStatusResponse(
        has_accepted=user.has_accepted_current_tos,
        tos_version=user.tos_version,
        current_version=CURRENT_TOS_VERSION,
    )


@router.post("/consent", response_model=ConsentAcceptResponse, status_code=status.HTTP_200_OK)
async def accept_consent(
    payload: ConsentAcceptRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> ConsentAcceptResponse:
    clerk_id = _get_clerk_id(request)

    # Reject if client sent a stale version (e.g. cached old page)
    if payload.tos_version != CURRENT_TOS_VERSION:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Stale TOS version. Please reload and accept version {CURRENT_TOS_VERSION}.",
        )

    result = await db.execute(select(User).where(User.clerk_id == clerk_id))
    user: User | None = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User record not found. Complete sign-up first.",
        )

    now = datetime.now(timezone.utc)

    # Idempotent: only write if not already accepted at current version
    if not user.has_accepted_current_tos:
        user.tos_accepted_at = now
        user.tos_version = CURRENT_TOS_VERSION

        # Audit log — write-only; no UPDATE/DELETE for app user
        db.add(AuditLog(
            user_id=user.id,
            action="tos_accepted",
            metadata_json={
                "tos_version": CURRENT_TOS_VERSION,
            },
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent", "")[:200],
        ))

        await db.commit()
        await db.refresh(user)

        logger.info(
            "tos_accepted",
            user_id=str(user.id),
            tos_version=CURRENT_TOS_VERSION,
        )
    else:
        logger.debug("tos_already_accepted", user_id=str(user.id))

    return ConsentAcceptResponse(
        accepted=True,
        tos_version=user.tos_version,  # type: ignore[arg-type]
        accepted_at=user.tos_accepted_at,  # type: ignore[arg-type]
    )
