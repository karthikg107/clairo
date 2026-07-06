"""
Upload validation endpoint.

POST /api/v1/upload/validate
- Receives file in memory (SpooledTemporaryFile never spills to disk at our size limit)
- Runs full validation pipeline
- Returns validation result — does NOT trigger OCR (that is CLR-010)

SECURITY: File is held in memory only. No disk writes. Content never logged.
"""
from __future__ import annotations

from fastapi import APIRouter, File, HTTPException, Request, UploadFile, status
from pydantic import BaseModel

from app.core.http import get_clerk_id, get_client_ip
from app.core.logging import get_logger
from app.core.rate_limit import check_upload_rate_limit
from app.core.security_events import (
    EVENT_RATE_LIMIT_HIT,
    EVENT_UPLOAD_REJECTED,
    log_security_event,
)
from app.services.file_validation import MAX_FILE_BYTES, validate_file

router = APIRouter()
logger = get_logger(__name__)


def _is_paid_tier(request: Request) -> bool:
    # Populated by JWTAuthMiddleware from Clerk public metadata (CLR-031);
    # defaults to free when auth middleware is not active (local dev).
    tier = getattr(request.state, "subscription_tier", "free")
    return tier not in ("free", None, "")


class ValidationResponse(BaseModel):
    valid: bool
    error_code: str | None = None
    message: str | None = None


@router.post(
    "/upload/validate",
    response_model=ValidationResponse,
    status_code=200,
    tags=["upload"],
    summary="Validate uploaded file before OCR",
)
async def validate_upload(
    request: Request,
    file: UploadFile = File(...),
) -> ValidationResponse:
    """
    Validate a file upload:
    - Size ≤ 25 MB
    - Allowed MIME type (PDF, DOCX, JPG, PNG, HEIC)
    - Magic bytes match declared MIME
    - ClamAV virus scan

    Returns 200 with valid=True/False. Callers should check `valid` before proceeding.
    Returns 413 if file exceeds 25 MB before any reads (enforced by nginx/Vercel as well).
    """
    # Per-user upload rate limit (item 9): free 10/hr, paid 50/hr. Keyed by
    # Clerk id when signed in, else client IP. Fail-open on Redis errors.
    identifier = get_clerk_id(request) or get_client_ip(request)
    upload_rl = await check_upload_rate_limit(identifier, paid=_is_paid_tier(request))
    if not upload_rl.allowed:
        await log_security_event(
            action=EVENT_RATE_LIMIT_HIT,
            request=request,
            metadata={"scope": "upload", "limit": upload_rl.limit},
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "error_code": "UPLOAD_RATE_LIMIT",
                "message": "Upload limit reached. Please try again later.",
            },
            headers={"Retry-After": str(upload_rl.reset_in_seconds)},
        )

    # Check Content-Length early to avoid reading a huge payload
    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > MAX_FILE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail={"error_code": "FILE_TOO_LARGE", "message": "File exceeds 25 MB"},
        )

    if not file.filename:
        raise HTTPException(status_code=400, detail={"error_code": "NO_FILENAME"})

    content_type = file.content_type or "application/octet-stream"

    # Read entire file into memory — NEVER write to disk
    data = await file.read()

    result = await validate_file(
        data=data,
        declared_mime=content_type,
        filename=file.filename,
    )

    # Immediately discard — do not hold reference longer than needed
    del data

    if not result.valid:
        # Security log — records the rejection reason (error code) only,
        # never the file content or bytes.
        await log_security_event(
            action=EVENT_UPLOAD_REJECTED,
            request=request,
            metadata={"error_code": result.error_code},
        )
        return ValidationResponse(
            valid=False,
            error_code=result.error_code,
            message=result.error_detail,
        )

    return ValidationResponse(valid=True)
