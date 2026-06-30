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

from app.core.logging import get_logger
from app.services.file_validation import MAX_FILE_BYTES, validate_file

router = APIRouter()
logger = get_logger(__name__)


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
        return ValidationResponse(
            valid=False,
            error_code=result.error_code,
            message=result.error_detail,
        )

    return ValidationResponse(valid=True)
