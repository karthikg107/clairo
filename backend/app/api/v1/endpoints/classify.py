"""
CLR-013 — Document type classification endpoint.

POST /api/v1/classify
Accepts extracted document text, returns type + prohibited flag.
If prohibited: quota is NOT decremented (enforced here and in the
analysis endpoint by checking this result first).
"""
from __future__ import annotations

from pydantic import BaseModel, Field
from fastapi import APIRouter, HTTPException, status

from app.services.document_type import (
    DocumentType,
    DocumentTypeResult,
    detect_document_type,
)

router = APIRouter()


class ClassifyRequest(BaseModel):
    text: str = Field(..., min_length=10, max_length=100_000)


class ClassifyResponse(BaseModel):
    document_type: str
    is_prohibited: bool
    confidence: float
    reasoning: str
    referral: dict | None = None   # org + url + reason_key, only if prohibited


@router.post(
    "/classify",
    response_model=ClassifyResponse,
    tags=["analysis"],
    summary="Classify document type — blocks prohibited documents",
)
async def classify_endpoint(body: ClassifyRequest) -> ClassifyResponse:
    """
    Classify document type from extracted text.

    - Returns is_prohibited=True for court orders, immigration, medical,
      financial instruments, and documents involving minors.
    - Prohibited documents must NEVER proceed to analysis.
    - The quota decrement must NOT happen when is_prohibited=True.
    - Returns referral details so the frontend (CLR-038) can show
      the appropriate specialist organisation.
    """
    try:
        result: DocumentTypeResult = await detect_document_type(body.text)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": "classification_failed", "message": str(exc)},
        )

    return ClassifyResponse(
        document_type=result.document_type.value,
        is_prohibited=result.is_prohibited,
        confidence=round(result.confidence, 3),
        reasoning=result.reasoning,
        referral=result.referral,
    )
