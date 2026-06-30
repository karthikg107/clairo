"""
OCR endpoint.

POST /api/v1/ocr
- Receives validated file bytes
- Runs OCR pipeline (GCV → Textract fallback)
- Purges document from memory immediately after OCR
- Returns structured per-word result (NO raw document content)
"""
from __future__ import annotations

from fastapi import APIRouter, File, HTTPException, UploadFile, status
from pydantic import BaseModel

from app.core.logging import get_logger
from app.services.file_validation import AllowedMime, validate_file
from app.services.ocr import ConfidenceLevel, OcrResult, run_ocr

router = APIRouter()
logger = get_logger(__name__)


class OcrWordOut(BaseModel):
    text: str
    confidence: float
    confidence_level: str
    bounding_box: dict | None = None


class OcrPageOut(BaseModel):
    page_number: int
    words: list[OcrWordOut]
    low_confidence_ratio: float


class OcrResponse(BaseModel):
    pages: list[OcrPageOut]
    total_pages: int
    source: str                    # "gcv" | "textract" | "direct"
    skip_review: bool              # True for PDF/DOCX (review screen skipped)


@router.post(
    "/ocr",
    response_model=OcrResponse,
    tags=["upload"],
    summary="Run OCR on a validated file",
)
async def ocr_endpoint(
    file: UploadFile = File(...),
) -> OcrResponse:
    """
    Run OCR on an uploaded file.

    - PDF/DOCX: direct text extraction (confidence = 1.0, review screen skipped)
    - Images: Google Cloud Vision → Textract fallback

    SECURITY:
    - File held in memory only — never written to disk
    - Document purged from memory immediately after OCR
    - Response contains structured word data — NOT raw document text as a blob
    """
    if not file.content_type:
        raise HTTPException(status_code=400, detail="Missing content type")

    data = await file.read()

    # Re-validate (defence in depth — should already be validated by /upload/validate)
    validation = await validate_file(
        data=data,
        declared_mime=file.content_type,
        filename=file.filename or "upload",
    )
    if not validation.valid:
        del data
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error_code": validation.error_code},
        )

    try:
        result: OcrResult = await run_ocr(
            data=data,
            mime_type=file.content_type,
            filename=file.filename or "upload",
        )
    finally:
        # SECURITY: Purge document from memory immediately after OCR
        del data

    is_digital = file.content_type in (AllowedMime.PDF.value, AllowedMime.DOCX.value)

    return OcrResponse(
        pages=[
            OcrPageOut(
                page_number=p.page_number,
                words=[
                    OcrWordOut(
                        text=w.text,
                        confidence=round(w.confidence, 3),
                        confidence_level=w.confidence_level.value,
                        bounding_box=w.bounding_box,
                    )
                    for w in p.words
                ],
                low_confidence_ratio=round(p.low_confidence_ratio, 3),
            )
            for p in result.pages
        ],
        total_pages=result.total_pages,
        source=result.source,
        skip_review=is_digital,
    )
