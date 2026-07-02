"""
CLR-015 — Analysis endpoint.

POST /api/v1/analyse
Orchestrates the full analysis pipeline:
  1. Validate input
  2. Check document_type is not prohibited (CLR-013 must have run first)
  3. Check free-tier lifetime quota (CLR-025) — rejects before calling Claude
  4. Run Claude analysis (CLR-015/016), served from cache when available (CLR-019)
  5. del verified_text immediately after analysis (CLR-032 memory isolation)
  6. Consume one unit of quota on success (cache hit or miss both count)
  7. Return structured result, including current quota status

QUOTA: decremented only for permitted types (enforced here) and only on a
successful response — a failed/unavailable analysis does not cost quota.

DELETE /api/v1/analyse/cache
Manual cache flush (CLR-019) — for when legal review requires an updated
analysis of a previously-cached template. Audit logged.
"""
from __future__ import annotations

import structlog
from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, Field, field_validator

from app.api.v1.endpoints.quota import QuotaResponse
from app.core.http import get_clerk_id, get_client_ip
from app.core.redis import flush_analysis_cache
from app.db.session import get_session_factory
from app.models.audit_log import AuditLog
from app.services.analysis import AnalysisResult, AnalysisServiceError, analyse_document
from app.services.document_type import PERMITTED_TYPES
from app.services.quota import check_quota, consume_quota

logger = structlog.get_logger(__name__)

router = APIRouter()

_PERMITTED_TYPE_STRINGS = {t.value for t in PERMITTED_TYPES}


async def _write_audit_log(*, action: str, metadata: dict, request: Request) -> None:
    """
    Best-effort audit log write — never blocks or fails the caller's response.
    Metadata must never contain document content (only safe, structured fields).
    """
    try:
        factory = get_session_factory()
        async with factory() as session:
            session.add(AuditLog(
                action=action,
                metadata_json=metadata,
                ip_address=request.client.host if request.client else None,
                user_agent=request.headers.get("user-agent", "")[:200],
            ))
            await session.commit()
    except Exception as exc:
        logger.warning("analyse.audit_log_failed", action=action, error=str(exc))


class AnalyseRequest(BaseModel):
    verified_text: str = Field(..., min_length=10, max_length=200_000)
    doc_language: str = Field(..., pattern=r"^[a-z]{2}(-[a-zA-Z]{2,4})?$")
    country: str = Field(..., pattern=r"^[A-Z]{2}$")
    output_language: str = Field(..., pattern=r"^[a-z]{2}(-[a-zA-Z]{2,4})?$")
    document_type: str = Field(...)

    @field_validator("document_type")
    @classmethod
    def must_be_permitted(cls, v: str) -> str:
        if v not in _PERMITTED_TYPE_STRINGS:
            raise ValueError(
                f"document_type must be a permitted type; '{v}' is prohibited or unknown. "
                "Run /api/v1/classify first."
            )
        return v


class AnalyseResponse(BaseModel):
    document_type: str
    summary: str
    clauses: list[dict]
    protective_clause_count: int
    review_clause_count: int
    quota: QuotaResponse


@router.post(
    "/analyse",
    response_model=AnalyseResponse,
    tags=["analysis"],
    summary="Analyse a document and return structured clause explanations",
)
async def analyse_endpoint(body: AnalyseRequest, request: Request) -> AnalyseResponse:
    """
    Run Claude analysis on user-reviewed, verified document text.

    SECURITY:
    - document_type must be a permitted type (prohibited types raise 400).
    - verified_text is deleted from memory immediately after analysis —
      on every path, including the quota-exceeded and both error branches
      below (CLR-032/CLR-020/CLR-025).
    - System prompt cannot be overridden by any field in this request.
    - Response validated against strict schema before returning.
    - CLR-019: a cache hit is recorded in the audit log (metadata only,
      never document content).
    - CLR-020: Claude timeouts/unavailability surface as a clear 503;
      malformed responses (after Claude's own correction retry) as a 422.
    - CLR-025: free-tier lifetime quota (2 analyses) is checked BEFORE
      calling Claude (a 402 costs nothing) and consumed only after a
      successful response, so a failed/unavailable analysis never costs
      the user their quota.
    """
    clerk_id = get_clerk_id(request)
    anonymous_id = request.headers.get("X-Anonymous-Id")
    ip = get_client_ip(request)

    # Extract text then delete reference — will del after analysis
    verified_text = body.verified_text

    try:
        quota = await check_quota(clerk_id=clerk_id, anonymous_id=anonymous_id, ip=ip)
        if not quota.allowed:
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail={
                    "error": "quota_exceeded",
                    "message": "You've used your free analyses. Upgrade to continue.",
                    "used": quota.used,
                    "limit": quota.limit,
                },
            )

        try:
            result: AnalysisResult = await analyse_document(
                verified_text=verified_text,
                doc_language=body.doc_language,
                country=body.country,
                output_language=body.output_language,
                document_type=body.document_type,
            )
        except AnalysisServiceError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={"error": "analysis_unavailable", "message": str(exc)},
            )
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"error": "analysis_failed", "message": str(exc)},
            )
    finally:
        # CLR-032: purge document from memory immediately — runs on every
        # path above, including the quota-exceeded and error branches.
        del verified_text

    if result.cache_hit:
        await _write_audit_log(
            action="analysis_cache_hit",
            metadata={
                "document_type": result.document_type,
                "output_language": body.output_language,
                "country": body.country,
            },
            request=request,
        )

    if quota.is_free_tier:
        await consume_quota(clerk_id=clerk_id, anonymous_id=anonymous_id, ip=ip)
        quota = await check_quota(clerk_id=clerk_id, anonymous_id=anonymous_id, ip=ip)

    return AnalyseResponse(
        document_type=result.document_type,
        summary=result.summary,
        clauses=result.clauses,
        protective_clause_count=result.protective_clause_count,
        review_clause_count=result.review_clause_count,
        quota=QuotaResponse(
            allowed=quota.allowed,
            is_free_tier=quota.is_free_tier,
            used=quota.used,
            limit=quota.limit,
            remaining=quota.remaining,
        ),
    )


class CacheFlushRequest(BaseModel):
    text_hash: str = Field(..., pattern=r"^[a-f0-9]{64}$")
    output_language: str = Field(..., pattern=r"^[a-z]{2}(-[a-zA-Z]{2,4})?$")
    country: str = Field(..., pattern=r"^[A-Z]{2}$")


@router.delete(
    "/analyse/cache",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["analysis"],
    summary="Manually flush a cached analysis result (CLR-019)",
)
async def flush_cache_endpoint(body: CacheFlushRequest, request: Request) -> None:
    """
    Manual cache flush — used when legal review requires an updated analysis
    of a template that is already cached. Requires a valid JWT (enforced by
    JWTAuthMiddleware, CLR-031, on every non-public route).
    """
    await flush_analysis_cache(body.text_hash, body.output_language, body.country)
    await _write_audit_log(
        action="analysis_cache_flushed",
        metadata={
            "text_hash": body.text_hash,
            "output_language": body.output_language,
            "country": body.country,
        },
        request=request,
    )
