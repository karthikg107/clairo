"""
CLR-041 — Shareable analysis links.

SECURITY (non-negotiable):
- A share link serves ONLY: summary, clause explanations (title +
  plain-language explanation), flags, frequency stats, and counts.
- It NEVER serves: the original document, extracted OCR text, or any
  user identity. Concretely that means `clauses[].original_text`
  (verbatim document excerpts) and `clauses[].numbers` (exact
  amounts/dates lifted from the document) are STRIPPED before serving.
- Sanitization is a strict whitelist — unknown keys are dropped, so a
  future addition to result_json can never leak through a share link
  by default.
- Expired / revoked / unknown links are indistinguishable to callers
  (all raise ShareLinkNotFoundError), preventing enumeration probing.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.analysis import Analysis
from app.models.share_link import ShareLink, default_expires_at
from app.models.user import User

logger = get_logger(__name__)

# Whitelist of clause keys safe for public serving. NOT here, by design:
# original_text (document excerpt), numbers (exact figures from the document).
_SHARE_SAFE_CLAUSE_KEYS = (
    "id",
    "title",
    "explanation",
    "frequency_pct",
    "is_protective",
    "flag_level",
)


class SharingError(Exception):
    """Ownership/validation failure creating or revoking a share link."""


class ShareLinkNotFoundError(Exception):
    """Unknown, expired, or revoked link — deliberately indistinguishable."""


def sanitize_result_for_share(result_json: dict[str, Any]) -> dict[str, Any]:
    """
    Returns the publicly-shareable subset of an analysis result.

    Whitelist copy — anything not explicitly listed here is dropped,
    including clauses[].original_text and clauses[].numbers.
    """
    clauses = [
        {key: clause.get(key) for key in _SHARE_SAFE_CLAUSE_KEYS}
        for clause in result_json.get("clauses", [])
        if isinstance(clause, dict)
    ]
    return {
        "document_type": result_json.get("document_type"),
        "summary": result_json.get("summary"),
        "clauses": clauses,
        "protective_clause_count": result_json.get("protective_clause_count"),
        "review_clause_count": result_json.get("review_clause_count"),
    }


async def create_share_link(
    db: AsyncSession, *, user: User, analysis_id: uuid.UUID
) -> ShareLink:
    """
    Creates a share link for the user's own analysis. If an active
    (non-revoked, non-expired) link already exists for it, returns that
    instead of minting another — one canonical URL per analysis.
    """
    result = await db.execute(select(Analysis).where(Analysis.id == analysis_id))
    analysis = result.scalar_one_or_none()
    if analysis is None or analysis.user_id != user.id:
        # Same error for "not found" and "not yours" — don't confirm existence.
        raise SharingError("Analysis not found")

    existing_result = await db.execute(
        select(ShareLink).where(
            ShareLink.analysis_id == analysis_id,
            ShareLink.is_revoked.is_(False),
        )
    )
    for existing in existing_result.scalars():
        if existing.is_active():
            return existing

    # id and expires_at set explicitly (not left to column defaults, which
    # only apply at flush) so the response can serialize them immediately.
    link = ShareLink(
        id=uuid.uuid4(), analysis_id=analysis_id, expires_at=default_expires_at()
    )
    db.add(link)
    await db.commit()
    logger.info("sharing.link_created", analysis_id=str(analysis_id))
    return link


async def revoke_share_link(
    db: AsyncSession, *, user: User, share_id: uuid.UUID
) -> None:
    """Revokes the user's own share link. Takes effect instantly."""
    result = await db.execute(
        select(ShareLink, Analysis)
        .join(Analysis, ShareLink.analysis_id == Analysis.id)
        .where(ShareLink.id == share_id)
    )
    row = result.first()
    if row is None or row[1].user_id != user.id:
        raise SharingError("Share link not found")

    link: ShareLink = row[0]
    link.is_revoked = True
    await db.commit()
    logger.info("sharing.link_revoked", share_id=str(share_id))


async def get_shared_analysis(
    db: AsyncSession, *, share_id: uuid.UUID
) -> dict[str, Any]:
    """
    Public read path. Returns the sanitized payload plus non-identifying
    metadata (document type, language pair, analysis date, link expiry).

    Raises ShareLinkNotFoundError identically for unknown, expired, and
    revoked links.
    """
    result = await db.execute(
        select(ShareLink, Analysis)
        .join(Analysis, ShareLink.analysis_id == Analysis.id)
        .where(ShareLink.id == share_id)
    )
    row = result.first()
    if row is None:
        raise ShareLinkNotFoundError()

    link: ShareLink = row[0]
    analysis: Analysis = row[1]
    if not link.is_active(datetime.now(UTC)):
        raise ShareLinkNotFoundError()

    payload = sanitize_result_for_share(analysis.result_json)
    payload["document_type"] = analysis.document_type.value
    payload["doc_language"] = analysis.doc_language
    payload["output_language"] = analysis.output_language
    payload["analysed_at"] = analysis.created_at.isoformat() if analysis.created_at else None
    payload["expires_at"] = link.expires_at.isoformat()
    return payload
