"""
CLR-012 — Language detection endpoint.

POST /api/v1/detect-language
Accepts plain extracted text (not raw document bytes) and returns the
detected language, confidence level, and whether it mismatches the
user's selection.

SECURITY: This endpoint never receives raw document bytes.
          Text passed here must already be extracted (by /api/v1/ocr).
"""
from __future__ import annotations

from pydantic import BaseModel, Field

from fastapi import APIRouter

from app.services.language_detection import (
    DetectionConfidence,
    LanguageDetectionResult,
    SUPPORTED_LANGUAGES,
    detect_language,
)

router = APIRouter()


class DetectLanguageRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=50_000)
    user_selected_code: str | None = Field(
        None,
        description="BCP-47 code the user chose in the UI (optional).",
        pattern=r"^[a-z]{2}(-[a-zA-Z]{2,4})?$",
    )


class DetectLanguageResponse(BaseModel):
    detected_code: str | None
    detected_name: str | None
    confidence: str                # "high" | "low" | "insufficient"
    probability: float
    mismatch: bool
    user_selected_code: str | None
    user_selected_name: str | None
    supported_languages: dict[str, str]


@router.post(
    "/detect-language",
    response_model=DetectLanguageResponse,
    tags=["upload"],
    summary="Detect language of extracted document text",
)
async def detect_language_endpoint(
    body: DetectLanguageRequest,
) -> DetectLanguageResponse:
    """
    Detect the language of extracted document text.

    - Returns detected BCP-47 code and confidence.
    - If *user_selected_code* is provided and detection is high-confidence,
      sets *mismatch=True* when they differ — the frontend uses this to
      show the language mismatch warning (CLR-012).
    - Also returns *supported_languages* so the frontend can render the
      override dropdown without a separate fetch.
    """
    result: LanguageDetectionResult = detect_language(
        text=body.text,
        user_selected_code=body.user_selected_code,
    )

    return DetectLanguageResponse(
        detected_code=result.detected_code,
        detected_name=result.detected_name,
        confidence=result.confidence.value,
        probability=result.probability,
        mismatch=result.mismatch,
        user_selected_code=result.user_selected_code,
        user_selected_name=result.user_selected_name,
        supported_languages=SUPPORTED_LANGUAGES,
    )
