"""
CLR-023 — Analysis history for the user dashboard.

GET /api/v1/analyses
  Authenticated only. Returns the caller's past analyses, most recent
  first. Search/filter (by document type, free text on date/summary) is
  intentionally done client-side — history size for this product is
  small enough that shipping the full list once is simpler and cheaper
  than a server-side search endpoint.
"""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.http import require_user
from app.db.session import get_db
from app.models.analysis import Analysis

router = APIRouter(tags=["history"])


class AnalysisHistoryItem(BaseModel):
    id: str
    document_type: str
    doc_language: str
    output_language: str
    summary: str
    created_at: datetime


class AnalysisHistoryResponse(BaseModel):
    items: list[AnalysisHistoryItem]
    total: int


@router.get("/analyses", response_model=AnalysisHistoryResponse)
async def list_analyses(
    request: Request,
    db: AsyncSession = Depends(get_db),
    limit: int = Query(default=100, ge=1, le=500),
) -> AnalysisHistoryResponse:
    user = await require_user(request, db)

    result = await db.execute(
        select(Analysis)
        .where(Analysis.user_id == user.id)
        .order_by(Analysis.created_at.desc())
        .limit(limit)
    )
    rows = result.scalars().all()

    items = [
        AnalysisHistoryItem(
            id=str(row.id),
            document_type=row.document_type.value,
            doc_language=row.doc_language,
            output_language=row.output_language,
            summary=row.result_json.get("summary", ""),
            created_at=row.created_at,
        )
        for row in rows
    ]
    return AnalysisHistoryResponse(items=items, total=len(items))
