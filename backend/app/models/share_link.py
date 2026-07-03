"""
ShareLink model — public shareable analysis links (CLR-041).

The row id IS the public share id in /s/[uuid] — a random UUIDv4, so
links are unguessable. The link serves ONLY sanitized analysis output
(see app/services/sharing.py); it never references the user, and the
FK cascade from analyses means GDPR deletion kills share links too.
"""
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import Boolean, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

SHARE_LINK_TTL_DAYS = 30


def default_expires_at() -> datetime:
    return datetime.now(UTC) + timedelta(days=SHARE_LINK_TTL_DAYS)


class ShareLink(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "share_links"

    analysis_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("analyses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=default_expires_at
    )
    is_revoked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Relationships
    analysis: Mapped["Analysis"] = relationship("Analysis")  # noqa: F821

    def is_active(self, now: datetime | None = None) -> bool:
        """Active = not revoked and not past expires_at."""
        now = now or datetime.now(UTC)
        expires = self.expires_at
        # Guard for unflushed instances / naive datetimes in tests
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=UTC)
        return not self.is_revoked and now < expires

    def __repr__(self) -> str:
        return f"<ShareLink id={self.id} analysis_id={self.analysis_id} revoked={self.is_revoked}>"
