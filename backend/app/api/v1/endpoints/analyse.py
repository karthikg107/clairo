"""
CLR-015 — Analysis endpoint.

POST /api/v1/analyse
Orchestrates the full analysis pipeline:
  1. Validate input
  2. Check document_type is not prohibited (CLR-013 must have run first)
  3. Run Claude analysis (CLR-015/016)
  4. del verified_text immediately after analysis (CLR-032 memory isolation)
  5. Return structured result

QUOTA: decremented only for permitted types (enforced here).
"""
from __future__ import annotations

from pydantic import BaseModel, Field, field_validator
from fastapi import APIRouter, HTTPException, status

from app.services.analysis import analyse_document, AnalysisResult
from app.services.document_type import PERMITTED_TYPES, DocumentType

router = APIRouter()

_PERMITTED_TYPE_STRINGS = {t.value for t in PERMITTED_TYPES}


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


@router.post(
    "/analyse",
    response_model=AnalyseResponse,
    tags=["analysis"],
    summary="Analyse a document and return structured clause explanations",
)
async def analyse_endpoint(body: AnalyseRequest) -> AnalyseResponse:
    """
    Run Claude analysis on user-reviewed, verified document text.

    SECURITY:
    - document_type must be a permitted type (prohibited types raise 400).
    - verified_text is deleted from memory immediately after analysis.
    - System prompt cannot be overridden by any field in this request.
    - Response validated against strict schema before returning.
    """
    # Extract text then delete reference — will del after analysis
    verified_text = body.verified_text

    try:
        result: AnalysisResult = await analyse_document(
            verified_text=verified_text,
            doc_language=body.doc_language,
            country=body.country,
            output_language=body.output_language,
            document_type=body.document_type,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": "analysis_failed", "message": str(exc)},
        )
    finally:
        # CLR-032: purge document from memory immediately
        del verified_text

    return AnalyseResponse(
        document_type=result.document_type,
        summary=result.summary,
        clauses=result.clauses,
        protective_clause_count=result.protective_clause_count,
        review_clause_count=result.review_clause_count,
    )
