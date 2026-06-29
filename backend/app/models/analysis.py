"""
Analysis model — stores structured AI output only.

SECURITY (non-negotiable):
- NO document_content column
- NO raw_text column
- NO ocr_text column
- NO extracted_text column
- result_json stores ONLY the structured analysis JSON (flags, clauses, summary)
- Document is processed in memory and purged immediately after OCR
"""
import enum
import uuid

from sqlalchemy import Enum, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class DocumentType(str, enum.Enum):
    rental = "rental"
    employment = "employment"
    freelance = "freelance"
    tos = "tos"
    other_permitted = "other_permitted"
    # prohibited types are rejected at upload — never reach this table


class Analysis(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "analyses"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Document metadata — safe to store
    document_type: Mapped[DocumentType] = mapped_column(
        Enum(DocumentType, name="document_type_enum"), nullable=False
    )
    locale: Mapped[str] = mapped_column(String(10), nullable=False)  # e.g. "en", "ar"
    page_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    processing_time_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # ── SECURITY: this column stores ONLY structured JSON output ─────────────
    # Allowed keys: summary, flags, clauses, risk_score, language_detected
    # FORBIDDEN keys (rejected at write time): content, text, raw, ocr, document
    # ─────────────────────────────────────────────────────────────────────────
    result_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="analyses")  # noqa: F821

    def __repr__(self) -> str:
        return f"<Analysis id={self.id} user_id={self.user_id} type={self.document_type}>"
